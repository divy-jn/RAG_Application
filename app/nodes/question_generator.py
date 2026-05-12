"""
Question Generation Node
Generates practice questions (MCQ, short, long) from uploaded notes
"""
from typing import Dict, Any, List, Optional
import re
from app.core.state import GraphState

from app.core.logging_config import get_logger, LogExecutionTime
from app.services.llm_service import get_llm_service
from app.core.exceptions import WorkflowNodeException, MissingDocumentsException
from app.core.prompts import (
    QUESTION_GEN_SYSTEM,
    QUESTION_GEN_MCQ,
    QUESTION_GEN_SHORT,
    QUESTION_GEN_LONG,
    QUESTION_GEN_NUMERICAL
)


logger = get_logger(__name__)


class QuestionGenerator:
    """
    Generates academic questions from notes
    Supports multiple question types and difficulty levels
    """
    
    # Question type specifications
    QUESTION_TYPES = {
        "mcq": {
            "name": "Multiple Choice Questions",
            "default_count": 5,
            "marks_range": (1, 2)
        },
        "short": {
            "name": "Short Answer Questions",
            "default_count": 5,
            "marks_range": (2, 5)
        },
        "long": {
            "name": "Long Answer Questions",
            "default_count": 3,
            "marks_range": (10, 15)
        },
        "numerical": {
            "name": "Numerical/Problem-Solving",
            "default_count": 3,
            "marks_range": (5, 10)
        }
    }
    
    def __init__(self):
        self.logger = logger
    
    async def generate(self, state: GraphState) -> GraphState:
        """
        Generate questions
        
        Args:
            state: Current graph state
            
        Returns:
            Updated state with generated questions
        """
        query = state["query"]
        context = state.get("context", "")
        doc_types = state.get("document_types_available", [])
        
        self.logger.info(
            f"Generating questions | "
            f"Query: '{query[:100]}'"
        )
        
        with LogExecutionTime(self.logger, "Question generation"):
            try:
                # Check if we have notes
                if not context or "notes" not in doc_types:
                    self.logger.warning("No notes available for question generation")
                    raise MissingDocumentsException(
                        required_types=["notes"],
                        available_types=doc_types
                    )
                
                # Parse question generation request
                request = self._parse_generation_request(query)
                
                # Generate questions
                questions = await self._generate_questions(
                    context=context,
                    question_type=request["type"],
                    num_questions=request["count"],
                    difficulty=request["difficulty"],
                    topic=request.get("topic", "")
                )
                
                # Format questions for display
                formatted_output = self._format_questions(questions, request)
                
                # Update state
                state["generated_questions"] = questions
                state["final_response"] = formatted_output
                state["task_data"]["question_type"] = request["type"]
                state["task_data"]["num_questions"] = len(questions)
                state["nodes_visited"].append("question_generator")
                
                self.logger.info(
                    f"Generated {len(questions)} questions | "
                    f"Type: {request['type']} | "
                    f"Difficulty: {request['difficulty']}"
                )
                
                return state
                
            except Exception as e:
                self.logger.error(f"Question generation failed: {str(e)}", exc_info=True)
                raise WorkflowNodeException(
                    node_name="question_generator",
                    reason=str(e),
                    original_exception=e
                )
    
    def _parse_generation_request(self, query: str) -> Dict[str, Any]:
        """
        Parse question generation request from query
        
        Returns:
            Dictionary with type, count, difficulty, topic
        """
        query_lower = query.lower()
        
        # Detect question type
        question_type = "short"  # default
        if any(word in query_lower for word in ["mcq", "multiple choice", "objective"]):
            question_type = "mcq"
        elif any(word in query_lower for word in ["long", "essay", "descriptive"]):
            question_type = "long"
        elif any(word in query_lower for word in ["numerical", "problem", "calculation"]):
            question_type = "numerical"
        
        # Extract number of questions
        num_match = re.search(r'(\d+)\s+(?:questions?|mcqs?)', query_lower)
        num_questions = int(num_match.group(1)) if num_match else self.QUESTION_TYPES[question_type]["default_count"]
        
        # Limit to reasonable number
        num_questions = min(num_questions, 15)
        
        # Detect difficulty
        difficulty = "medium"  # default
        if any(word in query_lower for word in ["easy", "simple", "basic"]):
            difficulty = "easy"
        elif any(word in query_lower for word in ["hard", "difficult", "challenging", "advanced"]):
            difficulty = "hard"
        
        # Extract topic if mentioned
        topic_match = re.search(r'(?:on|about|regarding)\s+(.+?)(?:\s+with|\s+of|\s*$)', query, re.IGNORECASE)
        topic = topic_match.group(1).strip() if topic_match else ""
        
        return {
            "type": question_type,
            "count": num_questions,
            "difficulty": difficulty,
            "topic": topic
        }
    
    async def _generate_questions(
        self,
        context: str,
        question_type: str,
        num_questions: int,
        difficulty: str,
        topic: str
    ) -> List[Dict[str, Any]]:
        """
        Generate questions using LLM
        
        Returns:
            List of question dictionaries
        """
        llm_service = await get_llm_service()
        
        # Build type-specific prompt
        if question_type == "mcq":
            prompt = self._build_mcq_prompt(context, num_questions, difficulty, topic)
        elif question_type == "short":
            prompt = self._build_short_prompt(context, num_questions, difficulty, topic)
        elif question_type == "long":
            prompt = self._build_long_prompt(context, num_questions, difficulty, topic)
        else:  # numerical
            prompt = self._build_numerical_prompt(context, num_questions, difficulty, topic)
        
        # Generate
        response = await llm_service.generate(
            prompt=prompt,
            system_prompt=self._get_system_prompt(),
            temperature=0.8,
            max_tokens=2000
        )
        
        # Parse response into structured questions
        questions = self._parse_llm_response(response, question_type)
        
        return questions
    
    def _build_mcq_prompt(self, context: str, num: int, difficulty: str, topic: str) -> str:
        """Build prompt for MCQ generation"""
        marks = self.QUESTION_TYPES["mcq"]["marks_range"][0]
        
        return QUESTION_GEN_MCQ.format(num=num, topic=topic, difficulty=difficulty, marks=marks, context=context)
    
    def _build_short_prompt(self, context: str, num: int, difficulty: str, topic: str) -> str:
        """Build prompt for short answer questions"""
        marks_range = self.QUESTION_TYPES["short"]["marks_range"]
        
        return QUESTION_GEN_SHORT.format(num=num, topic=topic, difficulty=difficulty, marks_min=marks_range[0], marks_max=marks_range[1], context=context)
    
    def _build_long_prompt(self, context: str, num: int, difficulty: str, topic: str) -> str:
        """Build prompt for long answer questions"""
        marks_range = self.QUESTION_TYPES["long"]["marks_range"]
        
        return QUESTION_GEN_LONG.format(num=num, topic=topic, difficulty=difficulty, marks_min=marks_range[0], marks_max=marks_range[1], context=context)
    
    def _build_numerical_prompt(self, context: str, num: int, difficulty: str, topic: str) -> str:
        """Build prompt for numerical questions"""
        marks_range = self.QUESTION_TYPES["numerical"]["marks_range"]
        
        return QUESTION_GEN_NUMERICAL.format(num=num, topic=topic, difficulty=difficulty, marks_min=marks_range[0], marks_max=marks_range[1], context=context)
    
    def _get_system_prompt(self) -> str:
        """System prompt for question generation"""
    def _get_system_prompt(self) -> str:
        """System prompt for question generation"""
        return QUESTION_GEN_SYSTEM
    
    def _parse_llm_response(self, response: str, question_type: str) -> List[Dict[str, Any]]:
        """
        Parse LLM response into structured question list
        
        Returns:
            List of question dictionaries
        """
        questions = []
        
        # Split by question number pattern
        question_blocks = re.split(r'\n(?=Q\d+\.)', response.strip())
        
        for block in question_blocks:
            if not block.strip():
                continue
            
            try:
                question = self._parse_question_block(block, question_type)
                if question:
                    questions.append(question)
            except Exception as e:
                self.logger.warning(f"Failed to parse question block: {str(e)}")
                continue
        
        return questions
    
    def _parse_question_block(self, block: str, question_type: str) -> Optional[Dict[str, Any]]:
        """Parse individual question block"""
        lines = block.strip().split('\n')
        
        if not lines:
            return None
        
        # Extract question text (first line)
        question_text = re.sub(r'^Q\d+\.\s*', '', lines[0])
        
        # Extract marks
        marks_match = re.search(r'\((\d+)\s*marks?\)', question_text)
        marks = int(marks_match.group(1)) if marks_match else self.QUESTION_TYPES[question_type]["marks_range"][0]
        
        question = {
            "question_text": question_text,
            "marks": marks,
            "type": question_type
        }
        
        # Type-specific parsing
        if question_type == "mcq":
            # Extract options and correct answer
            options = {}
            for line in lines[1:]:
                option_match = re.match(r'([A-D])\)\s*(.+)', line.strip())
                if option_match:
                    options[option_match.group(1)] = option_match.group(2).strip()
                
                correct_match = re.search(r'Correct:\s*([A-D])', line, re.IGNORECASE)
                if correct_match:
                    question["correct_answer"] = correct_match.group(1)
            
            question["options"] = options
        
        return question
    
    def _format_questions(self, questions: List[Dict[str, Any]], request: Dict[str, Any]) -> str:
        """Format questions for display"""
        type_name = self.QUESTION_TYPES[request["type"]]["name"]
        
        output = f"# Generated {type_name}\n\n"
        output += f"**Difficulty:** {request['difficulty'].capitalize()}\n"
        output += f"**Total Questions:** {len(questions)}\n\n"
        output += "---\n\n"
        
        for i, q in enumerate(questions, 1):
            output += f"## Question {i} ({q['marks']} marks)\n\n"
            output += f"{q['question_text']}\n\n"
            
            if q['type'] == 'mcq' and 'options' in q:
                for letter, text in q['options'].items():
                    output += f"{letter}) {text}\n"
                output += "\n"
                if 'correct_answer' in q:
                    output += f"**Correct Answer:** {q['correct_answer']}\n"
            
            output += "\n---\n\n"
        
        output += "*Note: These questions are generated from your uploaded notes.*"
        
        return output


# Global instance
_question_generator = QuestionGenerator()


async def generate_questions_node(state: GraphState) -> GraphState:
    """
    LangGraph node function for question generation
    
    Args:
        state: Current graph state
        
    Returns:
        Updated state with generated questions
    """
    return await _question_generator.generate(state)


if __name__ == "__main__":
    import asyncio
    from langgraph_state import create_initial_state
    
    async def test():
        state = create_initial_state(
            user_id=1,
            query="Generate 3 MCQs on machine learning"
        )
        
        state["context"] = """
--- NOTES ---
Machine Learning is a subset of AI that enables systems to learn from data.
Types include supervised learning (labeled data), unsupervised learning (unlabeled data),
and reinforcement learning (reward-based).
Common algorithms: linear regression, decision trees, neural networks.
"""
        
        state["document_types_available"] = ["notes"]
        
        result = await generate_questions_node(state)
        
        print("\n" + "="*60)
        print("GENERATED QUESTIONS")
        print("="*60)
        print(result["final_response"])
        print("="*60)
    
    asyncio.run(test())
