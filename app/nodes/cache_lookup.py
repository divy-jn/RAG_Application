"""
Cache Lookup Node
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
from app.services.semantic_cache import get_semantic_cache
from app.core.state import Intent

logger = get_logger(__name__)

class CacheLookupNode:
    """
    Checks if the user's query has a highly confident cached answer.
    """
    
    def __init__(self):
        self.logger = logger
        
    @traceable(name="cache_lookup", run_type="tool")
    async def process(self, state: GraphState) -> GraphState:
        """
        Check semantic cache.
        """
        self.logger.info(f"Checking Semantic Cache | Query: '{state['query'][:50]}...'")
        
        with LogExecutionTime(self.logger, "Cache lookup"):
            cache = get_semantic_cache()
            result = cache.search_cache(state["query"])
            
            if result:
                self.logger.info("Semantic cache hit!")
                # Override state with cached answer
                state["final_response"] = result["answer"]
                
                # If we know the original intent, set it
                try:
                    state["intent"] = Intent(result["intent"])
                except ValueError:
                    pass
                    
            else:
                self.logger.info("Semantic cache miss.")
                
            return state
