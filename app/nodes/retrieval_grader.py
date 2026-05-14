"""
Retrieval Grader Node
Assess the relevance of retrieved documents to the user question.
"""
import json
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
from app.core.prompts import RETRIEVAL_GRADER_SYSTEM, RETRIEVAL_GRADER_USER

logger = get_logger(__name__)

class RetrievalGrader:
    """
    Grades the relevance of retrieved documents.
    """
    
    def __init__(self):
        self.logger = logger
        
    async def grade(self, state: GraphState) -> GraphState:
        """
        Filter retrieved documents based on relevance.
        
        Args:
            state: Current graph state
            
        Returns:
            Updated state with filtered documents and is_relevant flag
        """
        query = state.get("rewritten_query") or state["query"]
        documents = state.get("retrieved_documents", [])
        
        self.logger.info(f"🔍 Grading {len(documents)} documents for relevance...")
        
        with LogExecutionTime(self.logger, "Retrieval grading"):
            if not documents:
                state["is_relevant"] = False
                state["nodes_visited"].append("retrieval_grader")
                return state
                
            llm = await get_llm_service()
            relevant_docs = []
            
            for doc in documents:
                prompt = RETRIEVAL_GRADER_USER.format(
                    question=query,
                    document=doc["chunk_text"]
                )
                
                # We use a lower temperature for classification
                llm_response = await llm.generate(
                    prompt=prompt,
                    system_prompt=RETRIEVAL_GRADER_SYSTEM,
                    temperature=0,
                    max_tokens=20
                )
                
                try:
                    # Parse JSON from LLM
                    content = llm_response["generations"][0]["text"]
                    # Sometimes LLM adds extra text or triple backticks
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0].strip()
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0].strip()
                        
                    res = json.loads(content)
                    score = res.get("score", "no").lower()
                    
                    if score == "yes":
                        relevant_docs.append(doc)
                except Exception as e:
                    self.logger.warning(f"Failed to parse grader response: {str(e)}")
                    # Default to keeping it if grading fails
                    relevant_docs.append(doc)
            
            # Update state
            state["retrieved_documents"] = relevant_docs
            state["is_relevant"] = len(relevant_docs) > 0
            state["nodes_visited"].append("retrieval_grader")
            
            self.logger.info(
                f"Grading complete | "
                f"Relevant: {len(relevant_docs)}/{len(documents)} | "
                f"Success: {state['is_relevant']}"
            )
            
            return state

# Global instance
_retrieval_grader = RetrievalGrader()

@traceable(name="node_grade_retrieval", run_type="chain")
async def grade_retrieval_node(state: GraphState) -> GraphState:
    """LangGraph node function for retrieval grading."""
    return await _retrieval_grader.grade(state)
