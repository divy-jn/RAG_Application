from typing import TypedDict, List, Dict, Any, Optional
from enum import Enum

class Intent(str, Enum):
    ANSWER_GENERATION = "answer_generation"
    ANSWER_EVALUATION = "answer_evaluation"
    DOUBT_CLARIFICATION = "doubt_clarification"
    QUESTION_GENERATION = "question_generation"
    EXAM_PAPER_GENERATION = "exam_paper_generation"
    GENERAL_CHAT = "general_chat"

class ProcessingStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class RetrievedDocument(TypedDict):
    document_id: int
    document_type: str
    chunk_text: str
    similarity_score: float
    metadata: Dict[str, Any]

class GraphState(TypedDict, total=False):
    # User / Session Info
    user_id: int
    conversation_id: Optional[int]
    status: ProcessingStatus
    conversation_history: List[Dict[str, str]]
    
    # Selected Knowledge Base
    active_document_ids: List[int]
    
    # Input
    query: str
    
    # Intent Analysis
    intent: Intent
    intent_confidence: float
    
    # Retrieval
    retrieval_query: str
    retrieved_documents: List[RetrievedDocument]
    document_types_available: List[str]  # e.g., ["notes", "marking_scheme"]
    context: str
    
    # Task specific data
    task_data: Dict[str, Any]
    
    # Outputs
    generated_answer: str
    evaluation_result: Dict[str, Any]
    generated_questions: List[Dict[str, Any]]
    final_response: str
    
    # Metadata
    nodes_visited: List[str]
    processing_time: float
    error_message: str

def create_initial_state(user_id: int, query: str, conversation_id: int = None, active_document_ids: List[int] = None, conversation_history: List[Dict[str, str]] = None) -> GraphState:
    return {
        "user_id": user_id,
        "query": query,
        "conversation_id": conversation_id,
        "conversation_history": conversation_history or [],
        "active_document_ids": active_document_ids or [],
        "nodes_visited": [],
        "task_data": {},
        "retrieved_documents": [],
        "document_types_available": []
    }
