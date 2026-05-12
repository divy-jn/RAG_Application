"""
Answer Generation Node
Generates exam-oriented answers based on marking schemes and notes
"""
from typing import Dict, Any, Optional
from app.core.state import GraphState, Intent

from app.core.logging_config import get_logger, LogExecutionTime
from app.services.llm_service import get_llm_service
from app.core.exceptions import WorkflowNodeException, MissingDocumentsException
from app.core.config import settings
from app.core.prompts import (
    ANSWER_GEN_SYSTEM,
    ANSWER_GEN_MARKING_SCHEME,
    ANSWER_GEN_NOTES_ONLY
)


logger = get_logger(__name__)


class AnswerGenerator:
    """
    Generates structured answers aligned with marking schemes
    """
    
    def __init__(self):
        self.logger = logger
    
    async def generate(self, state: GraphState) -> GraphState:
        """
        Generate answer based on marking scheme and notes
        
        Args:
            state: Current graph state
            
        Returns:
            Updated state with generated answer
        """
        query = state["query"]
        context = state.get("context", "")
        doc_types = state.get("document_types_available", [])
        
        self.logger.info(
            f"✍️ Generating answer | "
            f"Query: '{query[:100]}' | "
            f"Available docs: {doc_types}"
        )
        
        with LogExecutionTime(self.logger, "Answer generation"):
            try:
                # Check if we have necessary documents
                if not context:
                    self.logger.warning("No context available for answer generation")
                    raise MissingDocumentsException(
                        required_types=["marking_scheme", "notes"],
                        available_types=doc_types
                    )
                
                # Extract question from query
                question = self._extract_question(query)
                
                # Check if marking scheme is available
                has_marking_scheme = "marking_scheme" in doc_types
                has_notes = "notes" in doc_types
                
                # Build appropriate prompt
                if has_marking_scheme:
                    prompt = self._build_marking_scheme_prompt(
                        question, context, has_notes
                    )
                else:
                    prompt = self._build_notes_only_prompt(question, context)
                
                # Generate answer using LLM
                llm_service = await get_llm_service()
                
                generated_answer = await llm_service.generate(
                    prompt=prompt,
                    system_prompt=self._get_system_prompt(),
                    temperature=0.7,
                    max_tokens=2000,
                    context={"user_id": state["user_id"], "intent": "answer_generation"}
                )
                
                # Format the answer
                formatted_answer = self._format_answer(
                    generated_answer,
                    has_marking_scheme
                )
                
                # Update state
                state["generated_answer"] = formatted_answer
                state["task_data"]["question"] = question
                state["task_data"]["has_marking_scheme"] = has_marking_scheme
                state["nodes_visited"].append("answer_generator")
                
                self.logger.info(
                    f"Answer generated | "
                    f"Length: {len(formatted_answer)} chars"
                )
                
                return state
                
            except Exception as e:
                self.logger.error(f"Answer generation failed: {str(e)}", exc_info=True)
                raise WorkflowNodeException(
                    node_name="answer_generator",
                    reason=str(e),
                    original_exception=e
                )
    
    def _extract_question(self, query: str) -> str:
        """
        Extract the actual question from the query
        
        Args:
            query: User query
            
        Returns:
            Extracted question
        """
        # Remove common prefixes
        patterns_to_remove = [
            r'^(generate|write|create|provide)\s+(answer|solution)\s+(for|to)\s+',
            r'^(answer|solve)\s+(this|the)\s+(question|problem):\s*',
            r'^please\s+',
        ]
        
        import re
        cleaned_query = query
        for pattern in patterns_to_remove:
            cleaned_query = re.sub(pattern, '', cleaned_query, flags=re.IGNORECASE)
        
        return cleaned_query.strip()
    
    def _build_marking_scheme_prompt(
        self,
        question: str,
        context: str,
        has_notes: bool
    ) -> str:
        """Build prompt when marking scheme is available"""
        
        """Build prompt when marking scheme is available"""
        
        return ANSWER_GEN_MARKING_SCHEME.format(
            question=question,
            context=context
        )
    
    def _build_notes_only_prompt(self, question: str, context: str) -> str:
        """Build prompt when only notes are available"""
        
        """Build prompt when only notes are available"""
        
        return ANSWER_GEN_NOTES_ONLY.format(
            question=question,
            context=context
        )
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for answer generation"""
    def _get_system_prompt(self) -> str:
        """Get system prompt for answer generation"""
        return ANSWER_GEN_SYSTEM
    
    def _format_answer(self, raw_answer: str, has_marking_scheme: bool) -> str:
        """
        Format the generated answer
        
        Args:
            raw_answer: Raw LLM output
            has_marking_scheme: Whether answer used marking scheme
            
        Returns:
            Formatted answer
        """
        # Add header
        if has_marking_scheme:
            header = "## Generated Answer (Based on Marking Scheme)\n\n"
        else:
            header = "## Generated Answer (Based on Notes)\n\n"
        
        # Clean up the answer
        cleaned = raw_answer.strip()
        
        # Add footer with disclaimer
        footer = "\n\n---\n*Note: This answer is generated based on uploaded documents. Please verify and adapt as needed.*"
        
        return header + cleaned + footer


# Global instance
_answer_generator = AnswerGenerator()


async def generate_answer_node(state: GraphState) -> GraphState:
    """
    LangGraph node function for answer generation
    
    Args:
        state: Current graph state
        
    Returns:
        Updated state with generated answer
    """
    return await _answer_generator.generate(state)


if __name__ == "__main__":
    import asyncio
    from langgraph_state import create_initial_state
    
    async def test():
        # Create test state with mock context
        state = create_initial_state(
            user_id=1,
            query="Generate answer for: What is machine learning?"
        )
        
        # Mock context with marking scheme and notes
        state["context"] = """
--- MARKING SCHEME ---
[Chunk 1 | Similarity: 0.95]
Q1: Define machine learning and provide examples. (10 marks)
- Definition (3 marks)
- Types of ML (3 marks)
- Examples (4 marks)

--- NOTES ---
[Chunk 1 | Similarity: 0.92]
Machine Learning is a subset of Artificial Intelligence that enables systems to learn from data.
Types include supervised learning, unsupervised learning, and reinforcement learning.
Examples: Image recognition, spam filtering, recommendation systems.
"""
        
        state["document_types_available"] = ["marking_scheme", "notes"]
        state["intent"] = Intent.ANSWER_GENERATION
        
        # Generate answer
        result = await generate_answer_node(state)
        
        print("\n" + "="*60)
        print("GENERATED ANSWER")
        print("="*60)
        print(result["generated_answer"])
        print("="*60)
    
    asyncio.run(test())
