"""
Application entry point and FastAPI server configuration.
Defines middleware, exception handlers, health checks, and route registration.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional, List
from contextlib import asynccontextmanager
from pathlib import Path
import uvicorn


from app.core.logging_config import setup_logging, get_logger
from app.core.config import settings, ensure_directories
from app.core.health_check import get_system_health
from app.core.exceptions import BaseAppException

from app.services.llm_service import get_llm_service, close_llm_service


logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    logger.info("Starting AI Educational System...")
    
    # Setup logging
    setup_logging(
        log_level=settings.LOG_LEVEL.value,
        json_output=settings.LOG_JSON_FORMAT
    )
    
    # Ensure directories exist
    ensure_directories()
    
    # Initialize SQLite Database if missing
    try:
        import sqlite3
        db_path = settings.DATABASE_URL.replace("sqlite:///", "")
        with sqlite3.connect(db_path) as conn:
            with open("database_schema.sql", "r") as f:
                conn.executescript(f.read())
            from app.api.chat import ensure_title_column
            ensure_title_column()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
    
    # Configure LangSmith tracing (before any LangChain/LangGraph usage)
    settings.configure_langsmith()
    
    # Initialize services
    try:
        llm = await get_llm_service()
        logger.info(f"☁️ Cloud LLM initialized | Model: {settings.LLM_MODEL} | Provider: {settings.LLM_BASE_URL}")
    except Exception as e:
        logger.warning(f"Cloud LLM init check failed (will retry on first request): {e}")
    
    logger.info("Application started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down AI Educational System...")
    await close_llm_service()
    logger.info("Application shutdown complete")


# Initialize FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI Study Assistant API",
    lifespan=lifespan
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)


@app.exception_handler(BaseAppException)
async def custom_exception_handler(request, exc: BaseAppException):
    """Handle application-specific exceptions with structured error responses."""
    logger.error(
        f"Application error: {exc.error_code.value} | {exc.message}",
        extra={"error_details": exc.details}
    )
    
    return JSONResponse(
        status_code=400,
        content=exc.to_dict()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """Catch-all handler for unexpected server errors."""
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": "An unexpected error occurred",
            "type": type(exc).__name__
        }
    )


@app.get("/")
async def root():
    """Redirect to frontend application."""
    return RedirectResponse(url="/app")


@app.get("/api/status")
async def get_status():
    """Service metadata and status."""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Detailed health check including database, LLM, and vector store status."""
    health_status = await get_system_health()
    
    # Determine HTTP status code based on health
    if health_status["overall_status"] == "healthy":
        status_code = 200
    elif health_status["overall_status"] == "degraded":
        status_code = 200  # Still operational
    else:
        status_code = 503  # Service unavailable
    
    return JSONResponse(
        status_code=status_code,
        content=health_status
    )


@app.get("/health/simple")
async def simple_health():
    """Lightweight liveness probe."""
    return {"status": "ok"}


# Import API Routers

from app.api.auth import router as auth_router
from app.api.documents import router as documents_router
from app.api.chat import router as chat_router

# Register routers
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(documents_router, prefix="/api/documents", tags=["Documents"])
app.include_router(chat_router, prefix="/api/chat", tags=["Chat"])


@app.get("/api/stats")
async def get_stats():
    """Retrieve vector store and embedding service statistics."""
    from app.services.vector_store_service import get_vector_store
    from app.services.embedding_service import get_embedding_service
    
    vector_store = get_vector_store()
    embedding_service = get_embedding_service()
    
    return {
        "vector_store": vector_store.get_stats(),
        "embedding_service": embedding_service.get_stats()
    }


# Static Frontend

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

@app.get("/app")
async def serve_frontend():
    """Serve the frontend application"""
    return FileResponse(STATIC_DIR / "index.html")

# Mount static files AFTER all API routes
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# Development Server

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.value.lower()
    )
