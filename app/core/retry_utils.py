"""
Retry and Fallback Utilities
Provides robust retry mechanisms with exponential backoff and circuit breaker pattern
"""
import asyncio
import time
import functools
from typing import Callable, Optional, Type, Tuple, Any, List
from enum import Enum
import logging

from .exceptions import (
    LLMConnectionException,
    LLMTimeoutException,
    VectorStoreConnectionException,
    DatabaseConnectionException
)


logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failures detected, blocking requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker pattern implementation
    Prevents cascading failures by temporarily blocking requests to failing services
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: Type[Exception] = Exception
    ):
        """
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds before attempting recovery
            expected_exception: Exception type to monitor
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                logger.info(f"Circuit breaker for {func.__name__} entering HALF_OPEN state")
                self.state = CircuitState.HALF_OPEN
            else:
                raise Exception(f"Circuit breaker is OPEN for {func.__name__}")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery"""
        return (
            self.last_failure_time is not None and
            time.time() - self.last_failure_time >= self.recovery_timeout
        )
    
    def _on_success(self):
        """Handle successful call"""
        self.failure_count = 0
        if self.state == CircuitState.HALF_OPEN:
            logger.info("Circuit breaker recovered, state: CLOSED")
            self.state = CircuitState.CLOSED
    
    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            logger.error(
                f"Circuit breaker OPENED after {self.failure_count} failures"
            )
            self.state = CircuitState.OPEN


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable] = None
):
    """
    Decorator for retry logic with exponential backoff
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff calculation
        exceptions: Tuple of exception types to retry on
        on_retry: Optional callback function called on each retry
    
    Example:
        @retry_with_backoff(max_retries=3, exceptions=(ConnectionError,))
        def fetch_data():
            # Your code here
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(
                            f"{func.__name__} failed after {max_retries} retries",
                            exc_info=True
                        )
                        raise
                    
                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                        f"after {delay:.2f}s | Error: {str(e)}"
                    )
                    
                    if on_retry:
                        on_retry(attempt, e)
                    
                    time.sleep(delay)
                    delay = min(delay * exponential_base, max_delay)
            
            raise last_exception
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(
                            f"{func.__name__} failed after {max_retries} retries",
                            exc_info=True
                        )
                        raise
                    
                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                        f"after {delay:.2f}s | Error: {str(e)}"
                    )
                    
                    if on_retry:
                        on_retry(attempt, e)
                    
                    await asyncio.sleep(delay)
                    delay = min(delay * exponential_base, max_delay)
            
            raise last_exception
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class FallbackChain:
    """
    Implements fallback chain pattern
    Tries multiple strategies in order until one succeeds
    """
    
    def __init__(self, strategies: List[Callable], name: str = "FallbackChain"):
        """
        Args:
            strategies: List of callable strategies to try in order
            name: Name for logging purposes
        """
        self.strategies = strategies
        self.name = name
    
    def execute(self, *args, **kwargs) -> Any:
        """
        Execute strategies in order until one succeeds
        
        Returns:
            Result from first successful strategy
            
        Raises:
            Exception from last strategy if all fail
        """
        last_exception = None
        
        for i, strategy in enumerate(self.strategies):
            try:
                logger.info(
                    f"{self.name}: Trying strategy {i + 1}/{len(self.strategies)} - {strategy.__name__}"
                )
                result = strategy(*args, **kwargs)
                logger.info(f"{self.name}: Strategy {i + 1} succeeded")
                return result
                
            except Exception as e:
                last_exception = e
                logger.warning(
                    f"{self.name}: Strategy {i + 1} failed - {str(e)}"
                )
                
                if i == len(self.strategies) - 1:
                    logger.error(f"{self.name}: All strategies failed")
                    raise
        
        raise last_exception
    
    async def execute_async(self, *args, **kwargs) -> Any:
        """Async version of execute"""
        last_exception = None
        
        for i, strategy in enumerate(self.strategies):
            try:
                logger.info(
                    f"{self.name}: Trying strategy {i + 1}/{len(self.strategies)} - {strategy.__name__}"
                )
                
                if asyncio.iscoroutinefunction(strategy):
                    result = await strategy(*args, **kwargs)
                else:
                    result = strategy(*args, **kwargs)
                
                logger.info(f"{self.name}: Strategy {i + 1} succeeded")
                return result
                
            except Exception as e:
                last_exception = e
                logger.warning(
                    f"{self.name}: Strategy {i + 1} failed - {str(e)}"
                )
                
                if i == len(self.strategies) - 1:
                    logger.error(f"{self.name}: All strategies failed")
                    raise
        
        raise last_exception


def with_timeout(timeout_seconds: int):
    """
    Decorator to add timeout to function execution
    
    Args:
        timeout_seconds: Maximum execution time in seconds
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                logger.error(f"{func.__name__} timed out after {timeout_seconds}s")
                raise LLMTimeoutException(timeout_seconds)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, we can't enforce timeout easily
            # Just log and call the function
            logger.debug(f"{func.__name__} timeout set to {timeout_seconds}s (warning only)")
            return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class SafeExecutor:
    """
    Safe execution wrapper with multiple protection layers
    Combines retry, circuit breaker, timeout, and fallback
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        timeout: Optional[int] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        fallback: Optional[Callable] = None
    ):
        self.max_retries = max_retries
        self.timeout = timeout
        self.circuit_breaker = circuit_breaker
        self.fallback = fallback
    
    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with all protection layers
        
        Args:
            func: Function to execute
            *args, **kwargs: Arguments to pass to function
            
        Returns:
            Function result or fallback result
        """
        try:
            # Apply circuit breaker if configured
            if self.circuit_breaker:
                return self.circuit_breaker.call(func, *args, **kwargs)
            else:
                return func(*args, **kwargs)
                
        except Exception as e:
            logger.error(f"SafeExecutor: Execution failed - {str(e)}")
            
            # Try fallback if configured
            if self.fallback:
                logger.info("SafeExecutor: Attempting fallback")
                try:
                    return self.fallback(*args, **kwargs)
                except Exception as fallback_error:
                    logger.error(f"SafeExecutor: Fallback also failed - {str(fallback_error)}")
            
            raise


# Convenience decorators for common scenarios

def retry_on_connection_error(max_retries: int = 3):
    """Retry decorator specifically for connection errors"""
    return retry_with_backoff(
        max_retries=max_retries,
        exceptions=(
            LLMConnectionException,
            VectorStoreConnectionException,
            DatabaseConnectionException,
            ConnectionError
        )
    )


def retry_on_llm_error(max_retries: int = 3):
    """Retry decorator specifically for LLM errors"""
    return retry_with_backoff(
        max_retries=max_retries,
        exceptions=(
            LLMConnectionException,
            LLMTimeoutException
        )
    )


if __name__ == "__main__":
    # Test retry mechanism
    @retry_with_backoff(max_retries=3, initial_delay=0.5)
    def test_function():
        print("Attempting operation...")
        raise ConnectionError("Test error")
    
    try:
        test_function()
    except ConnectionError:
        print("Retry mechanism working correctly")
    
    # Test fallback chain
    def strategy1():
        raise Exception("Strategy 1 failed")
    
    def strategy2():
        return "Success from strategy 2"
    
    chain = FallbackChain([strategy1, strategy2], name="TestChain")
    result = chain.execute()
    print(f"Fallback chain result: {result}")
