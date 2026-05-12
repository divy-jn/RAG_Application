"""
Advanced Logging Configuration
Provides structured logging with rotation, different levels, and formatters
"""
import logging
import logging.handlers
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict
import traceback


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields if present
        if hasattr(record, 'user_id'):
            log_data['user_id'] = record.user_id
        if hasattr(record, 'request_id'):
            log_data['request_id'] = record.request_id
        if hasattr(record, 'execution_time'):
            log_data['execution_time'] = record.execution_time
        
        return json.dumps(log_data)


class ColoredFormatter(logging.Formatter):
    """Colored console output for better readability"""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'       # Reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        log_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        
        # Build log message
        log_msg = (
            f"{log_color}[{record.levelname}]{reset} "
            f"{timestamp} | {record.name} | "
            f"{record.funcName}:{record.lineno} | "
            f"{record.getMessage()}"
        )
        
        # Add exception if present
        if record.exc_info:
            log_msg += f"\n{reset}{self.formatException(record.exc_info)}"
        
        return log_msg


def setup_logging(
    log_dir: str = "logs",
    log_level: str = "INFO",
    console_output: bool = True,
    json_output: bool = False
) -> None:
    """
    Setup comprehensive logging system
    
    Args:
        log_dir: Directory for log files
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        console_output: Enable console logging
        json_output: Use JSON format for file logs
    """
    
    # Create logs directory
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Console Handler (colored, human-readable)
    if console_output:
        import io
        # Use UTF-8 encoding to handle emoji characters on Windows
        utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
        console_handler = logging.StreamHandler(utf8_stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(ColoredFormatter())
        root_logger.addHandler(console_handler)

    
    # File Handler - All Logs (rotating)
    all_logs_file = log_path / "app.log"
    file_handler = logging.handlers.RotatingFileHandler(
        all_logs_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    
    if json_output:
        file_handler.setFormatter(JSONFormatter())
    else:
        file_handler.setFormatter(
            logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        )
    root_logger.addHandler(file_handler)
    
    # Error Handler - Error Logs Only (rotating)
    error_logs_file = log_path / "error.log"
    error_handler = logging.handlers.RotatingFileHandler(
        error_logs_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    
    if json_output:
        error_handler.setFormatter(JSONFormatter())
    else:
        error_handler.setFormatter(
            logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s\n'
                'Exception: %(exc_info)s\n',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        )
    root_logger.addHandler(error_handler)
    
    # Performance Handler - Track slow operations
    perf_logs_file = log_path / "performance.log"
    perf_handler = logging.handlers.RotatingFileHandler(
        perf_logs_file,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    perf_handler.setLevel(logging.INFO)
    perf_handler.addFilter(lambda record: hasattr(record, 'execution_time'))
    
    if json_output:
        perf_handler.setFormatter(JSONFormatter())
    else:
        perf_handler.setFormatter(
            logging.Formatter(
                '%(asctime)s | %(name)s | %(funcName)s | Time: %(execution_time).3fs | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        )
    root_logger.addHandler(perf_handler)
    
    # Suppress overly verbose third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    
    root_logger.info("Logging system initialized")
    root_logger.info(f"📁 Log directory: {log_path.absolute()}")
    root_logger.info(f"Log level: {log_level}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


class LoggerMixin:
    """Mixin class to add logging capability to any class"""
    
    @property
    def logger(self) -> logging.Logger:
        """Get logger instance for this class"""
        if not hasattr(self, '_logger'):
            self._logger = logging.getLogger(self.__class__.__name__)
        return self._logger


# Context manager for tracking execution time
class LogExecutionTime:
    """Context manager to log execution time of code blocks"""
    
    def __init__(self, logger: logging.Logger, operation: str, log_level: int = logging.INFO):
        self.logger = logger
        self.operation = operation
        self.log_level = log_level
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.debug(f" Starting: {self.operation}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        execution_time = (datetime.now() - self.start_time).total_seconds()
        
        if exc_type is None:
            # Success
            self.logger.log(
                self.log_level,
                f"Completed: {self.operation}",
                extra={'execution_time': execution_time}
            )
        else:
            # Exception occurred
            self.logger.error(
                f"Failed: {self.operation}",
                exc_info=(exc_type, exc_val, exc_tb),
                extra={'execution_time': execution_time}
            )
        
        return False  # Don't suppress exceptions


# Decorator for logging function calls
def log_function_call(log_args: bool = False, log_result: bool = False):
    """
    Decorator to log function calls with execution time
    
    Args:
        log_args: Whether to log function arguments
        log_result: Whether to log function result
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger = logging.getLogger(func.__module__)
            func_name = f"{func.__module__}.{func.__name__}"
            
            # Log function call
            log_msg = f"🔧 Calling: {func_name}"
            if log_args:
                log_msg += f" | Args: {args}, Kwargs: {kwargs}"
            logger.debug(log_msg)
            
            start_time = datetime.now()
            
            try:
                result = func(*args, **kwargs)
                execution_time = (datetime.now() - start_time).total_seconds()
                
                log_msg = f"Completed: {func_name}"
                if log_result:
                    log_msg += f" | Result: {result}"
                
                logger.info(log_msg, extra={'execution_time': execution_time})
                
                return result
                
            except Exception as e:
                execution_time = (datetime.now() - start_time).total_seconds()
                logger.error(
                    f"Failed: {func_name} | Error: {str(e)}",
                    exc_info=True,
                    extra={'execution_time': execution_time}
                )
                raise
        
        return wrapper
    return decorator


if __name__ == "__main__":
    # Test logging setup
    setup_logging(log_level="DEBUG", json_output=False)
    
    logger = get_logger(__name__)
    
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    
    # Test execution time logging
    with LogExecutionTime(logger, "Test operation"):
        import time
        time.sleep(0.5)
    
    print("\nLogging test complete! Check logs/ directory")
