"""
LangGraph workflow orchestration.
Builds and executes the stateful AI pipeline from intent classification through response generation.
"""
from langgraph.graph import StateGraph, END
from typing import Dict, Any, List
import time

try:
    from langsmith import traceable
except ImportError:
    # Fallback: no-op decorator if langsmith not installed
    def traceable(**kwargs):
        def decorator(func):
            return func
        return decorator

from app.core.state import GraphState, create_initial_state, ProcessingStatus
from app.core.logging_config import get_logger, LogExecutionTime

from app.nodes.intent_classifier import classify_intent_node
from app.nodes.document_retriever import retrieve_documents_node
from app.nodes.answer_generator import generate_answer_node
from app.nodes.answer_evaluator import evaluate_answer_node
from app.nodes.doubt_resolver import resolve_doubt_node

from app.nodes.question_generator import generate_questions_node
from app.nodes.general_chat_node import general_chat_node
from app.nodes.retrieval_grader import grade_retrieval_node
from app.nodes.hallucination_grader import hallucination_grader_node
from app.nodes.query_rewriter import rewrite_query_node

from app.nodes.router import (
    route_after_intent, 
    route_after_retrieval,
    route_after_grading,
    route_after_reflection
)


logger = get_logger(__name__)


from app.nodes.cache_lookup import CacheLookupNode

# Instantiate cache node
cache_lookup_node_inst = CacheLookupNode()

def route_after_cache(state: GraphState) -> str:
    """Route after cache check."""
    if state.get("final_response"):
        return "end"
    return "classify_intent"

class WorkflowOrchestrator:
    """Orchestrates the LangGraph pipeline for processing user queries."""
    
    def __init__(self):
        self.logger = logger
        self.graph = self._build_graph()
        self.logger.info("LangGraph workflow initialized")
    
    def _build_graph(self) -> StateGraph:
        """Construct the state graph with nodes and conditional routing edges."""
        self.logger.info("Building workflow graph...")
        
        # Initialize graph
        workflow = StateGraph(GraphState)
        
        # Add all nodes
        workflow.add_node("cache_lookup", cache_lookup_node_inst.process)
        workflow.add_node("classify_intent", classify_intent_node)
        workflow.add_node("retrieve_documents", retrieve_documents_node)
        workflow.add_node("generate_answer", generate_answer_node)
        workflow.add_node("evaluate_answer", evaluate_answer_node)
        workflow.add_node("resolve_doubt", resolve_doubt_node)
        workflow.add_node("generate_questions", generate_questions_node)
        workflow.add_node("general_chat", general_chat_node)
        workflow.add_node("grade_retrieval", grade_retrieval_node)
        workflow.add_node("grade_hallucination", hallucination_grader_node)
        workflow.add_node("rewrite_query", rewrite_query_node)
        
        # Set entry point
        workflow.set_entry_point("cache_lookup")
        
        # Add conditional edges
        workflow.add_conditional_edges(
            "cache_lookup",
            route_after_cache,
            {
                "classify_intent": "classify_intent",
                "end": END
            }
        )
        
        workflow.add_conditional_edges(
            "classify_intent",
            route_after_intent,
            {
                "retrieve_documents": "retrieve_documents",
                "general_chat": "general_chat",
                "end": END
            }
        )
        
        workflow.add_conditional_edges(
            "retrieve_documents",
            route_after_retrieval,
            {
                "grade_retrieval": "grade_retrieval",
                "end": END
            }
        )
        
        workflow.add_conditional_edges(
            "grade_retrieval",
            route_after_grading,
            {
                "generate_answer": "generate_answer",
                "evaluate_answer": "evaluate_answer",
                "resolve_doubt": "resolve_doubt",
                "generate_questions": "generate_questions",
                "rewrite_query": "rewrite_query"
            }
        )
        
        workflow.add_edge("rewrite_query", "retrieve_documents")
        
        workflow.add_conditional_edges(
            "generate_answer",
            route_after_reflection,
            {
                "generate_answer": "generate_answer",
                "end": END
            }
        )
        
        workflow.add_conditional_edges(
            "resolve_doubt",
            route_after_reflection,
            {
                "resolve_doubt": "resolve_doubt",
                "end": END
            }
        )
        
        # Nodes that end directly
        workflow.add_edge("evaluate_answer", END)
        workflow.add_edge("generate_questions", END)
        workflow.add_edge("general_chat", END)
        
        # Compile graph
        compiled_graph = workflow.compile()
        
        self.logger.info("Workflow graph built successfully")
        
        return compiled_graph
    
    @traceable(name="workflow_process_query", run_type="chain")
    async def process_query(
        self,
        user_id: int,
        query: str,
        conversation_id: int = None,
        active_document_ids: List[int] = None,
        conversation_history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Execute the full workflow pipeline for a user query."""
        self.logger.info(
            f"Processing query | "
            f"User: {user_id} | "
            f"Query: '{query[:100]}...'"
        )
        
        start_time = time.time()
        
        try:
            # Create initial state
            initial_state = create_initial_state(
                user_id=user_id,
                query=query,
                conversation_id=conversation_id,
                active_document_ids=active_document_ids,
                conversation_history=conversation_history
            )
            
            initial_state["status"] = ProcessingStatus.IN_PROGRESS
            
            # Execute workflow
            with LogExecutionTime(self.logger, f"Workflow execution"):
                final_state = await self.graph.ainvoke(
                    initial_state,
                    config={"run_name": f"rag_workflow_user_{user_id}"}
                )
            
            # Calculate total processing time
            processing_time = time.time() - start_time
            final_state["processing_time"] = processing_time
            final_state["status"] = ProcessingStatus.COMPLETED
            
            # Build response
            response = self._build_response(final_state)
            
            self.logger.info(
                f"Query processed successfully | "
                f"Intent: {final_state.get('intent', 'unknown')} | "
                f"Time: {processing_time:.2f}s | "
                f"Nodes: {len(final_state['nodes_visited'])}"
            )
            
            return response
            
        except Exception as e:
            self.logger.error(
                f"Workflow execution failed: {str(e)}",
                exc_info=True
            )
            
            processing_time = time.time() - start_time
            
            # Return error response
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "processing_time": processing_time,
                "user_id": user_id,
                "query": query
            }
    
    def _build_response(self, state: GraphState) -> Dict[str, Any]:
        """Extract and structure the final response from the completed graph state."""
        intent = state.get("intent")
        
        # Base response
        response = {
            "success": True,
            "intent": intent.value if intent else "unknown",
            "processing_time": state.get("processing_time", 0),
            "nodes_visited": state.get("nodes_visited", []),
            "metadata": {
                "user_id": state["user_id"],
                "conversation_id": state.get("conversation_id"),
                "document_types_used": state.get("document_types_available", []),
                "num_documents_retrieved": len(state.get("retrieved_documents", []))
            }
        }
        
        # Add intent-specific data
        if state.get("generated_answer"):
            response["answer"] = state["generated_answer"]
        
        if state.get("evaluation_result"):
            response["evaluation"] = state["evaluation_result"]
        
        if state.get("final_response"):
            response["response"] = state["final_response"]
        
        if state.get("generated_questions"):
            response["questions"] = state["generated_questions"]
        
        # Add context info
        if state.get("context"):
            response["metadata"]["context_length"] = len(state["context"])
        
        return response
    
    def get_workflow_info(self) -> Dict[str, Any]:
        """Return metadata about the workflow's available nodes and intents."""
        return {
            "nodes": [
                "classify_intent",
                "retrieve_documents",
                "generate_answer",
                "evaluate_answer",
                "resolve_doubt",
                "generate_questions",
                "general_chat"
            ],
            "entry_point": "classify_intent",
            "supported_intents": [
                "answer_generation",
                "answer_evaluation",
                "doubt_clarification",
                "question_generation"
            ]
        }


# Global workflow instance
_workflow_instance = None


def get_workflow() -> WorkflowOrchestrator:
    """Return the singleton workflow orchestrator instance."""
    global _workflow_instance
    
    if _workflow_instance is None:
        _workflow_instance = WorkflowOrchestrator()
    
    return _workflow_instance


async def process_user_query(
    user_id: int,
    query: str,
    conversation_id: int = None,
    active_document_ids: List[int] = None,
    conversation_history: List[Dict[str, str]] = None
) -> Dict[str, Any]:
    """Convenience function to process a query through the workflow."""
    workflow = get_workflow()
    return await workflow.process_query(
        user_id=user_id,
        query=query,
        conversation_id=conversation_id,
        active_document_ids=active_document_ids,
        conversation_history=conversation_history
    )
