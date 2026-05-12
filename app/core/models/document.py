from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum

class DocumentProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class DocumentBase(BaseModel):
    filename: str
    document_type: str
    subject: Optional[str] = None
    topic: Optional[str] = None
    visibility: str = "private"

class DocumentCreate(DocumentBase):
    pass

class DocumentResponse(DocumentBase):
    id: int
    user_id: int
    file_type: str
    file_size: int
    upload_date: Optional[str] = None  # SQLite usually stores dates as strings
    is_processed: bool
    chunk_count: int
    
    class Config:
        from_attributes = True

class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int
