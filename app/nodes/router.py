"""
Workflow Router
Determines which node to execute next based on intent and state
"""
from typing import Literal
from app.core.state import GraphState, Intent

from app.core.logging_config import get_logger


logger = get_logger(__name__)


def route_after_intent(state: GraphState) -> Literal[
    "retrieve_documents",
    "generate_answer",
    "evaluate_answer", 
    "resolve_doubt",
    "generate_questions",
    "end"
]:
    """
    Route to appropriate node after intent classification
    
    Args:
        state: Current graph state
        
    Returns:
        Next node name
    """
    intent = state.get("intent", Intent.DOUBT_CLARIFICATION)
    
    logger.info(f"Routing based on intent: {intent.value}")
    
    # All intents need document retrieval first (except general chat)
    if intent == Intent.GENERAL_CHAT:
        return "end"
    else:
        return "retrieve_documents"


def route_after_retrieval(state: GraphState) -> Literal[
    "generate_answer",
    "evaluate_answer",
    "resolve_doubt",
    "generate_questions",
    "end"
]:
    """
    Route to task-specific node after document retrieval
    
    Args:
        state: Current graph state
        
    Returns:
        Next node name
    """
    intent = state.get("intent", Intent.DOUBT_CLARIFICATION)
    
    logger.info(f"Routing to task node: {intent.value}")
    
    # Route based on intent
    if intent == Intent.ANSWER_GENERATION:
        return "generate_answer"
    elif intent == Intent.ANSWER_EVALUATION:
        return "evaluate_answer"
    elif intent == Intent.DOUBT_CLARIFICATION:
        return "resolve_doubt"
    elif intent == Intent.QUESTION_GENERATION:
        return "generate_questions"
    else:
        # Default to doubt resolution
        return "resolve_doubt"


def should_continue(state: GraphState) -> Literal["end", "continue"]:
    """
    Determine if workflow should continue or end
    
    Args:
        state: Current graph state
        
    Returns:
        "end" or "continue"
    """
    # Check if we have a final response
    if state.get("final_response") or state.get("generated_answer") or state.get("evaluation_result"):
        return "end"
    
    # Check for errors
    if state.get("error_message"):
        return "end"
    
    return "continue"

