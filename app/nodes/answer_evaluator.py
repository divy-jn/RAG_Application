"""
Answer Evaluation Node
Evaluates student answers using semantic similarity with marking schemes
"""
from typing import Dict, Any, List, Optional
import re
from app.core.state import GraphState

from app.core.logging_config import get_logger, LogExecutionTime
from app.services.llm_service import get_llm_service
from app.services.embedding_service import get_embedding_service
from app.core.exceptions import WorkflowNodeException, MissingDocumentsException
from app.core.prompts import EVALUATION_LLM_PROMPT, FEEDBACK_GENERATION_PROMPT


logger = get_logger(__name__)


class AnswerEvaluator:
    """
    Evaluates student answers against marking schemes using semantic similarity
    """
    
    def __init__(self):
        self.logger = logger
    
    async def evaluate(self, state: GraphState) -> GraphState:
        """
        Evaluate student answer
        
        Args:
            state: Current graph state
            
        Returns:
            Updated state with evaluation results
        """
        query = state["query"]
        context = state.get("context", "")
        doc_types = state.get("document_types_available", [])
        
        self.logger.info(
            f"Evaluating answer | "
            f"Query length: {len(query)} | "
            f"Available docs: {doc_types}"
        )
        
        with LogExecutionTime(self.logger, "Answer evaluation"):
            try:
                # Check for marking scheme
                if "marking_scheme" not in doc_types:
                    raise MissingDocumentsException(
                        required_types=["marking_scheme"],
                        available_types=doc_types
                    )
                
                # Extract question and student answer from query
                question, student_answer = self._extract_question_and_answer(query)
                
                # Extract marking scheme from context
                marking_scheme = self._extract_marking_scheme(context)
                
                # Parse marking points
                marking_points = self._parse_marking_scheme(marking_scheme)
                
                if not marking_points:
                    # Fallback to LLM-based evaluation
                    evaluation = await self._llm_based_evaluation(
                        question, student_answer, marking_scheme
                    )
                else:
                    # Use semantic similarity evaluation
                    evaluation = await self._semantic_evaluation(
                        student_answer, marking_points
                    )
                
                # Generate detailed feedback
                feedback = await self._generate_feedback(
                    question, student_answer, marking_scheme, evaluation
                )
                
                # Prepare evaluation result
                evaluation_result = {
                    "question": question,
                    "student_answer": student_answer,
                    "total_marks": evaluation["total_marks"],
                    "obtained_marks": evaluation["obtained_marks"],
                    "percentage": (evaluation["obtained_marks"] / evaluation["total_marks"] * 100) if evaluation["total_marks"] > 0 else 0,
                    "point_wise_evaluation": evaluation.get("points", []),
                    "feedback": feedback,
                    "strengths": evaluation.get("strengths", []),
                    "improvements": evaluation.get("improvements", [])
                }
                
                # Update state
                state["evaluation_result"] = evaluation_result
                state["task_data"]["question"] = question
                state["task_data"]["student_answer"] = student_answer
                state["nodes_visited"].append("answer_evaluator")
                
                self.logger.info(
                    f"Evaluation complete | "
                    f"Score: {evaluation['obtained_marks']}/{evaluation['total_marks']} "
                    f"({evaluation_result['percentage']:.1f}%)"
                )
                
                return state
                
            except Exception as e:
                self.logger.error(f"Answer evaluation failed: {str(e)}", exc_info=True)
                raise WorkflowNodeException(
                    node_name="answer_evaluator",
                    reason=str(e),
                    original_exception=e
                )
    
    def _extract_question_and_answer(self, query: str) -> tuple[str, str]:
        """
        Extract question and student answer from query
        
        Returns:
            (question, student_answer)
        """
        # Try to find patterns like "Question: ... Answer: ..."
        question_pattern = r'(?:question|q):\s*(.+?)(?:answer|my answer|student answer|a):\s*(.+)'
        match = re.search(question_pattern, query, re.IGNORECASE | re.DOTALL)
        
        if match:
            return match.group(1).strip(), match.group(2).strip()
        
        # If no clear separation, assume entire query is the answer to evaluate
        # and question will be extracted from marking scheme
        return "", query
    
    def _extract_marking_scheme(self, context: str) -> str:
        """Extract marking scheme section from context"""
        # Find marking scheme section
        pattern = r'---\s*MARKING[_ ]SCHEME\s*---\s*(.+?)(?=---|$)'
        match = re.search(pattern, context, re.IGNORECASE | re.DOTALL)
        
        if match:
            return match.group(1).strip()
        
        # If no clear section, return full context
        return context
    
    def _parse_marking_scheme(self, marking_scheme: str) -> List[Dict[str, Any]]:
        """
        Parse marking scheme into individual points
        
        Returns:
            List of marking points with description and marks
        """
        points = []
        
        # Pattern: "Point description (X marks)" or "- Point (X marks)"
        pattern = r'[-•*]?\s*(.+?)\s*\((\d+)\s*marks?\)'
        matches = re.findall(pattern, marking_scheme, re.IGNORECASE)
        
        for description, marks in matches:
            points.append({
                "description": description.strip(),
                "max_marks": int(marks),
                "obtained_marks": 0
            })
        
        return points
    
    async def _semantic_evaluation(
        self,
        student_answer: str,
        marking_points: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Evaluate using semantic similarity
        
        Args:
            student_answer: Student's answer text
            marking_points: Parsed marking points
            
        Returns:
            Evaluation results
        """
        embedding_service = get_embedding_service()
        
        # Split student answer into sentences for granular matching
        import nltk
        try:
            student_sentences = nltk.sent_tokenize(student_answer)
        except:
            # Fallback: split by periods
            student_sentences = [s.strip() + '.' for s in student_answer.split('.') if s.strip()]
        
        # Evaluate each marking point
        evaluated_points = []
        total_marks = 0
        obtained_marks = 0.0
        
        for point in marking_points:
            point_description = point["description"]
            max_marks = point["max_marks"]
            total_marks += max_marks
            
            # Find best matching sentence in student answer
            best_similarity = 0.0
            best_sentence = ""
            
            for sentence in student_sentences:
                if len(sentence.strip()) < 10:  # Skip very short sentences
                    continue
                
                similarity = embedding_service.compute_similarity(
                    point_description,
                    sentence,
                    metric="cosine"
                )
                
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_sentence = sentence
            
            # Award marks based on similarity
            # High similarity (>0.85): Full marks
            # Medium similarity (0.70-0.85): Partial marks
            # Low similarity (<0.70): Minimal marks
            
            if best_similarity >= 0.85:
                awarded = max_marks
                status = "✓ Fully covered"
            elif best_similarity >= 0.70:
                awarded = max_marks * 0.7
                status = "◐ Partially covered"
            elif best_similarity >= 0.50:
                awarded = max_marks * 0.4
                status = "◔ Mentioned"
            else:
                awarded = 0
                status = "✗ Missing"
            
            obtained_marks += awarded
            
            evaluated_points.append({
                "description": point_description,
                "max_marks": max_marks,
                "obtained_marks": round(awarded, 1),
                "similarity": round(best_similarity, 3),
                "status": status,
                "matching_sentence": best_sentence[:100] if best_sentence else None
            })
        
        return {
            "total_marks": total_marks,
            "obtained_marks": round(obtained_marks, 1),
            "points": evaluated_points,
            "evaluation_method": "semantic_similarity"
        }
    
    async def _llm_based_evaluation(
        self,
        question: str,
        student_answer: str,
        marking_scheme: str
    ) -> Dict[str, Any]:
        """
        Fallback: Use LLM for evaluation when scheme parsing fails
        
        Returns:
            Evaluation results
        """
        llm_service = await get_llm_service()
        
        prompt = EVALUATION_LLM_PROMPT.format(
            question=question if question else "See marking scheme",
            marking_scheme=marking_scheme,
            student_answer=student_answer
        )
        
        response = await llm_service.generate(
            prompt=prompt,
            temperature=0.3,
            max_tokens=1000
        )
        
        # Parse LLM response
        total_marks = self._extract_number(response, r'TOTAL_MARKS:\s*(\d+)')
        obtained_marks = self._extract_number(response, r'OBTAINED_MARKS:\s*([\d.]+)')
        
        return {
            "total_marks": total_marks or 10,
            "obtained_marks": obtained_marks or 0,
            "points": [],
            "evaluation_method": "llm_based",
            "llm_response": response
        }
    
    async def _generate_feedback(
        self,
        question: str,
        student_answer: str,
        marking_scheme: str,
        evaluation: Dict[str, Any]
    ) -> str:
        """Generate detailed feedback for student"""
        
        llm_service = await get_llm_service()
        
        prompt = FEEDBACK_GENERATION_PROMPT.format(
            question=question if question else "See marking scheme",
            student_answer=student_answer,
            obtained_marks=evaluation['obtained_marks'],
            total_marks=evaluation['total_marks'],
            evaluation_details=self._format_evaluation_for_prompt(evaluation)
        )
        
        feedback = await llm_service.generate(
            prompt=prompt,
            temperature=0.7,
            max_tokens=500
        )
        
        return feedback.strip()
    
    def _format_evaluation_for_prompt(self, evaluation: Dict[str, Any]) -> str:
        """Format evaluation data for LLM prompt"""
        if "points" in evaluation and evaluation["points"]:
            lines = ["Point-wise breakdown:"]
            for point in evaluation["points"]:
                lines.append(
                    f"- {point['description']}: "
                    f"{point['obtained_marks']}/{point['max_marks']} marks "
                    f"({point['status']})"
                )
            return "\n".join(lines)
        return ""
    
    def _extract_number(self, text: str, pattern: str) -> Optional[float]:
        """Extract number from text using regex pattern"""
        match = re.search(pattern, text)
        if match:
            try:
                return float(match.group(1))
            except:
                pass
        return None


# Global instance
_answer_evaluator = AnswerEvaluator()


async def evaluate_answer_node(state: GraphState) -> GraphState:
    """
    LangGraph node function for answer evaluation
    
    Args:
        state: Current graph state
        
    Returns:
        Updated state with evaluation results
    """
    return await _answer_evaluator.evaluate(state)
