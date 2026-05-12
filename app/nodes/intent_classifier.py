"""
Intent Classification Node
Analyzes user query to determine which academic task they want to perform
"""
import re
from typing import Dict, Any
from app.core.state import GraphState, Intent

from app.core.logging_config import get_logger, LogExecutionTime
from app.services.llm_service import get_llm_service
from app.core.exceptions import UnknownIntentException, WorkflowNodeException
from app.core.prompts import INTENT_CLASSIFICATION_SYSTEM, INTENT_CLASSIFICATION_USER


logger = get_logger(__name__)


class IntentClassifier:
    """
    Classifies user intent using rule-based patterns and LLM fallback
    """
    
    # Intent keywords and patterns
    INTENT_PATTERNS = {
        Intent.ANSWER_GENERATION: [
            r'\b(generate|write|create|provide)\s+(answer|response|solution)',
            r'\banswer\s+(this|the)\s+question',
            r'\bgenerate\s+answer',
            r'\bsolve\s+(this|the)\s+problem',
            r'\bwrite\s+answer\s+for',
            r'\bprovide\s+solution',
            r'\baccording\s+to\s+marking\s+scheme',
        ],
        Intent.ANSWER_EVALUATION: [
            r'\b(evaluate|check|review|grade|assess|mark)\s+(my|this)\s+answer',
            r'\bhow\s+(many|much)\s+marks',
            r'\bis\s+(my|this)\s+answer\s+(correct|right|good)',
            r'\bcompare\s+(with|to)\s+marking\s+scheme',
            r'\bcheck\s+my\s+solution',
            r'\bgrade\s+(this|my)\s+answer',
            r'\bfeedback\s+on\s+(my|this)\s+answer',
        ],
        Intent.DOUBT_CLARIFICATION: [
            r'\b(what|why|how|when|where|who)\s+(is|are|does|do|can|should)',
            r'\b(explain|clarify|help\s+me\s+understand)',
            r'\bI\s+(don\'t|do\s+not)\s+understand',
            r'\bcan\s+you\s+explain',
            r'\bdoubt\s+(about|regarding)',
            r'\bconfused\s+about',
            r'\bwhat\s+does\s+.+\s+mean',
        ],
        Intent.QUESTION_GENERATION: [
            r'\b(generate|create|make|give)\s+(questions?|quiz|mcq)',
            r'\bquestion\s+paper',
            r'\bcreate\s+.+\s+questions?',
            r'\bgenerate\s+mcq',
            r'\bmake\s+.+\s+quiz',
            r'\bprovide\s+practice\s+questions',
        ],
        Intent.EXAM_PAPER_GENERATION: [
            r'\b(generate|create|make)\s+(exam|test)\s+paper',
            r'\bfull\s+exam\s+paper',
            r'\bquestion\s+paper\s+with',
            r'\bcreate\s+complete\s+exam',
        ]
    }
    
    # Keywords that suggest specific intents
    INTENT_KEYWORDS = {
        Intent.ANSWER_GENERATION: ['answer', 'solution', 'solve', 'generate answer', 'write answer'],
        Intent.ANSWER_EVALUATION: ['evaluate', 'check', 'grade', 'marks', 'feedback', 'assess'],
        Intent.DOUBT_CLARIFICATION: ['what', 'why', 'how', 'explain', 'clarify', 'understand', 'doubt'],
        Intent.QUESTION_GENERATION: ['generate questions', 'create questions', 'quiz', 'mcq'],
        Intent.EXAM_PAPER_GENERATION: ['exam paper', 'test paper', 'question paper']
    }
    
    def __init__(self):
        self.logger = logger
    
    async def classify(self, state: GraphState) -> GraphState:
        """
        Classify user intent
        
        Args:
            state: Current graph state
            
        Returns:
            Updated state with intent classification
        """
        query = state["query"].lower()
        
        self.logger.info(f"Classifying intent | Query: '{state['query'][:100]}'")
        
        with LogExecutionTime(self.logger, "Intent classification"):
            try:
                # Step 1: Try rule-based classification
                intent, confidence = self._rule_based_classification(query)
                
                # Step 2: If confidence is low, use LLM
                if confidence < 0.7:
                    self.logger.debug(
                        f"Low confidence ({confidence:.2f}), using LLM for classification"
                    )
                    intent, confidence = await self._llm_based_classification(state["query"])
                
                # Update state
                state["intent"] = intent
                state["intent_confidence"] = confidence
                state["nodes_visited"].append("intent_classifier")
                
                self.logger.info(
                    f"Intent classified | "
                    f"Intent: {intent.value} | "
                    f"Confidence: {confidence:.2%}"
                )
                
                return state
                
            except Exception as e:
                self.logger.error(f"Intent classification failed: {str(e)}", exc_info=True)
                raise WorkflowNodeException(
                    node_name="intent_classifier",
                    reason=str(e),
                    original_exception=e
                )
    
    def _rule_based_classification(self, query: str) -> tuple[Intent, float]:
        """
        Classify intent using regex patterns and keywords
        
        Returns:
            (Intent, confidence_score)
        """
        intent_scores = {intent: 0.0 for intent in Intent}
        
        # Check patterns
        for intent, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    intent_scores[intent] += 0.3
        
        # Check keywords
        for intent, keywords in self.INTENT_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in query:
                    intent_scores[intent] += 0.2
        
        # Find highest scoring intent
        best_intent = max(intent_scores.items(), key=lambda x: x[1])
        
        # If no strong match, return DOUBT_CLARIFICATION as default
        if best_intent[1] == 0:
            return Intent.DOUBT_CLARIFICATION, 0.5
        
        # Normalize confidence to 0-1
        confidence = min(best_intent[1], 1.0)
        
        return best_intent[0], confidence
    
    async def _llm_based_classification(self, query: str) -> tuple[Intent, float]:
        """
        Use LLM to classify intent when rules are uncertain
        
        Returns:
            (Intent, confidence_score)
        """
        llm_service = await get_llm_service()
        
        
        try:
            prompt = INTENT_CLASSIFICATION_USER.format(query=query)
            
            response = await llm_service.generate(
                prompt=prompt,
                system_prompt=INTENT_CLASSIFICATION_SYSTEM,
                temperature=0.3,
                max_tokens=150
            )
            
            # Parse LLM response
            intent_str = self._extract_field(response, "INTENT")
            confidence_str = self._extract_field(response, "CONFIDENCE")
            
            # Map to Intent enum
            intent_mapping = {
                "ANSWER_GENERATION": Intent.ANSWER_GENERATION,
                "ANSWER_EVALUATION": Intent.ANSWER_EVALUATION,
                "DOUBT_CLARIFICATION": Intent.DOUBT_CLARIFICATION,
                "QUESTION_GENERATION": Intent.QUESTION_GENERATION,
                "EXAM_PAPER_GENERATION": Intent.EXAM_PAPER_GENERATION,
            }
            
            intent = intent_mapping.get(intent_str.upper(), Intent.DOUBT_CLARIFICATION)
            confidence = float(confidence_str) if confidence_str else 0.7
            
            return intent, confidence
            
        except Exception as e:
            self.logger.warning(f"LLM classification failed: {str(e)}")
            # Fallback to doubt clarification
            return Intent.DOUBT_CLARIFICATION, 0.6
    
    def _extract_field(self, text: str, field_name: str) -> str:
        """Extract field value from LLM response"""
        pattern = rf"{field_name}:\s*(.+?)(?:\n|$)"
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else ""


# Global instance
_intent_classifier = IntentClassifier()


async def classify_intent_node(state: GraphState) -> GraphState:
    """
    LangGraph node function for intent classification
    
    Args:
        state: Current graph state
        
    Returns:
        Updated state with intent
    """
    return await _intent_classifier.classify(state)


if __name__ == "__main__":
    import asyncio
    from langgraph_state import create_initial_state
    
    async def test():
        # Test various queries
        test_queries = [
            "Generate answer for question 1 using the marking scheme",
            "Can you check my answer and tell me how many marks I got?",
            "What is the difference between supervised and unsupervised learning?",
            "Create 5 MCQ questions on neural networks",
            "Generate a complete exam paper with 10 questions"
        ]
        
        for query in test_queries:
            state = create_initial_state(user_id=1, query=query)
            result = await classify_intent_node(state)
            
            print(f"\nQuery: {query}")
            print(f"   Intent: {result['intent'].value}")
            print(f"   Confidence: {result['intent_confidence']:.2%}")
    
    asyncio.run(test())
