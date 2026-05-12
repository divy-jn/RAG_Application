"""
Custom Exception Hierarchy
Provides specific exceptions for different error scenarios with detailed context
"""
from typing import Optional, Dict, Any
from enum import Enum


class ErrorCode(str, Enum):
    """Standard error codes for the application"""
    
    # Authentication & Authorization
    AUTH_INVALID_CREDENTIALS = "AUTH_001"
    AUTH_TOKEN_EXPIRED = "AUTH_002"
    AUTH_TOKEN_INVALID = "AUTH_003"
    AUTH_INSUFFICIENT_PERMISSIONS = "AUTH_004"
    AUTH_USER_NOT_FOUND = "AUTH_005"
    AUTH_USER_ALREADY_EXISTS = "AUTH_006"
    
    # Document Processing
    DOC_UPLOAD_FAILED = "DOC_001"
    DOC_INVALID_FORMAT = "DOC_002"
    DOC_TOO_LARGE = "DOC_003"
    DOC_PARSING_FAILED = "DOC_004"
    DOC_NOT_FOUND = "DOC_005"
    DOC_PROCESSING_FAILED = "DOC_006"
    DOC_CHUNKING_FAILED = "DOC_007"
    
    # Vector Store
    VECTOR_STORE_CONNECTION_FAILED = "VEC_001"
    VECTOR_EMBEDDING_FAILED = "VEC_002"
    VECTOR_SEARCH_FAILED = "VEC_003"
    VECTOR_INSERT_FAILED = "VEC_004"
    VECTOR_DELETE_FAILED = "VEC_005"
    
    # LLM Service
    LLM_CONNECTION_FAILED = "LLM_001"
    LLM_MODEL_NOT_FOUND = "LLM_002"
    LLM_GENERATION_FAILED = "LLM_003"
    LLM_TIMEOUT = "LLM_004"
    LLM_RATE_LIMIT_EXCEEDED = "LLM_005"
    LLM_INVALID_RESPONSE = "LLM_006"
    
    # LangGraph Workflow
    WORKFLOW_INVALID_STATE = "WF_001"
    WORKFLOW_NODE_FAILED = "WF_002"
    WORKFLOW_ROUTING_FAILED = "WF_003"
    WORKFLOW_INTENT_UNKNOWN = "WF_004"
    WORKFLOW_MISSING_DOCUMENTS = "WF_005"
    
    # Database
    DB_CONNECTION_FAILED = "DB_001"
    DB_QUERY_FAILED = "DB_002"
    DB_RECORD_NOT_FOUND = "DB_003"
    DB_DUPLICATE_ENTRY = "DB_004"
    DB_INTEGRITY_ERROR = "DB_005"
    
    # Configuration
    CONFIG_MISSING = "CFG_001"
    CONFIG_INVALID = "CFG_002"
    
    # General
    INTERNAL_ERROR = "GEN_001"
    VALIDATION_ERROR = "GEN_002"
    NOT_IMPLEMENTED = "GEN_003"


class BaseAppException(Exception):
    """Base exception class for all application exceptions"""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        details: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.original_exception = original_exception
        
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses"""
        return {
            "error": True,
            "error_code": self.error_code.value,
            "message": self.message,
            "details": self.details,
            "type": self.__class__.__name__
        }
    
    def __str__(self) -> str:
        base_str = f"[{self.error_code.value}] {self.message}"
        if self.details:
            base_str += f" | Details: {self.details}"
        if self.original_exception:
            base_str += f" | Caused by: {str(self.original_exception)}"
        return base_str


# Authentication & Authorization Exceptions

class AuthenticationException(BaseAppException):
    """Base class for authentication-related exceptions"""
    pass


class InvalidCredentialsException(AuthenticationException):
    """Raised when user credentials are invalid"""
    
    def __init__(self, username: str):
        super().__init__(
            message=f"Invalid credentials for user: {username}",
            error_code=ErrorCode.AUTH_INVALID_CREDENTIALS,
            details={"username": username}
        )


class TokenExpiredException(AuthenticationException):
    """Raised when authentication token has expired"""
    
    def __init__(self):
        super().__init__(
            message="Authentication token has expired",
            error_code=ErrorCode.AUTH_TOKEN_EXPIRED
        )


class TokenInvalidException(AuthenticationException):
    """Raised when authentication token is invalid"""
    
    def __init__(self, reason: str = "Unknown"):
        super().__init__(
            message=f"Invalid authentication token: {reason}",
            error_code=ErrorCode.AUTH_TOKEN_INVALID,
            details={"reason": reason}
        )


class UserNotFoundException(AuthenticationException):
    """Raised when user is not found"""
    
    def __init__(self, identifier: str):
        super().__init__(
            message=f"User not found: {identifier}",
            error_code=ErrorCode.AUTH_USER_NOT_FOUND,
            details={"identifier": identifier}
        )


class UserAlreadyExistsException(AuthenticationException):
    """Raised when attempting to create a user that already exists"""
    
    def __init__(self, username: str, email: str):
        super().__init__(
            message=f"User already exists",
            error_code=ErrorCode.AUTH_USER_ALREADY_EXISTS,
            details={"username": username, "email": email}
        )


# Document Processing Exceptions

class DocumentException(BaseAppException):
    """Base class for document-related exceptions"""
    pass


class DocumentUploadException(DocumentException):
    """Raised when document upload fails"""
    
    def __init__(self, filename: str, reason: str, original_exception: Optional[Exception] = None):
        super().__init__(
            message=f"Failed to upload document: {filename}",
            error_code=ErrorCode.DOC_UPLOAD_FAILED,
            details={"filename": filename, "reason": reason},
            original_exception=original_exception
        )


class InvalidDocumentFormatException(DocumentException):
    """Raised when document format is not supported"""
    
    def __init__(self, filename: str, file_type: str, supported_types: list):
        super().__init__(
            message=f"Invalid document format: {file_type}",
            error_code=ErrorCode.DOC_INVALID_FORMAT,
            details={
                "filename": filename,
                "file_type": file_type,
                "supported_types": supported_types
            }
        )


class DocumentTooLargeException(DocumentException):
    """Raised when document exceeds size limit"""
    
    def __init__(self, filename: str, size_mb: float, max_size_mb: float):
        super().__init__(
            message=f"Document too large: {size_mb:.2f}MB (max: {max_size_mb}MB)",
            error_code=ErrorCode.DOC_TOO_LARGE,
            details={
                "filename": filename,
                "size_mb": size_mb,
                "max_size_mb": max_size_mb
            }
        )


class DocumentParsingException(DocumentException):
    """Raised when document parsing fails"""
    
    def __init__(self, filename: str, reason: str, original_exception: Optional[Exception] = None):
        super().__init__(
            message=f"Failed to parse document: {filename}",
            error_code=ErrorCode.DOC_PARSING_FAILED,
            details={"filename": filename, "reason": reason},
            original_exception=original_exception
        )


class DocumentNotFoundException(DocumentException):
    """Raised when document is not found"""
    
    def __init__(self, document_id: int):
        super().__init__(
            message=f"Document not found: {document_id}",
            error_code=ErrorCode.DOC_NOT_FOUND,
            details={"document_id": document_id}
        )


# Vector Store Exceptions

class VectorStoreException(BaseAppException):
    """Base class for vector store exceptions"""
    pass


class VectorStoreConnectionException(VectorStoreException):
    """Raised when connection to vector store fails"""
    
    def __init__(self, reason: str, original_exception: Optional[Exception] = None):
        super().__init__(
            message=f"Failed to connect to vector store: {reason}",
            error_code=ErrorCode.VECTOR_STORE_CONNECTION_FAILED,
            details={"reason": reason},
            original_exception=original_exception
        )


class VectorEmbeddingException(VectorStoreException):
    """Raised when vector embedding generation fails"""
    
    def __init__(self, text_sample: str, original_exception: Optional[Exception] = None):
        super().__init__(
            message="Failed to generate vector embeddings",
            error_code=ErrorCode.VECTOR_EMBEDDING_FAILED,
            details={"text_sample": text_sample[:100]},
            original_exception=original_exception
        )


class VectorSearchException(VectorStoreException):
    """Raised when vector search fails"""
    
    def __init__(self, query: str, original_exception: Optional[Exception] = None):
        super().__init__(
            message="Vector search failed",
            error_code=ErrorCode.VECTOR_SEARCH_FAILED,
            details={"query": query[:100]},
            original_exception=original_exception
        )


# LLM Service Exceptions

class LLMException(BaseAppException):
    """Base class for LLM-related exceptions"""
    pass


class LLMConnectionException(LLMException):
    """Raised when connection to LLM fails"""
    
    def __init__(self, url: str, original_exception: Optional[Exception] = None):
        super().__init__(
            message=f"Failed to connect to LLM at {url}",
            error_code=ErrorCode.LLM_CONNECTION_FAILED,
            details={"url": url},
            original_exception=original_exception
        )


class LLMModelNotFoundException(LLMException):
    """Raised when LLM model is not found"""
    
    def __init__(self, model_name: str):
        super().__init__(
            message=f"LLM model not found: {model_name}",
            error_code=ErrorCode.LLM_MODEL_NOT_FOUND,
            details={"model_name": model_name}
        )


class LLMGenerationException(LLMException):
    """Raised when LLM generation fails"""
    
    def __init__(self, prompt_sample: str, reason: str, original_exception: Optional[Exception] = None):
        super().__init__(
            message=f"LLM generation failed: {reason}",
            error_code=ErrorCode.LLM_GENERATION_FAILED,
            details={"prompt_sample": prompt_sample[:100], "reason": reason},
            original_exception=original_exception
        )


class LLMTimeoutException(LLMException):
    """Raised when LLM request times out"""
    
    def __init__(self, timeout_seconds: int):
        super().__init__(
            message=f"LLM request timed out after {timeout_seconds}s",
            error_code=ErrorCode.LLM_TIMEOUT,
            details={"timeout_seconds": timeout_seconds}
        )


class LLMRateLimitException(LLMException):
    """Raised when LLM rate limit is exceeded"""
    
    def __init__(self, retry_after: Optional[int] = None):
        super().__init__(
            message="LLM rate limit exceeded",
            error_code=ErrorCode.LLM_RATE_LIMIT_EXCEEDED,
            details={"retry_after": retry_after}
        )


# Workflow Exceptions

class WorkflowException(BaseAppException):
    """Base class for workflow exceptions"""
    pass


class InvalidWorkflowStateException(WorkflowException):
    """Raised when workflow state is invalid"""
    
    def __init__(self, reason: str, state_snapshot: Optional[Dict] = None):
        super().__init__(
            message=f"Invalid workflow state: {reason}",
            error_code=ErrorCode.WORKFLOW_INVALID_STATE,
            details={"reason": reason, "state": state_snapshot}
        )


class WorkflowNodeException(WorkflowException):
    """Raised when a workflow node fails"""
    
    def __init__(self, node_name: str, reason: str, original_exception: Optional[Exception] = None):
        super().__init__(
            message=f"Workflow node '{node_name}' failed: {reason}",
            error_code=ErrorCode.WORKFLOW_NODE_FAILED,
            details={"node_name": node_name, "reason": reason},
            original_exception=original_exception
        )


class UnknownIntentException(WorkflowException):
    """Raised when user intent cannot be determined"""
    
    def __init__(self, query: str):
        super().__init__(
            message="Could not determine user intent",
            error_code=ErrorCode.WORKFLOW_INTENT_UNKNOWN,
            details={"query": query[:200]}
        )


class MissingDocumentsException(WorkflowException):
    """Raised when required documents are not available"""
    
    def __init__(self, required_types: list, available_types: list):
        super().__init__(
            message="Required documents not available",
            error_code=ErrorCode.WORKFLOW_MISSING_DOCUMENTS,
            details={
                "required": required_types,
                "available": available_types,
                "missing": list(set(required_types) - set(available_types))
            }
        )


# Database Exceptions

class DatabaseException(BaseAppException):
    """Base class for database exceptions"""
    pass


class DatabaseConnectionException(DatabaseException):
    """Raised when database connection fails"""
    
    def __init__(self, reason: str, original_exception: Optional[Exception] = None):
        super().__init__(
            message=f"Database connection failed: {reason}",
            error_code=ErrorCode.DB_CONNECTION_FAILED,
            details={"reason": reason},
            original_exception=original_exception
        )


class DatabaseQueryException(DatabaseException):
    """Raised when database query fails"""
    
    def __init__(self, query: str, reason: str, original_exception: Optional[Exception] = None):
        super().__init__(
            message=f"Database query failed: {reason}",
            error_code=ErrorCode.DB_QUERY_FAILED,
            details={"query": query[:200], "reason": reason},
            original_exception=original_exception
        )


# Configuration Exceptions

class ConfigurationException(BaseAppException):
    """Base class for configuration exceptions"""
    pass


class MissingConfigException(ConfigurationException):
    """Raised when required configuration is missing"""
    
    def __init__(self, config_key: str):
        super().__init__(
            message=f"Missing required configuration: {config_key}",
            error_code=ErrorCode.CONFIG_MISSING,
            details={"config_key": config_key}
        )


class InvalidConfigException(ConfigurationException):
    """Raised when configuration value is invalid"""
    
    def __init__(self, config_key: str, value: Any, reason: str):
        super().__init__(
            message=f"Invalid configuration for {config_key}: {reason}",
            error_code=ErrorCode.CONFIG_INVALID,
            details={"config_key": config_key, "value": str(value), "reason": reason}
        )
