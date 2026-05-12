"""
Doubt resolution node.
Handles conceptual question answering using retrieved document context or general knowledge fallback.
"""
from typing import Dict, Any, Optional
from app.core.state import GraphState

from app.core.logging_config import get_logger, LogExecutionTime
from app.services.llm_service import get_llm_service
from app.core.exceptions import WorkflowNodeException
from app.core.prompts import (
    DOUBT_RESOLVER_SYSTEM,
    DOUBT_RESOLVER_NOTES_PROMPT,
    DOUBT_RESOLVER_GENERAL_SYSTEM,
    DOUBT_RESOLVER_GENERAL_PROMPT
)


logger = get_logger(__name__)


class DoubtResolver:
    """Resolves student doubts by generating answers from uploaded notes or general knowledge."""
    
    def __init__(self):
        self.logger = logger
    
    async def resolve(self, state: GraphState) -> GraphState:
        query = state["query"]
        context = state.get("context", "")
        doc_types = state.get("document_types_available", [])
        retrieved_docs = state.get("retrieved_documents", [])
        
        self.logger.info(
            f"Resolving doubt | "
            f"Query: '{query[:100]}' | "
            f"Context available: {bool(context)}"
        )
        
        with LogExecutionTime(self.logger, "Doubt resolution"):
            try:
                # Determine if we have relevant notes
                has_relevant_notes = self._check_relevance(retrieved_docs)
                
                if has_relevant_notes:
                    # Answer from notes
                    answer, source_type = await self._answer_from_notes(
                        query, context
                    )
                else:
                    # Fallback to general knowledge
                    answer, source_type = await self._answer_from_general_knowledge(
                        query
                    )
                
                # Format the response
                formatted_response = self._format_response(
                    answer, source_type, has_relevant_notes
                )
                
                # Update state
                state["final_response"] = formatted_response
                state["task_data"]["source_type"] = source_type
                state["task_data"]["has_relevant_notes"] = has_relevant_notes
                state["nodes_visited"].append("doubt_resolver")
                
                self.logger.info(
                    f"Doubt resolved | "
                    f"Source: {source_type} | "
                    f"Length: {len(answer)} chars"
                )
                
                return state
                
            except Exception as e:
                self.logger.error(f"Doubt resolution failed: {str(e)}", exc_info=True)
                raise WorkflowNodeException(
                    node_name="doubt_resolver",
                    reason=str(e),
                    original_exception=e
                )
    
    def _check_relevance(self, retrieved_docs: list) -> bool:
        """Determine if retrieved documents contain sufficiently relevant content."""
        if not retrieved_docs:
            return False
        
        # Use a lower threshold to match the configured similarity threshold (0.2)
        # Real cosine similarity scores from MiniLM embeddings are typically 0.2-0.5
        relevant_count = sum(
            1 for doc in retrieved_docs
            if doc.get("similarity_score", 0) >= 0.15
        )
        
        # Consider relevant if at least 1 document has reasonable similarity
        return relevant_count >= 1
    
    async def _answer_from_notes(
        self,
        query: str,
        context: str
    ) -> tuple[str, str]:
        """Generate an answer strictly from the provided document context."""
        llm_service = await get_llm_service()
        
        prompt = DOUBT_RESOLVER_NOTES_PROMPT.format(query=query, context=context)
        
        system_prompt = DOUBT_RESOLVER_SYSTEM
        
        answer = await llm_service.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=1500
        )
        
        return answer.strip(), "notes"
    
    async def _answer_from_general_knowledge(
        self,
        query: str
    ) -> tuple[str, str]:
        """Reject the query and instruct the user to upload relevant documents."""
        llm_service = await get_llm_service()
        
        prompt = DOUBT_RESOLVER_GENERAL_PROMPT.format(query=query)
        
        system_prompt = DOUBT_RESOLVER_GENERAL_SYSTEM
        
        answer = await llm_service.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.8,
            max_tokens=1500
        )
        
        return answer.strip(), "general_knowledge"
    
    def _format_response(
        self,
        answer: str,
        source_type: str,
        has_relevant_notes: bool
    ) -> str:
        """Apply header and footer formatting based on the answer source."""
        # Add header based on source
        if source_type == "notes":
            header = "## Answer (Based on Your Notes)\n\n"
            footer = "\n\n---\n*This answer is based on your uploaded notes.*"
        else:
            header = "## Answer\n\n"
            footer = "\n\n---\n*This answer is based on general knowledge as your uploaded notes don't contain sufficient information on this topic. Please verify with your study materials.*"
        
        return header + answer + footer


# Global instance
_doubt_resolver = DoubtResolver()


async def resolve_doubt_node(state: GraphState) -> GraphState:
    """LangGraph node entry point for doubt resolution."""
    return await _doubt_resolver.resolve(state)
