"""
Chat API Router
Handles user queries and integrates with LangGraph workflow
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import sqlite3
import json
import uuid
from datetime import datetime

from app.core.logging_config import get_logger
from app.workflows.graph import process_user_query
from .auth import get_current_user
from app.services.llm_service import get_llm_service, CloudLLMService
from app.services.cache_service import get_cache_service
from fastapi.responses import StreamingResponse


logger = get_logger(__name__)
router = APIRouter()


# Request/Response Models

class ChatRequest(BaseModel):
    """Chat request model"""
    query: str
    conversation_id: Optional[int] = None
    active_document_ids: Optional[List[int]] = None


class ChatResponse(BaseModel):
    """Chat response model"""
    success: bool
    intent: str
    response: Optional[str] = None
    answer: Optional[str] = None
    evaluation: Optional[Dict[str, Any]] = None
    questions: Optional[List[Dict[str, Any]]] = None
    processing_time: float
    metadata: Dict[str, Any]


class ConversationResponse(BaseModel):
    """Conversation history response"""
    conversation_id: int
    started_at: str
    last_message_at: str
    message_count: int


class RenameRequest(BaseModel):
    """Conversation rename request."""
    title: str


class ModelRequest(BaseModel):
    """LLM model selection request."""
    model: str



def get_db():
    """Get database connection"""
    conn = sqlite3.connect("./data/sqlite.db")
    conn.row_factory = sqlite3.Row
    return conn


def ensure_title_column():
    """Add title column to conversations if it doesn't exist"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT title FROM conversations LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE conversations ADD COLUMN title TEXT DEFAULT NULL")
        conn.commit()
    conn.close()
    conn.close()

# Migration runs inside lifespan now


def create_conversation(user_id: int, title: str = "New Chat") -> int:
    """Create a new conversation with a title"""
    conn = get_db()
    cursor = conn.cursor()
    
    session_id = str(uuid.uuid4())
    
    cursor.execute(
        """
        INSERT INTO conversations (user_id, session_id, title)
        VALUES (?, ?, ?)
        """,
        (user_id, session_id, title)
    )
    
    conn.commit()
    conversation_id = cursor.lastrowid
    conn.close()
    
    return conversation_id


def update_conversation_title(conversation_id: int, title: str):
    """Update a conversation's title"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE conversations SET title = ? WHERE id = ?",
        (title, conversation_id)
    )
    conn.commit()
    conn.close()


def save_message(
    conversation_id: int,
    role: str,
    content: str,
    intent: Optional[str] = None,
    metadata: Optional[Dict] = None
):
    """Save a message to conversation history"""
    conn = get_db()
    cursor = conn.cursor()
    
    metadata_json = json.dumps(metadata) if metadata else None
    
    cursor.execute(
        """
        INSERT INTO messages (conversation_id, role, content, intent, metadata)
        VALUES (?, ?, ?, ?, ?)
        """,
        (conversation_id, role, content, intent, metadata_json)
    )
    
    conn.commit()
    conn.close()


# API Endpoints

# --- Models cache (avoids hitting the provider on every request) ---
import time as _time
_models_cache: dict = {"models": None, "fetched_at": 0}
_MODELS_CACHE_TTL = 300  # 5 minutes


@router.get("/models")
async def list_models(
    current_user: dict = Depends(get_current_user),
    llm_service: CloudLLMService = Depends(get_llm_service)
):
    """List available models from the cloud LLM provider (cached for 5 min)."""
    global _models_cache
    
    def make_model_obj(model_id: str, available: bool = True) -> dict:
        """Build a rich model descriptor for the frontend."""
        label = model_id.replace("-", " ").replace("_", " ").replace(":", " ").title()
        return {
            "name": model_id,
            "label": label,
            "description": "Cloud LLM model",
            "available": available,
        }

    now = _time.time()
    
    # Return cached result if still fresh
    if _models_cache["models"] and (now - _models_cache["fetched_at"]) < _MODELS_CACHE_TTL:
        return {"models": _models_cache["models"], "active": llm_service.model}

    try:
        response = await llm_service.client.get(f"{llm_service.base_url}/models")
        if response.status_code == 200:
            data = response.json()
            raw_list = data.get("data", data.get("models", []))
            
            # Keywords for good, free, important open-source models often used with Ollama/Cloud
            allowed_keywords = [
                "llama3", "llama-3", "mistral", "mixtral", 
                "gemma", "qwen", "phi3", "phi-3", "gpt-oss", "deepseek"
            ]
            
            rich_models = []
            for m in raw_list:
                model_id = ""
                if isinstance(m, dict):
                    model_id = m.get("id") or m.get("name") or ""
                elif isinstance(m, str) and m:
                    model_id = m
                    
                if model_id:
                    model_lower = model_id.lower()
                    # Keep if it matches our allowed list, OR if it's the currently active model
                    if any(kw in model_lower for kw in allowed_keywords) or model_id == llm_service.model:
                        rich_models.append(make_model_obj(model_id))
            
            if rich_models:
                # Ensure active model is in the list
                for m in rich_models:
                    if m["name"] == llm_service.model:
                        break
                else:
                    rich_models.insert(0, make_model_obj(llm_service.model))
                
                # Cache the result
                _models_cache = {"models": rich_models, "fetched_at": now}
                return {"models": rich_models, "active": llm_service.model}

    except Exception as e:
        logger.warning(f"Failed to fetch models list from provider: {e}")

    # Fallback — return just the active model
    fallback = [make_model_obj(llm_service.model)]
    return {"models": fallback, "active": llm_service.model}


@router.post("/model")
async def set_model(
    request: ModelRequest,
    current_user: dict = Depends(get_current_user),
    llm_service: CloudLLMService = Depends(get_llm_service)
):
    """Switch the active LLM model for this session."""
    llm_service.model = request.model
    logger.info(f"Model changed to {request.model} by user {current_user['id']}")
    return {"status": "success", "active": llm_service.model}


@router.post("/query", response_model=ChatResponse)
async def process_query(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    llm_service: CloudLLMService = Depends(get_llm_service)
):
    """Process a user query through the AI workflow"""
    user_id = current_user["id"]
    query = request.query
    
    logger.info(f"Processing query | User: {user_id} | Query: '{query[:100]}...'")
    
    try:
        conversation_id = request.conversation_id
        if not conversation_id:
            title = query[:50].strip() + ("..." if len(query) > 50 else "")
            conversation_id = create_conversation(user_id, title=title)
        
        save_message(conversation_id=conversation_id, role="user", content=query)
        
        # Check semantic cache for instant response
        try:
            cache_service = get_cache_service()
            cached = cache_service.check_cache(query)
            if cached and cached.get("success"):
                logger.info(f"⚡ Semantic cache hit for query: '{query[:50]}...'")
                
                # Extract response content for saving
                response_content = ""
                if cached.get("response"):
                    response_content = cached["response"]
                elif cached.get("answer"):
                    response_content = cached["answer"]
                
                save_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=response_content,
                    intent=cached.get("intent", "cached"),
                    metadata={"source": "semantic_cache"}
                )
                
                cached["processing_time"] = 0.0
                cached["metadata"] = cached.get("metadata", {})
                cached["metadata"]["cached"] = True
                
                return ChatResponse(
                    success=True,
                    intent=cached.get("intent", "cached"),
                    response=cached.get("response"),
                    answer=cached.get("answer"),
                    evaluation=cached.get("evaluation"),
                    questions=cached.get("questions"),
                    processing_time=0.0,
                    metadata=cached.get("metadata", {})
                )
        except Exception as e:
            logger.debug(f"Cache check skipped: {e}")
        
        # Fetch History for Contextualization
        history_dicts = []
        if conversation_id:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT 10",
                (conversation_id,)
            )
            history_rows = cursor.fetchall()[::-1]
            conn.close()
            
            # Exclude current query if it happens to be saved already (though save_message is called just above)
            if history_rows and history_rows[-1][1] == query:
                history_rows = history_rows[:-1]
                
            history_dicts = [{"role": row[0], "content": row[1]} for row in history_rows]

        result = await process_user_query(
            user_id=user_id,
            query=query,
            conversation_id=conversation_id,
            active_document_ids=request.active_document_ids,
            conversation_history=history_dicts
        )
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("error", "Query processing failed"))
        
        response_content = ""
        if result.get("response"):
            response_content = result["response"]
        elif result.get("answer"):
            response_content = result["answer"]
        elif result.get("evaluation"):
            eval_result = result["evaluation"]
            response_content = f"Score: {eval_result['obtained_marks']}/{eval_result['total_marks']}\n\n{eval_result.get('feedback', '')}"
        
        save_message(
            conversation_id=conversation_id,
            role="assistant",
            content=response_content,
            intent=result["intent"],
            metadata=result.get("metadata", {})
        )
        
        # Cache the successful response for future similar queries
        try:
            cache_service = get_cache_service()
            cache_service.store_cache(
                query=query,
                response=result,
                intent=result.get("intent", "")
            )
        except Exception:
            pass  # Cache storage is best-effort
        
        return ChatResponse(
            success=True,
            intent=result["intent"],
            response=result.get("response"),
            answer=result.get("answer"),
            evaluation=result.get("evaluation"),
            questions=result.get("questions"),
            processing_time=result["processing_time"],
            metadata=result.get("metadata", {})
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query processing failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process query: {str(e)}")


@router.post("/stream")
async def stream_query(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
    llm_service: CloudLLMService = Depends(get_llm_service)
):
    """Stream a user query response using Server-Sent Events (SSE) with context"""
    user_id = current_user["id"]
    query = request.query
    conversation_id = request.conversation_id
    
    logger.info(f"🌊 Streaming query | User: {user_id} | Query: '{query[:50]}...'")
    
    # Create conversation if needed, title = first message
    is_new_conversation = False
    if not conversation_id:
        title = query[:50].strip() + ("..." if len(query) > 50 else "")
        conversation_id = create_conversation(user_id, title=title)
        is_new_conversation = True
    
    save_message(conversation_id=conversation_id, role="user", content=query)
    
    async def event_generator():
        try:
            yield f"data: {json.dumps({'type': 'status', 'message': 'Fetching history...'})}\n\n"

            # 1. Fetch History
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT 10",
                (conversation_id,)
            )
            history_rows = cursor.fetchall()[::-1]
            conn.close()
            
            messages = []
            
            yield f"data: {json.dumps({'type': 'status', 'message': 'Classifying intent...'})}\n\n"

            from app.nodes.document_retriever import DocumentRetriever, Intent
            from app.core.state import create_initial_state
            from app.nodes.intent_classifier import _intent_classifier
            
            # Exclude the CURRENT user message from history we pass to context rewriter
            # (it was saved just before this function ran, so it would be the last row)
            if history_rows and history_rows[-1][1] == query:
                context_history_rows = history_rows[:-1]
            else:
                context_history_rows = history_rows
                
            history_dicts = [{"role": row[0], "content": row[1]} for row in context_history_rows]

            state = create_initial_state(
                user_id=user_id, 
                query=query, 
                conversation_id=conversation_id,
                active_document_ids=request.active_document_ids,
                conversation_history=history_dicts
            )
            
            # 1.5 Classify Intent
            state = await _intent_classifier.classify(state)
            intent = state["intent"]
            
            yield f"data: {json.dumps({'type': 'status', 'message': 'Searching knowledge base...'})}\n\n"
            
            # 2. Retrieve Documents (RAG)
            
            retriever = DocumentRetriever()
            await retriever.retrieve(state)
            
            context = state.get("context", "")
            retrieved_docs = state.get("retrieved_documents", [])
            
            if retrieved_docs:
                yield f"data: {json.dumps({'type': 'info', 'message': f'Found {len(retrieved_docs)} relevant notes'})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'info', 'message': 'No documents found. Rejecting query.'})}\n\n"

            yield f"data: {json.dumps({'type': 'status', 'message': 'Thinking...'})}\n\n"
            
            # 3. Build System Prompt & Messages
            from app.core.prompts import (
                DOUBT_RESOLVER_SYSTEM,
                DOUBT_RESOLVER_GENERAL_SYSTEM,
                QUESTION_GEN_SYSTEM,
                ANSWER_GEN_SYSTEM,
                ANSWER_GEN_MARKING_SCHEME,
                ANSWER_GEN_NOTES_ONLY
            )
            
            if intent == Intent.QUESTION_GENERATION:
                system_prompt_text = QUESTION_GEN_SYSTEM
                if context:
                    final_query = f"The user has requested questions based on their uploaded notes. Generate questions exactly matching their request.\n\nUser Request: {query}\n\nNotes Context:\n{context}\n\nStrictly formulate the questions based on the notes above."
                    encoded_source = "notes"
                else:
                    final_query = f"The user has requested questions, but no documents were found. Respond by saying you can only generate questions based on uploaded study materials."
                    encoded_source = "rejected"
            elif intent == Intent.EXAM_PAPER_GENERATION:
                system_prompt_text = QUESTION_GEN_SYSTEM
                if context:
                    final_query = f"The user wants to generate a full exam paper. Create a complete exam paper with questions covering different topics and mark weightings.\n\nUser Request: {query}\n\nNotes Context:\n{context}\n\nGenerate a structured exam paper based on the notes above."
                    encoded_source = "notes"
                else:
                    final_query = f"No documents found. Inform the user that you need uploaded notes to generate an exam paper."
                    encoded_source = "rejected"
            elif intent in (Intent.ANSWER_GENERATION, Intent.ANSWER_EVALUATION):
                system_prompt_text = ANSWER_GEN_SYSTEM
                if context:
                    doc_types = state.get("document_types_available", [])
                    if "marking_scheme" in doc_types:
                        final_query = ANSWER_GEN_MARKING_SCHEME.format(question=query, context=context)
                    else:
                        final_query = ANSWER_GEN_NOTES_ONLY.format(question=query, context=context)
                    encoded_source = "notes"
                else:
                    final_query = f"The user has asked a question, but no documents were found. Respond by saying you can only generate answers based on uploaded study materials."
                    encoded_source = "rejected"
            else:  # DOUBT_CLARIFICATION or fallback
                if context:
                    system_prompt_text = DOUBT_RESOLVER_SYSTEM
                    final_query = f"Context information is below.\n---------------------\n{context}\n---------------------\nGiven the context information and not prior knowledge, answer the query.\nQuery: {query}"
                    encoded_source = "notes"
                else:
                    system_prompt_text = DOUBT_RESOLVER_GENERAL_SYSTEM
                    final_query = f"I'm sorry, I was unable to find relevant information in your uploaded documents to answer this question: \"{query}\". Please make sure you have uploaded the correct study materials, and check that they are active."
                    encoded_source = "rejected"

            messages.append({"role": "system", "content": system_prompt_text})
            
            # Add conversation history (exclude current message to avoid duplication)
            if history_rows and history_rows[-1][1] == query:
                history_rows = history_rows[:-1]
                
            for row in history_rows:
                messages.append({"role": row[0], "content": row[1]})
            
            messages.append({"role": "user", "content": final_query})
            
            # 4. Stream LLM Response
            full_response = ""
            async for chunk in llm_service.chat_stream(
                messages=messages,
                temperature=0.7,
                max_tokens=2500
            ):
                full_response += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            
            # 5. Save assistant message
            save_message(
                conversation_id=conversation_id,
                role="assistant",
                content=full_response,
                intent=intent.value,
                metadata={"source": encoded_source, "streamed": True}
            )
            
            # 6. Cache the response for future similar queries
            try:
                cache_svc = get_cache_service()
                cache_svc.store_cache(
                    query=query,
                    response={
                        "success": True,
                        "intent": intent.value,
                        "response": full_response,
                        "metadata": {"source": encoded_source, "streamed": True}
                    },
                    intent=intent.value
                )
            except Exception:
                pass  # Best-effort caching
            
            # Final event
            yield f"data: {json.dumps({'type': 'done', 'conversation_id': conversation_id})}\n\n"
            
        except Exception as e:
            logger.error(f"Streaming failed: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/conversations/{conversation_id}/summarize-title")
async def summarize_title(
    conversation_id: int,
    current_user: dict = Depends(get_current_user),
    llm_service: CloudLLMService = Depends(get_llm_service)
):
    """Use LLM to generate a better title for a conversation"""
    user_id = current_user["id"]
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Verify ownership
    cursor.execute("SELECT * FROM conversations WHERE id = ? AND user_id = ?", (conversation_id, user_id))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Get first few messages
    cursor.execute(
        "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id LIMIT 4",
        (conversation_id,)
    )
    msgs = cursor.fetchall()
    conn.close()
    
    if not msgs:
        return {"title": "New Chat"}
    
    convo_text = "\n".join([f"{m[0]}: {m[1][:100]}" for m in msgs])
    
    try:
        prompt = f"Summarize this conversation in 4-6 words as a title. Return ONLY the title, nothing else.\n\n{convo_text}"
        title = ""
        async for chunk in llm_service.generate_stream(prompt=prompt, temperature=0.3, max_tokens=20):
            title += chunk
        
        title = title.strip().strip('"').strip("'")[:60]
        if title:
            update_conversation_title(conversation_id, title)
            return {"title": title}
    except Exception as e:
        logger.warning(f"Title summarization failed: {e}")
    
    return {"title": "Chat"}


@router.get("/conversations")
async def list_conversations(current_user: dict = Depends(get_current_user)):
    """List user's conversations with titles"""
    user_id = current_user["id"]
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute(
        """
        SELECT 
            c.id,
            c.title,
            c.started_at,
            c.last_message_at,
            COUNT(m.id) as message_count
        FROM conversations c
        LEFT JOIN messages m ON c.id = m.conversation_id
        WHERE c.user_id = ?
        GROUP BY c.id
        ORDER BY c.last_message_at DESC
        LIMIT 50
        """,
        (user_id,)
    )
    
    conversations = []
    for row in cursor.fetchall():
        conversations.append({
            "conversation_id": row[0],
            "title": row[1] or "Untitled Chat",
            "started_at": row[2],
            "last_message_at": row[3],
            "message_count": row[4]
        })
    
    conn.close()
    
    return {"conversations": conversations}


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get conversation history"""
    user_id = current_user["id"]
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT * FROM conversations WHERE id = ? AND user_id = ?",
        (conversation_id, user_id)
    )
    
    conversation = cursor.fetchone()
    if not conversation:
        conn.close()
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    cursor.execute(
        """
        SELECT role, content, intent, timestamp
        FROM messages
        WHERE conversation_id = ?
        ORDER BY timestamp ASC
        """,
        (conversation_id,)
    )
    
    messages = []
    for row in cursor.fetchall():
        messages.append({
            "role": row[0],
            "content": row[1],
            "intent": row[2],
            "timestamp": row[3]
        })
    
    conn.close()
    
    return {
        "conversation_id": conversation_id,
        "messages": messages
    }


@router.patch("/conversations/{conversation_id}")
async def rename_conversation(
    conversation_id: int,
    request: RenameRequest,
    current_user: dict = Depends(get_current_user)
):
    """Rename a conversation"""
    user_id = current_user["id"]
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute(
        "UPDATE conversations SET title = ? WHERE id = ? AND user_id = ?",
        (request.title, conversation_id, user_id)
    )
    
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    conn.commit()
    conn.close()
    
    return {"message": "Renamed", "title": request.title}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Delete a conversation"""
    user_id = current_user["id"]
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute(
        "DELETE FROM conversations WHERE id = ? AND user_id = ?",
        (conversation_id, user_id)
    )
    
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    conn.commit()
    conn.close()
    
    logger.info(f"Conversation deleted | ID: {conversation_id}")
    
    return {"message": "Conversation deleted successfully", "conversation_id": conversation_id}


@router.get("/cache/stats")
async def cache_stats(current_user: dict = Depends(get_current_user)):
    """Get semantic cache statistics."""
    try:
        cache_service = get_cache_service()
        return cache_service.get_stats()
    except Exception as e:
        return {"error": str(e), "enabled": False}


@router.delete("/cache")
async def clear_cache(current_user: dict = Depends(get_current_user)):
    """Clear the semantic cache."""
    try:
        cache_service = get_cache_service()
        cache_service.clear_cache()
        return {"message": "Semantic cache cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")
