"""
Enhanced Configuration System
Provides validated, type-safe configuration with environment variable support
"""
from pydantic import (
    BaseModel,
    Field,
    validator,
    field_validator,
    model_validator
)
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
from pathlib import Path
import os
from enum import Enum

from .exceptions import MissingConfigException, InvalidConfigException


class Environment(str, Enum):
    """Application environment"""
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"


class LogLevel(str, Enum):
    """Logging levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    """
    Application settings with validation
    Automatically loads from environment variables and .env file
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    # ========================================================================
    # Application Settings
    # ========================================================================
    
    APP_NAME: str = Field(
        default="AI Educational Document Reasoning System",
        description="Application name"
    )
    
    APP_VERSION: str = Field(
        default="1.0.0",
        description="Application version"
    )
    
    ENVIRONMENT: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Application environment"
    )
    
    DEBUG: bool = Field(
        default=True,
        description="Enable debug mode"
    )
    
    HOST: str = Field(
        default="0.0.0.0",
        description="Server host"
    )
    
    PORT: int = Field(
        default=8000,
        ge=1024,
        le=65535,
        description="Server port"
    )
    
    # ========================================================================
    # Security Settings
    # ========================================================================
    
    SECRET_KEY: str = Field(
        default="change-this-secret-key-in-production",
        min_length=32,
        description="Secret key for JWT token generation"
    )
    
    ALGORITHM: str = Field(
        default="HS256",
        description="JWT algorithm"
    )
    
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        ge=5,
        le=1440,
        description="Access token expiration time in minutes"
    )
    
    # ========================================================================
    # Database Settings
    # ========================================================================
    
    DATABASE_URL: str = Field(
        default="sqlite:///./data/sqlite.db",
        description="Database connection URL"
    )
    
    DATABASE_POOL_SIZE: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Database connection pool size"
    )
    
    DATABASE_MAX_OVERFLOW: int = Field(
        default=10,
        ge=0,
        le=50,
        description="Maximum overflow connections"
    )
    
    # ========================================================================
    # Cloud LLM Settings (provider-agnostic, OpenAI-compatible)
    # Change LLM_BASE_URL, LLM_API_KEY, LLM_MODEL in .env to switch providers
    # ========================================================================
    
    LLM_BASE_URL: str = Field(
        default="https://ollama.com/v1",
        description="OpenAI-compatible API base URL (e.g. https://ollama.com/v1, https://api.openai.com/v1)"
    )
    
    LLM_API_KEY: str = Field(
        default="",
        description="API key for the cloud LLM provider"
    )
    
    LLM_MODEL: str = Field(
        default="gpt-oss:120b-cloud",
        description="Model name (e.g. gpt-oss:120b-cloud, gpt-4o, llama3)"
    )
    
    LLM_TEMPERATURE: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="LLM temperature for response generation"
    )
    
    LLM_TOP_P: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="LLM top_p sampling parameter"
    )
    
    LLM_MAX_TOKENS: int = Field(
        default=2048,
        ge=100,
        le=8192,
        description="Maximum tokens for LLM response"
    )
    
    LLM_TIMEOUT: int = Field(
        default=120,
        ge=30,
        le=600,
        description="LLM request timeout in seconds"
    )
    
    LLM_MAX_RETRIES: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retries for LLM requests"
    )
    
    # ========================================================================
    # Embedding Settings
    # ========================================================================
    
    EMBEDDING_MODEL: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="Sentence transformer model for embeddings"
    )
    
    EMBEDDING_DEVICE: str = Field(
        default="cuda",
        description="Device for embedding model (cuda or cpu)"
    )
    
    EMBEDDING_BATCH_SIZE: int = Field(
        default=32,
        ge=1,
        le=256,
        description="Batch size for embedding generation"
    )
    
    # ========================================================================
    # ChromaDB Settings
    # ========================================================================
    
    CHROMA_PERSIST_DIRECTORY: str = Field(
        default="./data/chroma_db",
        description="ChromaDB persistence directory"
    )
    
    CHROMA_COLLECTION_NAME: str = Field(
        default="educational_documents",
        description="ChromaDB collection name"
    )
    
    CHROMA_DISTANCE_METRIC: str = Field(
        default="cosine",
        description="Distance metric for similarity (cosine, l2, ip)"
    )
    
    # ========================================================================
    # Document Processing Settings
    # ========================================================================
    
    MAX_UPLOAD_SIZE_MB: int = Field(
        default=500,
        ge=1,
        le=1024,
        description="Maximum document upload size in MB"
    )
    
    CHUNK_SIZE: int = Field(
        default=1000,
        ge=100,
        le=5000,
        description="Document chunk size in characters"
    )
    
    CHUNK_OVERLAP: int = Field(
        default=200,
        ge=0,
        le=1000,
        description="Overlap between document chunks"
    )
    
    SUPPORTED_FORMATS: str = Field(
        default="pdf,docx,txt,pptx",
        description="Comma-separated list of supported file formats"
    )
    
    UPLOAD_DIRECTORY: str = Field(
        default="./data/uploads",
        description="Directory for uploaded documents"
    )
    
    # ========================================================================
    # Retrieval Settings
    # ========================================================================
    
    TOP_K_RETRIEVAL: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of top chunks to retrieve"
    )
    
    SIMILARITY_THRESHOLD: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score for retrieval"
    )
    
    # ========================================================================
    # CORS Settings
    # ========================================================================
    
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="Allowed CORS origins"
    )
    
    CORS_ALLOW_CREDENTIALS: bool = Field(
        default=True,
        description="Allow credentials in CORS requests"
    )
    
    # ========================================================================
    # Logging Settings
    # ========================================================================
    
    LOG_LEVEL: LogLevel = Field(
        default=LogLevel.INFO,
        description="Logging level"
    )
    
    LOG_FILE: str = Field(
        default="./logs/app.log",
        description="Log file path"
    )
    
    LOG_JSON_FORMAT: bool = Field(
        default=False,
        description="Use JSON format for logs"
    )
    
    LOG_ROTATION_SIZE_MB: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Log file rotation size in MB"
    )
    
    LOG_BACKUP_COUNT: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of log backup files to keep"
    )
    
    # ========================================================================
    # Rate Limiting
    # ========================================================================
    
    RATE_LIMIT_ENABLED: bool = Field(
        default=True,
        description="Enable rate limiting"
    )
    
    RATE_LIMIT_REQUESTS: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Number of requests allowed per window"
    )
    
    RATE_LIMIT_WINDOW_SECONDS: int = Field(
        default=60,
        ge=10,
        le=3600,
        description="Rate limit time window in seconds"
    )
    
    # ========================================================================
    # Performance Settings
    # ========================================================================
    
    MAX_CONCURRENT_REQUESTS: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum concurrent requests"
    )
    
    CACHE_ENABLED: bool = Field(
        default=True,
        description="Enable response caching"
    )
    
    CACHE_TTL_SECONDS: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="Cache time-to-live in seconds"
    )
    
    # ========================================================================
    # LangSmith Tracing Settings
    # ========================================================================
    
    LANGSMITH_TRACING: bool = Field(
        default=False,
        description="Enable LangSmith tracing"
    )
    
    LANGSMITH_API_KEY: Optional[str] = Field(
        default=None,
        description="LangSmith API key"
    )
    
    LANGSMITH_PROJECT: str = Field(
        default="rag-ai-application",
        description="LangSmith project name"
    )
    
    LANGSMITH_ENDPOINT: str = Field(
        default="https://api.smith.langchain.com",
        description="LangSmith API endpoint"
    )
    
    # ========================================================================
    # Cross-Encoder Re-ranking Settings
    # ========================================================================
    
    CROSS_ENCODER_MODEL: str = Field(
        default="cross-encoder/ms-marco-MiniLM-L-6-v2",
        description="Cross-encoder model for re-ranking retrieved documents"
    )
    
    CROSS_ENCODER_ENABLED: bool = Field(
        default=True,
        description="Enable cross-encoder re-ranking"
    )
    
    RERANK_OVERFETCH_MULTIPLIER: int = Field(
        default=3,
        ge=2,
        le=5,
        description="How many extra documents to fetch before re-ranking (multiplier)"
    )
    
    # ========================================================================
    # Semantic Cache Settings
    # ========================================================================
    
    SEMANTIC_CACHE_ENABLED: bool = Field(
        default=True,
        description="Enable semantic caching of query responses"
    )
    
    SEMANTIC_CACHE_COLLECTION: str = Field(
        default="rag_semantic_cache",
        description="ChromaDB collection name for semantic cache"
    )
    
    SEMANTIC_CACHE_THRESHOLD: float = Field(
        default=0.95,
        ge=0.80,
        le=1.0,
        description="Similarity threshold for cache hit (0.95 = 95% similar)"
    )
    
    SEMANTIC_CACHE_TTL_HOURS: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Cache entry time-to-live in hours"
    )
    
    # ========================================================================
    # Validators
    # ========================================================================
    
    @field_validator('SECRET_KEY')
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        """Validate secret key is strong enough"""
        if v == "change-this-secret-key-in-production" and os.getenv('ENVIRONMENT') == 'production':
            raise InvalidConfigException(
                "SECRET_KEY",
                v,
                "Default secret key cannot be used in production"
            )
        return v
    
    @field_validator('EMBEDDING_DEVICE')
    @classmethod
    def validate_embedding_device(cls, v: str) -> str:
        """Validate embedding device"""
        if v not in ['cuda', 'cpu', 'mps']:
            raise InvalidConfigException(
                "EMBEDDING_DEVICE",
                v,
                "Must be one of: cuda, cpu, mps"
            )
        return v
    
    @field_validator('CHROMA_DISTANCE_METRIC')
    @classmethod
    def validate_distance_metric(cls, v: str) -> str:
        """Validate ChromaDB distance metric"""
        if v not in ['cosine', 'l2', 'ip']:
            raise InvalidConfigException(
                "CHROMA_DISTANCE_METRIC",
                v,
                "Must be one of: cosine, l2, ip"
            )
        return v
    
    @field_validator('CHUNK_OVERLAP')
    @classmethod
    def validate_chunk_overlap(cls, v: int, info) -> int:
        """Validate chunk overlap is less than chunk size"""
        chunk_size = info.data.get('CHUNK_SIZE', 1000)
        if v >= chunk_size:
            raise InvalidConfigException(
                "CHUNK_OVERLAP",
                v,
                f"Overlap ({v}) must be less than chunk size ({chunk_size})"
            )
        return v
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported file formats"""
        return [fmt.strip() for fmt in self.SUPPORTED_FORMATS.split(',')]
    
    def get_max_upload_size_bytes(self) -> int:
        """Get maximum upload size in bytes"""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.ENVIRONMENT == Environment.PRODUCTION
    
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.ENVIRONMENT == Environment.DEVELOPMENT
    
    def configure_langsmith(self):
        """
        Configure LangSmith tracing by setting environment variables.
        Must be called before any LangChain/LangGraph imports or usage.
        """
        if self.LANGSMITH_TRACING and self.LANGSMITH_API_KEY:
            # New-style env vars (langsmith SDK)
            os.environ["LANGSMITH_TRACING"] = "true"
            os.environ["LANGSMITH_API_KEY"] = self.LANGSMITH_API_KEY
            os.environ["LANGSMITH_PROJECT"] = self.LANGSMITH_PROJECT
            os.environ["LANGSMITH_ENDPOINT"] = self.LANGSMITH_ENDPOINT
            # Legacy env vars (required by LangChain/LangGraph auto-tracing)
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_API_KEY"] = self.LANGSMITH_API_KEY
            os.environ["LANGCHAIN_PROJECT"] = self.LANGSMITH_PROJECT
            os.environ["LANGCHAIN_ENDPOINT"] = self.LANGSMITH_ENDPOINT
            print(f"LangSmith tracing enabled for project: {self.LANGSMITH_PROJECT}")
        else:
            os.environ["LANGSMITH_TRACING"] = "false"
            if not self.LANGSMITH_TRACING:
                print("LangSmith tracing is disabled")
            elif not self.LANGSMITH_API_KEY:
                print("LangSmith tracing disabled: no API key configured")


# Global settings instance
settings = Settings()


def ensure_directories():
    """
    Ensure all required directories exist
    Creates directories if they don't exist
    """
    directories = [
        "data",
        "data/uploads",
        "data/chroma_db",
        "logs"
    ]
    
    # Add custom directories from settings
    if settings.UPLOAD_DIRECTORY and settings.UPLOAD_DIRECTORY != "./data/uploads":
        directories.append(settings.UPLOAD_DIRECTORY)
    
    if settings.CHROMA_PERSIST_DIRECTORY and settings.CHROMA_PERSIST_DIRECTORY != "./data/chroma_db":
        directories.append(settings.CHROMA_PERSIST_DIRECTORY)
    
    log_dir = Path(settings.LOG_FILE).parent
    if str(log_dir) not in directories:
        directories.append(str(log_dir))
    
    for directory in directories:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
    
    return directories


def validate_configuration():
    """
    Validate configuration and check dependencies
    Raises exceptions if configuration is invalid
    """
    # Check if LLM API is reachable
    import httpx
    
    if not settings.LLM_API_KEY:
        print("⚠️  WARNING: LLM_API_KEY is not set in .env")
    
    try:
        headers = {}
        if settings.LLM_API_KEY:
            headers["Authorization"] = f"Bearer {settings.LLM_API_KEY}"
        
        response = httpx.get(
            f"{settings.LLM_BASE_URL}/models",
            headers=headers,
            timeout=10
        )
        if response.status_code not in (200, 401, 403):
            raise InvalidConfigException(
                "LLM_BASE_URL",
                settings.LLM_BASE_URL,
                f"LLM API not responding correctly (status {response.status_code})"
            )
        if response.status_code in (401, 403):
            print("⚠️  WARNING: LLM API key may be invalid (auth error)")
        else:
            print(f"✅ LLM API reachable at {settings.LLM_BASE_URL}")
    except httpx.ConnectError as e:
        print(f"⚠️  WARNING: Cannot connect to LLM API at {settings.LLM_BASE_URL}: {e}")
    except Exception as e:
        print(f"⚠️  WARNING: LLM API check failed: {str(e)}")
    
    # Validate embedding device
    if settings.EMBEDDING_DEVICE == "cuda":
        try:
            import torch
            if not torch.cuda.is_available():
                print("⚠️  WARNING: CUDA not available, falling back to CPU")
                settings.EMBEDDING_DEVICE = "cpu"
        except ImportError:
            print("⚠️  WARNING: PyTorch not installed, using CPU")
            settings.EMBEDDING_DEVICE = "cpu"
    
    print("Configuration validated successfully")


if __name__ == "__main__":
    print("🔧 Configuration Settings:")
    print(f"Environment: {settings.ENVIRONMENT}")
    print(f"Debug: {settings.DEBUG}")
    print(f"LLM Provider: {settings.LLM_BASE_URL}")
    print(f"LLM Model: {settings.LLM_MODEL}")
    print(f"LLM API Key: {'***' + settings.LLM_API_KEY[-8:] if settings.LLM_API_KEY else 'NOT SET'}")
    print(f"Embedding Device: {settings.EMBEDDING_DEVICE}")
    print(f"Database: {settings.DATABASE_URL}")
    print(f"Log Level: {settings.LOG_LEVEL}")
    
    print("\n📁 Creating directories...")
    dirs = ensure_directories()
    for d in dirs:
        print(f"  ✓ {d}")
    
    print("\nValidating configuration...")
    try:
        validate_configuration()
    except Exception as e:
        print(f"Validation failed: {e}")
