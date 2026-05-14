"""
Query Rewriter Node
Optimizes the user query for better semantic search results.
"""
from typing import Dict, Any
from app.core.state import GraphState

try:
    from langsmith import traceable
except ImportError:
    def traceable(**kwargs):
        def decorator(func):
            return func
        return decorator

from app.core.logging_config import get_logger, LogExecutionTime
from app.services.llm_service import get_llm_service
from app.core.prompts import QUERY_REWRITER_SYSTEM, QUERY_REWRITER_USER

logger = get_logger(__name__)

class QueryRewriter:
    """
    Rewrites queries to improve retrieval.
    """
    
    def __init__(self):
        self.logger = logger
        
    async def rewrite(self, state: GraphState) -> GraphState:
        """
        Rewrite the user query.
        
        Args:
            state: Current graph state
            
        Returns:
            Updated state with rewritten_query
        """
        query = state["query"]
        
        self.logger.info(f"🔄 Rewriting query for better retrieval: '{query[:50]}...'")
        
        with LogExecutionTime(self.logger, "Query rewriting"):
            llm = await get_llm_service()
            
            prompt = QUERY_REWRITER_USER.format(question=query)
            
            llm_response = await llm.generate(
                prompt=prompt,
                system_prompt=QUERY_REWRITER_SYSTEM,
                temperature=0.7,
                max_tokens=100
            )
            
            rewritten_query = llm_response["generations"][0]["text"].strip()
            
            # Update state
            state["rewritten_query"] = rewritten_query
            state["run_loop_count"] = state.get("run_loop_count", 0) + 1
            state["nodes_visited"].append("query_rewriter")
            
            self.logger.info(f"Query rewritten: '{rewritten_query}'")
            
            return state

# Global instance
_query_rewriter = QueryRewriter()

@traceable(name="node_rewrite_query", run_type="chain")
async def rewrite_query_node(state: GraphState) -> GraphState:
    """LangGraph node function for query rewriting."""
    return await _query_rewriter.rewrite(state)
