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
    "general_chat",
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
        return "general_chat"
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
    
    # New for Phase 4: Route to retrieval grader first
    return "grade_retrieval"


def route_after_grading(state: GraphState) -> Literal[
    "generate_answer",
    "evaluate_answer",
    "resolve_doubt",
    "generate_questions",
    "rewrite_query"
]:
    """Decide whether to proceed with generation or rewrite the query."""
    is_relevant = state.get("is_relevant", False)
    loop_count = state.get("run_loop_count", 0)
    intent = state.get("intent", Intent.DOUBT_CLARIFICATION)
    
    if not is_relevant and loop_count < 2:
        logger.info(f"Context irrelevant, routing to rewrite_query (Loop {loop_count})")
        return "rewrite_query"
    
    logger.info(f"Proceeding to task node: {intent.value}")
    if intent == Intent.ANSWER_GENERATION:
        return "generate_answer"
    elif intent == Intent.ANSWER_EVALUATION:
        return "evaluate_answer"
    elif intent == Intent.DOUBT_CLARIFICATION:
        return "resolve_doubt"
    elif intent == Intent.QUESTION_GENERATION:
        return "generate_questions"
    else:
        return "resolve_doubt"


def route_after_reflection(state: GraphState) -> Literal[
    "generate_answer",
    "resolve_doubt",
    "end"
]:
    """Decide whether to regenerate the answer or end."""
    is_hallucination = state.get("is_hallucination", False)
    loop_count = state.get("run_loop_count", 0)
    intent = state.get("intent", Intent.DOUBT_CLARIFICATION)
    
    if is_hallucination and loop_count < 3:
        logger.warning(f"Hallucination detected, routing back to regenerate (Loop {loop_count})")
        if intent == Intent.ANSWER_GENERATION:
            return "generate_answer"
        else:
            return "resolve_doubt"
            
    return "end"


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

