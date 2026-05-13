"""
General Chat Node
Handles greetings, app instructions, and casual conversation without doing heavy RAG
"""
from typing import Dict, Any
from app.core.state import GraphState

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
                
                # Format prompt
                prompt = GENERAL_CHAT_PROMPT.format(
                    query=state["query"]
                )
                
                # Generate response
                response = await llm.generate(
                    prompt=prompt,
                    system_prompt=GENERAL_CHAT_SYSTEM,
                    temperature=0.6,
                    max_tokens=300
                )
                
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


async def general_chat_node(state: GraphState) -> GraphState:
    """
    LangGraph node function for general chat
    """
    return await _general_chat_node.generate(state)
