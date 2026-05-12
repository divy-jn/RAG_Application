"""
Documents API Router
Handles document upload, processing, and management
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import List, Optional
import sqlite3
import shutil
from pathlib import Path
import uuid

from app.core.logging_config import get_logger, LogExecutionTime
from app.core.config import settings
from app.core.models.document import DocumentResponse, DocumentListResponse, DocumentProcessingStatus
from fastapi import BackgroundTasks
from app.api.auth import get_current_user
from app.services.document_processor import get_document_processor, DocumentProcessor
from app.services.vector_store_service import get_vector_store, VectorStoreService
from app.core.exceptions import (
    DocumentUploadException,
    InvalidDocumentFormatException,
    DocumentTooLargeException
)


logger = get_logger(__name__)
router = APIRouter()


# Helper Functions

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(settings.DATABASE_URL.replace("sqlite:///", ""))
    conn.row_factory = sqlite3.Row
    return conn


async def save_upload_file(upload_file: UploadFile, user_id: int) -> Path:
    """
    Save uploaded file to disk
    
    Args:
        upload_file: Uploaded file
        user_id: User ID
        
    Returns:
        Path to saved file
    """
    # Create user directory
    user_dir = Path(settings.UPLOAD_DIRECTORY) / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    file_ext = Path(upload_file.filename).suffix
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = user_dir / unique_filename
    
    # Save file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
    
    return file_path


def _save_document_metadata(
    filename: str,
    file_path: str,
    file_type: str,
    file_size: int,
    subject: Optional[str],
    topic: Optional[str],
    visibility: str,
    user_id: int
) -> int:
    """Save document metadata to database"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute(
        """
        INSERT INTO documents 
        (user_id, filename, original_filename, file_path, file_type, 
         document_type, subject, topic, visibility, file_size, is_processed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """,
        (
            user_id,
            filename,
            filename,
            file_path,
            file_type,
            "uploaded",  # Default type, will be updated if needed or ignore
            subject,
            topic,
            visibility,
            file_size
        )
    )
    
    conn.commit()
    document_id = cursor.lastrowid
    conn.close()
    return document_id


def _update_document_processing_status(
    document_id: int,
    is_processed: bool,
    chunk_count: int = 0
):
    """Update document processing status"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute(
        """
        UPDATE documents 
        SET is_processed = ?, chunk_count = ?
        WHERE id = ?
        """,
        (1 if is_processed else 0, chunk_count, document_id)
    )
    
    conn.commit()
    conn.close()


# API Endpoints

@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form(...),
    subject: str = Form(None),
    topic: str = Form(None),
    visibility: str = Form("private"),
    current_user: dict = Depends(get_current_user),
    doc_processor: DocumentProcessor = Depends(get_document_processor),
    vector_store: VectorStoreService = Depends(get_vector_store)
):
    """
    Upload and process a document
    
    Args:
        file: Document file to upload
        document_type: Type (notes, marking_scheme, question_paper)
        subject: Subject name
        topic: Topic name
        visibility: Document visibility (private/public)
        current_user: Current authenticated user
        
    Returns:
        Document information
    """
    user_id = current_user["id"]
    
    logger.info(
        f"Document upload | "
        f"User: {user_id} | "
        f"File: {file.filename} | "
        f"Type: {document_type}"
    )

    
    try:
        # Validate file type
        file_ext = Path(file.filename).suffix.lstrip('.').lower()
        if file_ext not in settings.get_supported_formats():
            raise InvalidDocumentFormatException(
                filename=file.filename,
                file_type=file_ext,
                supported_types=settings.get_supported_formats()
            )
        
        # Check file size
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning
        
        file_size_mb = file_size / (1024 * 1024)
        if file_size_mb > settings.MAX_UPLOAD_SIZE_MB:
            raise DocumentTooLargeException(
                filename=file.filename,
                size_mb=file_size_mb,
                max_size_mb=settings.MAX_UPLOAD_SIZE_MB
            )
        
        # Save file
        file_path = await save_upload_file(file, user_id)
        
        # Save to database first
        document_id = _save_document_metadata(
            filename=file.filename,
            file_path=str(file_path),
            file_type=file_ext,
            file_size=file_size,
            subject=subject,
            topic=topic,
            visibility=visibility,
            user_id=current_user["id"]
        )
        
        logger.info(f"Document metadata saved | ID: {document_id}")
        
        # Process document
        with LogExecutionTime(logger, f"Document processing: {document_id}"):
            processed_doc = doc_processor.process_file(
                file_path=str(file_path),
                document_metadata={
                    "document_id": document_id,
                    "user_id": current_user["id"],
                    "document_type": document_type,
                    "subject": subject,
                    "topic": topic,
                    "visibility": visibility,
                    "original_filename": file.filename
                }
            )
            
            # Add to vector store
            chunk_texts = [chunk.text for chunk in processed_doc.chunks]
            chunk_metadatas = [chunk.metadata for chunk in processed_doc.chunks]
            chunk_ids = [f"{document_id}_{chunk.chunk_index}" for chunk in processed_doc.chunks]
            
            vector_store.add_documents(
                documents=chunk_texts,
                metadatas=chunk_metadatas,
                ids=chunk_ids
            )
            
            _update_document_processing_status(document_id, True, len(processed_doc.chunks))
            logger.info(
                f"Document processed and indexed | "
                f"ID: {document_id} | "
                f"Chunks: {len(processed_doc.chunks)}"
            )
        
        # Fetch created document
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE id = ?", (document_id,))
        doc = dict(cursor.fetchone())
        conn.close()
        
        return DocumentResponse(**doc)
        
    except (InvalidDocumentFormatException, DocumentTooLargeException):
        raise
    except Exception as e:
        logger.error(f"Document upload failed: {str(e)}", exc_info=True)
        raise DocumentUploadException(
            filename=file.filename,
            reason=str(e),
            original_exception=e
        )


async def process_document_internal(document_id: int, file_path: str, user_id: int):
    """
    Process document and store in vector database
    
    Args:
        document_id: Document ID
        file_path: Path to document file
        user_id: User ID
    """
    logger.info(f"Processing document | ID: {document_id}")
    
    with LogExecutionTime(logger, f"Document processing: {document_id}"):
        try:
            # Get document info from database
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM documents WHERE id = ?", (document_id,))
            doc = dict(cursor.fetchone())
            conn.close()
            
            # Process document
            processor = get_document_processor()
            parsed_doc = processor.process_file(
                file_path=file_path,
                document_metadata={
                    "document_id": document_id,
                    "user_id": user_id,
                    "document_type": doc["document_type"],
                    "subject": doc["subject"],
                    "topic": doc["topic"],
                    "visibility": doc["visibility"]
                }
            )
            
            # Store chunks in vector database
            vector_store = get_vector_store()
            
            chunk_texts = [chunk.text for chunk in parsed_doc.chunks]
            chunk_metadatas = [chunk.metadata for chunk in parsed_doc.chunks]
            chunk_ids = [f"{document_id}_{chunk.chunk_index}" for chunk in parsed_doc.chunks]
            
            vector_store.add_documents(
                documents=chunk_texts,
                metadatas=chunk_metadatas,
                ids=chunk_ids
            )
            
            # Update document status in database
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE documents 
                SET is_processed = 1, chunk_count = ?
                WHERE id = ?
                """,
                (len(parsed_doc.chunks), document_id)
            )
            conn.commit()
            conn.close()
            
            logger.info(
                f"Document processed | "
                f"ID: {document_id} | "
                f"Chunks: {len(parsed_doc.chunks)}"
            )
            
        except Exception as e:
            logger.error(f"Document processing failed: {str(e)}", exc_info=True)
            
            # Update document status as failed
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE documents SET is_processed = 0 WHERE id = ?",
                (document_id,)
            )
            conn.commit()
            conn.close()


@router.get("/list", response_model=DocumentListResponse)
async def list_documents(
    document_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    List user's documents
    
    Args:
        document_type: Filter by document type
        current_user: Current authenticated user
        
    Returns:
        List of documents
    """
    user_id = current_user["id"]
    
    conn = get_db()
    cursor = conn.cursor()
    
    if document_type:
        cursor.execute(
            """
            SELECT * FROM documents 
            WHERE user_id = ? AND document_type = ?
            ORDER BY upload_date DESC
            """,
            (user_id, document_type)
        )
    else:
        cursor.execute(
            """
            SELECT * FROM documents 
            WHERE user_id = ?
            ORDER BY upload_date DESC
            """,
            (user_id,)
        )
    
    documents = [DocumentResponse(**dict(row)) for row in cursor.fetchall()]
    conn.close()
    
    return DocumentListResponse(
        documents=documents,
        total=len(documents)
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Get document details
    
    Args:
        document_id: Document ID
        current_user: Current authenticated user
        
    Returns:
        Document information
    """
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT * FROM documents WHERE id = ? AND user_id = ?",
        (document_id, current_user["id"])
    )
    
    doc = cursor.fetchone()
    conn.close()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return DocumentResponse(**dict(doc))


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a document
    
    Args:
        document_id: Document ID
        current_user: Current authenticated user
        
    Returns:
        Success message
    """
    user_id = current_user["id"]
    
    # Get document
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM documents WHERE id = ? AND user_id = ?",
        (document_id, user_id)
    )
    doc = cursor.fetchone()
    
    if not doc:
        conn.close()
        raise HTTPException(status_code=404, detail="Document not found")
    
    doc = dict(doc)
    
    # Delete file
    try:
        file_path = Path(doc["file_path"])
        if file_path.exists():
            file_path.unlink()
    except Exception as e:
        logger.warning(f"Failed to delete file: {e}")
    
    # Delete from vector store
    try:
        vector_store = get_vector_store()
        chunk_count = doc["chunk_count"]
        chunk_ids = [f"{document_id}_{i}" for i in range(chunk_count)]
        vector_store.delete_documents(chunk_ids)
    except Exception as e:
        logger.warning(f"Failed to delete from vector store: {e}")
    
    # Delete from database
    cursor.execute("DELETE FROM documents WHERE id = ?", (document_id,))
    conn.commit()
    conn.close()
    
    logger.info(f"Document deleted | ID: {document_id}")
    
    return {
        "message": "Document deleted successfully",
        "document_id": document_id
    }


if __name__ == "__main__":
    print("Documents API Router")
