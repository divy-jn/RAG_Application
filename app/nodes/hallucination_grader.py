"""
Hallucination Grader Node
Assess whether the generation is grounded in the retrieved documents.
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
from app.core.prompts import HALLUCINATION_GRADER_SYSTEM, HALLUCINATION_GRADER_USER, ANSWER_GRADER_SYSTEM, ANSWER_GRADER_USER

logger = get_logger(__name__)

class ReflectionGrader:
    """
    Grades the generation for hallucinations and question relevance.
    """
    
    def __init__(self):
        self.logger = logger
        
    async def grade(self, state: GraphState) -> GraphState:
        """
        Check for hallucinations and verify answer relevance.
        
        Args:
            state: Current graph state
            
        Returns:
            Updated state with is_hallucination flag
        """
        generation = state.get("generated_answer") or state.get("final_response")
        documents = state.get("retrieved_documents", [])
        query = state["query"]
        
        if not generation or not documents:
            state["is_hallucination"] = False # Can't check
            state["nodes_visited"].append("hallucination_grader")
            return state
            
        self.logger.info("🧠 Reflecting on answer quality and grounding...")
        
        with LogExecutionTime(self.logger, "Reflection grading"):
            llm = await get_llm_service()
            
            # 1. Check for Hallucination
            context_text = "\n\n".join([d["chunk_text"] for d in documents])
            hallucination_prompt = HALLUCINATION_GRADER_USER.format(
                documents=context_text,
                generation=generation
            )
            
            llm_response = await llm.generate(
                prompt=hallucination_prompt,
                system_prompt=HALLUCINATION_GRADER_SYSTEM,
                temperature=0,
                max_tokens=20
            )
            
            try:
                content = llm_response["generations"][0]["text"]
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                res = json.loads(content)
                is_grounded = res.get("score", "yes").lower() == "yes"
            except:
                is_grounded = True # Default to safe
                
            # 2. Check if it actually answers the question
            answer_prompt = ANSWER_GRADER_USER.format(
                question=query,
                generation=generation
            )
            
            llm_response_answer = await llm.generate(
                prompt=answer_prompt,
                system_prompt=ANSWER_GRADER_SYSTEM,
                temperature=0,
                max_tokens=20
            )
            
            try:
                content = llm_response_answer["generations"][0]["text"]
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                res = json.loads(content)
                is_addressing = res.get("score", "yes").lower() == "yes"
            except:
                is_addressing = True
            
            # Logic: If it's grounded AND addresses the question, it's NOT a hallucination/failure
            state["is_hallucination"] = not (is_grounded and is_addressing)
            state["nodes_visited"].append("hallucination_grader")
            
            self.logger.info(
                f"Reflection complete | "
                f"Grounded: {is_grounded} | "
                f"Addresses Question: {is_addressing} | "
                f"Issue Detected: {state['is_hallucination']}"
            )
            
            return state

# Global instance
_reflection_grader = ReflectionGrader()

@traceable(name="node_grade_hallucination", run_type="chain")
async def hallucination_grader_node(state: GraphState) -> GraphState:
    """LangGraph node function for hallucination grading."""
    return await _reflection_grader.grade(state)
