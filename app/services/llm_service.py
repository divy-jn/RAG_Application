"""
Cloud LLM Service — Universal OpenAI-Compatible Interface
Provides a provider-agnostic LLM interface using the /v1/chat/completions standard.
Switch providers/models by changing LLM_BASE_URL, LLM_API_KEY, LLM_MODEL in .env.
"""
import asyncio
import json
import httpx
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

try:
    from langsmith import traceable, get_current_run_tree
except ImportError:
    # Fallback: no-op decorator if langsmith not installed
    def traceable(**kwargs):
        def decorator(func):
            return func
        return decorator
    
    def get_current_run_tree():
        return None


from app.core.logging_config import LoggerMixin, LogExecutionTime, get_logger
from app.core.exceptions import (
    LLMConnectionException,
    LLMModelNotFoundException,
    LLMGenerationException,
    LLMTimeoutException,
    LLMRateLimitException
)
from app.core.retry_utils import (
    retry_with_backoff,
    CircuitBreaker,
    with_timeout,
    SafeExecutor
)
from app.core.config import settings


logger = get_logger(__name__)


class CloudLLMService(LoggerMixin):
    """
    Universal cloud LLM service using OpenAI-compatible /v1/chat/completions API.
    
    Works with any OpenAI-compatible provider:
    - Ollama Cloud (https://ollama.com/v1)
    - OpenAI (https://api.openai.com/v1)
    - Together AI (https://api.together.xyz/v1)
    - Groq (https://api.groq.com/openai/v1)
    - Local Ollama (http://localhost:11434/v1)
    
    Configure via .env:
        LLM_BASE_URL=https://ollama.com/v1
        LLM_API_KEY=your-key
        LLM_MODEL=gpt-oss:120b-cloud
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 120
    ):
        """
        Initialize Cloud LLM Service
        
        Args:
            base_url: API base URL (defaults to settings.LLM_BASE_URL)
            model: Model name (defaults to settings.LLM_MODEL)
            api_key: API key (defaults to settings.LLM_API_KEY)
            timeout: Request timeout in seconds
        """
        self.base_url = (base_url or settings.LLM_BASE_URL).rstrip("/")
        self.model = model or settings.LLM_MODEL
        self.api_key = api_key or settings.LLM_API_KEY
        self.timeout = timeout
        
        # Circuit breaker to prevent cascading failures
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60,
            expected_exception=LLMConnectionException
        )
        
        # Build default headers
        self._headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            self._headers["Authorization"] = f"Bearer {self.api_key}"
        
        # HTTP client with timeout
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            headers=self._headers
        )
        
        self.logger.info(
            f"Initialized Cloud LLM Service | Model: {self.model} | URL: {self.base_url}"
        )
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
        self.logger.info("LLM Service closed")
    
    @retry_with_backoff(
        max_retries=3,
        initial_delay=1.0,
        exceptions=(LLMConnectionException, LLMTimeoutException)
    )
    async def check_model_availability(self) -> bool:
        """
        Check if the cloud API is reachable and the model is available.
        
        Returns:
            True if API is reachable
            
        Raises:
            LLMConnectionException: If cannot connect to the API
        """
        with LogExecutionTime(self.logger, "Check model availability"):
            try:
                response = await self.client.get(f"{self.base_url}/models")
                
                if response.status_code == 401:
                    self.logger.error("API key is invalid or missing")
                    raise LLMConnectionException(
                        url=self.base_url,
                        original_exception=Exception("Invalid API key (401 Unauthorized)")
                    )
                
                if response.status_code != 200:
                    # Non-critical: some providers don't support /models
                    self.logger.warning(
                        f"Models endpoint returned {response.status_code} — "
                        f"this is OK, model availability will be verified on first call"
                    )
                    return True
                
                # Try to find the model in the list
                data = response.json()
                models = data.get("data", data.get("models", []))
                
                if models:
                    model_ids = [
                        m.get("id", m.get("name", "")) 
                        for m in models if isinstance(m, dict)
                    ]
                    model_found = any(self.model in mid for mid in model_ids)
                    
                    if model_found:
                        self.logger.info(f"✅ Model '{self.model}' is available")
                    else:
                        self.logger.warning(
                            f"Model '{self.model}' not found in list. "
                            f"Available: {model_ids[:10]}... "
                            f"Will attempt to use it anyway."
                        )
                
                return True
                
            except httpx.ConnectError as e:
                raise LLMConnectionException(
                    url=self.base_url,
                    original_exception=e
                )
            except httpx.TimeoutException as e:
                raise LLMTimeoutException(timeout_seconds=self.timeout)
    
    @traceable(name="cloud_llm_generate", run_type="llm")
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        stream: bool = False,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate text using OpenAI-compatible chat completions API.
        
        Args:
            prompt: User prompt
            system_prompt: System prompt for context
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            top_p: Top-p sampling parameter
            stream: Whether to stream response
            context: Additional context for logging
            
        Returns:
            Generated text
            
        Raises:
            LLMGenerationException: If generation fails
        """
        # Use defaults from settings if not provided
        temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE
        max_tokens = max_tokens or settings.LLM_MAX_TOKENS
        top_p = top_p if top_p is not None else settings.LLM_TOP_P
        
        context = context or {}
        
        self.logger.info(
            f"🧠 Generating response | "
            f"Prompt length: {len(prompt)} chars | "
            f"Temperature: {temperature} | "
            f"Max tokens: {max_tokens}",
            extra=context
        )
        
        with LogExecutionTime(self.logger, "LLM Generation", logging.INFO):
            try:
                # Execute with circuit breaker protection
                result, usage = await self._generate_with_protection(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    stream=stream
                )
                
                # Report token usage to LangSmith
                run = get_current_run_tree()
                if run and usage:
                    # Update run metadata and extra usage
                    run.metadata["usage"] = usage
                    if hasattr(run, "extra"):
                        if "usage" not in run.extra:
                            run.extra["usage"] = usage
                        else:
                            run.extra["usage"].update(usage)
                
                self.logger.info(
                    f"Generated response | "
                    f"Length: {len(result)} chars",
                    extra=context
                )
                
                return result
                
            except Exception as e:
                self.logger.error(
                    f"Generation failed | Error: {str(e)}",
                    exc_info=True,
                    extra=context
                )
                raise
    
    def _build_messages(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """Build OpenAI-compatible messages array from prompt and system prompt."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages
    
    @retry_with_backoff(
        max_retries=settings.LLM_MAX_RETRIES,
        initial_delay=2.0,
        max_delay=30.0,
        exceptions=(LLMConnectionException, LLMTimeoutException)
    )
    async def _generate_with_protection(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
        top_p: float,
        stream: bool
    ) -> tuple[str, Optional[Dict[str, Any]]]:
        """
        Internal generation method with retry protection.
        Uses OpenAI-compatible /v1/chat/completions endpoint.
        """
        try:
            # Build OpenAI-compatible request payload
            messages = self._build_messages(prompt, system_prompt)
            
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p,
                "stream": stream
            }
            
            # Make request
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json=payload
            )
            
            if response.status_code == 429:
                raise LLMRateLimitException()
            
            if response.status_code == 401:
                raise LLMGenerationException(
                    prompt_sample=prompt[:100],
                    reason="API key is invalid or expired (401 Unauthorized)",
                    original_exception=None
                )
            
            if response.status_code != 200:
                raise LLMGenerationException(
                    prompt_sample=prompt[:100],
                    reason=f"HTTP {response.status_code}: {response.text}",
                    original_exception=None
                )
            
                return full_response, None  # Streaming usage tracking is more complex, returning None for now
            else:
                # Handle non-streaming response
                data = response.json()
                usage = data.get("usage")
                choices = data.get("choices", [])
                if not choices:
                    raise LLMGenerationException(
                        prompt_sample=prompt[:100],
                        reason=f"Empty response from API: {data}",
                        original_exception=None
                    )
                content = choices[0].get("message", {}).get("content", "")
                return content, usage
            
        except httpx.ConnectError as e:
            raise LLMConnectionException(
                url=self.base_url,
                original_exception=e
            )
        except httpx.TimeoutException:
            raise LLMTimeoutException(timeout_seconds=self.timeout)
        except LLMRateLimitException:
            raise
        except Exception as e:
            if not isinstance(e, (LLMConnectionException, LLMTimeoutException, LLMGenerationException)):
                raise LLMGenerationException(
                    prompt_sample=prompt[:100],
                    reason=str(e),
                    original_exception=e
                )
            raise
    
    async def generate_with_fallback(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        fallback_response: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Generate with fallback to default response if all retries fail
        
        Args:
            prompt: User prompt
            system_prompt: System prompt
            fallback_response: Response to return if generation fails
            **kwargs: Additional arguments for generate()
            
        Returns:
            Generated text or fallback response
        """
        try:
            return await self.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                **kwargs
            )
        except Exception as e:
            self.logger.warning(
                f"Generation failed, using fallback | Error: {str(e)}"
            )
            
            if fallback_response:
                return fallback_response
            else:
                return (
                    "I apologize, but I'm having trouble generating a response "
                    "right now. Please try again in a moment."
                )
    
    @traceable(name="cloud_llm_chat", run_type="llm")
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Chat completion with message history.
        Directly uses the messages array with the OpenAI API.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            context: Additional context for logging
            
        Returns:
            Assistant's response
        """
        # Build system prompt and user prompt from messages
        system_messages = [m for m in messages if m.get("role") == "system"]
        user_messages = [m for m in messages if m.get("role") in ("user", "assistant")]
        
        system_prompt = None
        if system_messages:
            system_prompt = "\n".join(m.get("content", "") for m in system_messages)
        
        # Build conversation context
        conversation = "\n".join(
            f"{m.get('role', 'user').title()}: {m.get('content', '')}"
            for m in user_messages
        )
        
        return await self.generate(
            prompt=conversation,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            context=context
        )
    

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Generate streaming text using OpenAI-compatible SSE streaming.
        
        Yields:
             Text chunks
        """
        # Use defaults from settings if not provided
        temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE
        max_tokens = max_tokens or settings.LLM_MAX_TOKENS
        top_p = top_p if top_p is not None else settings.LLM_TOP_P
        
        context = context or {}
        
        self.logger.info(
            f"🧠 Streaming response | "
            f"Prompt length: {len(prompt)} chars",
            extra=context
        )
        
        try:
            # Build OpenAI-compatible request payload
            messages = self._build_messages(prompt, system_prompt)
            
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p,
                "stream": True
            }
            
            # Streaming request using SSE format
            async with self.client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=payload
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    raise LLMGenerationException(
                        prompt_sample=prompt[:100],
                        reason=f"HTTP {response.status_code}: {error_text.decode()}",
                        original_exception=None
                    )
                
                # Parse SSE stream
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
                            
        except Exception as e:
            self.logger.error(
                f"Streaming failed | Error: {str(e)}",
                exc_info=True,
                extra=context
            )
            # Re-raise so the caller handles it (e.g. closes the stream)
            raise

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Chat completion with streaming
        """
        # Reuse chat logic to build prompt
        system_messages = [m for m in messages if m.get("role") == "system"]
        user_messages = [m for m in messages if m.get("role") in ("user", "assistant")]
        
        system_prompt = None
        if system_messages:
            system_prompt = "\n".join(m.get("content", "") for m in system_messages)
        
        conversation = "\n".join(
            f"{m.get('role', 'user').title()}: {m.get('content', '')}"
            for m in user_messages
        )
        
        async for chunk in self.generate_stream(
            prompt=conversation,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            context=context
        ):
            yield chunk



# Singleton instance for application-wide use
_llm_service_instance: Optional[CloudLLMService] = None



def set_llm_service_override(service: CloudLLMService):
    """Override the global instance (for testing)"""
    global _llm_service_instance
    _llm_service_instance = service


async def get_llm_service() -> CloudLLMService:
    """
    Get or create LLM service singleton instance.
    Compatible with FastAPI Depends.
    """
    global _llm_service_instance
    
    if _llm_service_instance is None:
        _llm_service_instance = CloudLLMService()
        # Verify API connectivity on first use
        try:
            await _llm_service_instance.check_model_availability()
        except Exception as e:
            logger.warning(f"LLM API check failed on init: {e}")
    
    return _llm_service_instance


async def close_llm_service():
    """Close the global LLM service instance"""
    global _llm_service_instance
    
    if _llm_service_instance:
        await _llm_service_instance.close()
        _llm_service_instance = None


if __name__ == "__main__":
    # Test LLM service
    async def test():
        async with CloudLLMService() as llm:
            # Check availability
            await llm.check_model_availability()
            
            # Test generation
            response = await llm.generate(
                prompt="What is machine learning?",
                system_prompt="You are a helpful AI assistant.",
                max_tokens=100
            )
            
            print(f"\nResponse:\n{response}\n")
            
            # Test chat
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello!"},
                {"role": "assistant", "content": "Hi! How can I help you?"},
                {"role": "user", "content": "Tell me a joke."}
            ]
            
            chat_response = await llm.chat(messages, max_tokens=50)
            print(f"\nChat Response:\n{chat_response}\n")
    
    asyncio.run(test())
