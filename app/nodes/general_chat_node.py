"""
General Chat Node
Handles greetings, app instructions, and casual conversation without doing heavy RAG
"""
from typing import Dict, Any
from app.core.state import GraphState

try:
    from langsmith import traceable
except ImportError:
    # Fallback: no-op decorator if langsmith not installed
    def traceable(**kwargs):
        def decorator(func):
            return func
        return decorator
        
from app.core.logging_config import get_logger, LogExecutionTime
from app.services.llm_service import get_llm_service
from app.core.exceptions import WorkflowNodeException
from app.core.prompts import GENERAL_CHAT_SYSTEM, GENERAL_CHAT_PROMPT


logger = get_logger(__name__)


class GeneralChatNode:
    """
    Handles general chat intents
    """
    
    def __init__(self):
        self.logger = logger
        
    async def generate(self, state: GraphState) -> GraphState:
        """
        Generate response for general chat
        
        Args:
            state: Current graph state
            
        Returns:
            Updated state
        """
        self.logger.info(
            f"Generating general chat response | "
            f"Query: '{state['query'][:50]}...'"
        )
        
        with LogExecutionTime(self.logger, "General chat generation"):
            try:
                llm = await get_llm_service()
                
                # Format history for prompt (last 4 interactions)
                history = state.get("conversation_history", [])
                history_text = "\n".join([f"{msg['role']}: {msg['content'][:200]}" for msg in history[-4:]])
                if not history_text:
                    history_text = "No previous conversation history."
                    
                # Fetch active document names
                active_doc_ids = state.get("active_document_ids", [])
                active_doc_names = "None"
                
                if active_doc_ids:
                    import sqlite3
                    from app.core.config import settings
                    try:
                        conn = sqlite3.connect(settings.DATABASE_URL.replace("sqlite:///", ""))
                        cursor = conn.cursor()
                        placeholders = ",".join("?" * len(active_doc_ids))
                        cursor.execute(f"SELECT original_filename FROM documents WHERE id IN ({placeholders})", tuple(active_doc_ids))
                        rows = cursor.fetchall()
                        conn.close()
                        names = [row[0] for row in rows]
                        active_doc_names = ", ".join(names)
                    except Exception as e:
                        self.logger.warning(f"Failed to fetch document names for context: {e}")
                
                # Format system prompt
                system_prompt = GENERAL_CHAT_SYSTEM.format(
                    active_documents=active_doc_names,
                    history=history_text
                )
                
                # Format user prompt
                prompt = GENERAL_CHAT_PROMPT.format(
                    query=state["query"]
                )
                
                # Generate response
                llm_response = await llm.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=0.6,
                    max_tokens=300
                )
                response = llm_response["generations"][0]["text"]
                
                # Update state
                state["final_response"] = response
                state["nodes_visited"].append("general_chat")
                
                self.logger.info("General chat response generated successfully")
                
                return state
                
            except Exception as e:
                self.logger.error(f"General chat generation failed: {str(e)}", exc_info=True)
                raise WorkflowNodeException(
                    node_name="general_chat",
                    reason=str(e),
                    original_exception=e
                )


# Global instance
_general_chat_node = GeneralChatNode()


@traceable(name="node_general_chat", run_type="chain")
async def general_chat_node(state: GraphState) -> GraphState:
    """
    LangGraph node function for general chat
    """
    return await _general_chat_node.generate(state)
