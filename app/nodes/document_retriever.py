"""
Document Retrieval Node
Retrieves relevant document chunks based on user query and intent
"""
from typing import List, Dict, Any, Optional
from app.core.state import GraphState, Intent, RetrievedDocument

try:
    from langsmith import traceable
except ImportError:
    # Fallback: no-op decorator if langsmith not installed
    def traceable(**kwargs):
        def decorator(func):
            return func
        return decorator
        
from app.core.logging_config import get_logger, LogExecutionTime
from app.services.vector_store_service import get_vector_store
from app.services.embedding_service import get_embedding_service
from app.core.exceptions import WorkflowNodeException
from app.core.config import settings

try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None


logger = get_logger(__name__)


class DocumentRetriever:
    """
    Retrieves relevant documents from vector store based on query and intent
    """
    
    # Number of documents to retrieve per intent
    RETRIEVAL_COUNTS = {
        Intent.ANSWER_GENERATION: 10,
        Intent.ANSWER_EVALUATION: 5,  # Mainly marking scheme
        Intent.DOUBT_CLARIFICATION: 8,
        Intent.QUESTION_GENERATION: 10,
        Intent.EXAM_PAPER_GENERATION: 15,
    }
    
    # Document type priorities per intent
    DOCUMENT_TYPE_PRIORITIES = {
        Intent.ANSWER_GENERATION: ["marking_scheme", "notes", "question_paper"],
        Intent.ANSWER_EVALUATION: ["marking_scheme"],
        Intent.DOUBT_CLARIFICATION: ["notes", "marking_scheme"],
        Intent.QUESTION_GENERATION: ["notes", "question_paper"],
        Intent.EXAM_PAPER_GENERATION: ["notes", "question_paper", "marking_scheme"],
    }
    
    def __init__(self):
        self.logger = logger
        self.vector_store = None
    
    async def retrieve(self, state: GraphState) -> GraphState:
        """
        Retrieve relevant documents
        
        Args:
            state: Current graph state
            
        Returns:
            Updated state with retrieved documents
        """
        query = state["query"]
        intent = state.get("intent", Intent.DOUBT_CLARIFICATION)
        user_id = state["user_id"]
        
        self.logger.info(
            f"Retrieving documents | "
            f"Intent: {intent.value} | "
            f"Query: '{query[:100]}'"
        )
        
        with LogExecutionTime(self.logger, "Document retrieval"):
            try:
                # Initialize vector store if needed
                if self.vector_store is None:
                    self.vector_store = get_vector_store()
                
                # Build enhanced query based on intent and history
                history = state.get("conversation_history", [])
                enhanced_query = await self._enhance_query(query, intent, history)
                
                # Determine how many documents to retrieve
                n_results = self.RETRIEVAL_COUNTS.get(intent, 10)
                
                # Handle Active Documents Filtering
                active_doc_ids = state.get("active_document_ids")
                
                # If explicit empty list provided, skip retrieval entirely
                if active_doc_ids is not None and len(active_doc_ids) == 0:
                    self.logger.info("No active documents selected. Skipping retrieval.")
                    state["retrieved_documents"] = []
                    state["context"] = ""
                    state["document_types_available"] = []
                    state["nodes_visited"].append("document_retriever")
                    return state
                    
                where_filter = None
                if active_doc_ids:
                    where_filter = {"document_id": {"$in": active_doc_ids}}
                
                # Perform semantic search
                search_results = self.vector_store.search(
                    query=enhanced_query,
                    n_results=n_results * 2,  # Retrieve more, then filter
                    where=where_filter,
                    include=["documents", "metadatas", "distances"]
                )
                
                # Filter and rank results
                filtered_results = self._filter_and_rank_results(
                    search_results,
                    intent,
                    user_id,
                    n_results
                )
                
                # Re-rank with Cross-Encoder for higher accuracy
                filtered_results = self._rerank_results(
                    query, filtered_results, n_results
                )
                
                # Convert to RetrievedDocument format
                retrieved_docs = self._format_retrieved_documents(filtered_results)
                
                # Build context string
                context = self._build_context(retrieved_docs)
                
                # Web Search Fallback (CRAG-lite)
                # If we got very few docs or top score is low, augment with web search
                is_web_search_needed = len(retrieved_docs) == 0 or (
                    len(retrieved_docs) > 0 and retrieved_docs[0]["similarity_score"] < 0.6
                )
                
                if is_web_search_needed and DDGS:
                    self.logger.info("Local documents insufficient. Falling back to Web Search.")
                    web_context = self._perform_web_search(enhanced_query)
                    if web_context:
                        context = context + "\n\n--- WEB SEARCH RESULTS ---\n" + web_context
                        # Add a dummy document type so frontend knows web search was used
                        state["document_types_available"] = state.get("document_types_available", []) + ["web_search"]
                
                # Get available document types
                doc_types = list(set(doc["document_type"] for doc in retrieved_docs))
                
                # Update state
                state["retrieved_documents"] = retrieved_docs
                state["context"] = context
                state["document_types_available"] = doc_types
                state["retrieval_query"] = enhanced_query
                state["nodes_visited"].append("document_retriever")
                
                self.logger.info(
                    f"Retrieved {len(retrieved_docs)} documents | "
                    f"Types: {doc_types} | "
                    f"Context length: {len(context)} chars"
                )
                
                return state
                
            except Exception as e:
                self.logger.error(f"Document retrieval failed: {str(e)}", exc_info=True)
                
                # Set empty results instead of failing
                state["retrieved_documents"] = []
                state["context"] = ""
                state["document_types_available"] = []
                state["nodes_visited"].append("document_retriever")
                
                self.logger.warning("Continuing with empty document set")
                
                return state
    
    async def _enhance_query(self, query: str, intent: Intent, history: List[Dict[str, str]] = None) -> str:
        """
        Enhance query with intent-specific context and conversation history
        
        Args:
            query: Original query
            intent: Classified intent
            history: Conversation history
            
        Returns:
            Enhanced query string
        """
        final_query = query
        
        # Check if query needs contextualization (short or contains reference words)
        reference_words = ["it", "this", "that", "these", "those", "topic", "explain", "more", "detail", "he", "she", "they", "them", "first", "second", "last"]
        words = query.lower().split()
        needs_context = len(words) < 8 or any(word in words for word in reference_words)
        
        if needs_context and history and len(history) > 0:
            try:
                from app.services.llm_service import get_llm_service
                llm = get_llm_service()
                
                # Format history for prompt (last 2 interactions)
                history_text = "\n".join([f"{msg['role']}: {msg['content'][:200]}" for msg in history[-4:]])
                
                prompt = (
                    "Given the following conversation history and the latest user query, "
                    "rewrite the latest user query to be a standalone, highly descriptive search query "
                    "that explicitly includes the subject/topic being discussed in the history. "
                    "Replace pronouns like 'it' or 'the topic' with the actual topic name. "
                    "If the query is already standalone, just return the query.\n\n"
                    f"History:\n{history_text}\n\n"
                    f"Latest Query: {query}\n\n"
                    "Standalone Search Query (Return ONLY the query text, no other text or quotes):"
                )
                
                rewritten_query = ""
                async for chunk in llm.generate_stream(prompt, max_tokens=40, temperature=0.1):
                    rewritten_query += chunk
                    
                rewritten_query = rewritten_query.strip().strip('"').strip("'")
                if rewritten_query:
                    final_query = rewritten_query
                    self.logger.info(f"Contextualized query: '{query}' -> '{final_query}'")
            except Exception as e:
                self.logger.error(f"Failed to contextualize query: {e}")

        # Add intent-specific keywords to improve retrieval
        enhancements = {
            Intent.ANSWER_GENERATION: "answer solution explanation",
            Intent.ANSWER_EVALUATION: "marking scheme grading criteria",
            Intent.DOUBT_CLARIFICATION: "explanation concept definition",
            Intent.QUESTION_GENERATION: "questions examples problems",
            Intent.EXAM_PAPER_GENERATION: "questions topics syllabus",
        }
        
        enhancement = enhancements.get(intent, "")
        return f"{final_query} {enhancement}".strip()
    
    def _filter_and_rank_results(
        self,
        search_results: Dict[str, Any],
        intent: Intent,
        user_id: int,
        n_results: int
    ) -> List[Dict[str, Any]]:
        # Filter and rank search results based on intent and user access
        
        # Iterate over pre-formatted results from VectorStoreService
        results_list = search_results.get("results", [])
        
        if not results_list:
            return []
            
        # Get document type priorities for this intent
        type_priorities = self.DOCUMENT_TYPE_PRIORITIES.get(intent, [])
        
        # Score and filter results
        scored_results = []
        for result in results_list:
            metadata = result.get("metadata", {})
            document = result.get("document", "")
            distance = result.get("distance", 0.0)
            
            # Check access (user's own docs or public docs)
            if metadata.get("user_id") != user_id and metadata.get("visibility") != "public":
                continue
                
            # Convert distance to a similarity score (0 to 1) 
            # ChromaDB cosine distance ranges from 0 (perfect match) to 2.0 (exact opposite)
            # Mathematical conversion: Cosine Similarity = 1 - (Cosine Distance / 2)
            similarity = 1.0 - (distance / 2.0)
            
            # Base score from similarity
            score = similarity
            
            # Boost score based on document type priority
            doc_type = metadata.get("document_type", "other")
            if doc_type in type_priorities:
                priority_index = type_priorities.index(doc_type)
                boost = (len(type_priorities) - priority_index) * 0.1
                score += boost
            
            # Filter by similarity threshold
            if similarity >= settings.SIMILARITY_THRESHOLD:
                scored_results.append({
                    "result": {
                        "metadata": metadata,
                        "document": document,
                        "similarity": similarity
                    },
                    "score": score
                })
        
        # Return top n results (over-fetch for re-ranking)
        overfetch_n = n_results * settings.RERANK_OVERFETCH_MULTIPLIER
        return [item["result"] for item in scored_results[:overfetch_n]]
    
    def _rerank_results(
        self,
        query: str,
        results: List[Dict[str, Any]],
        n_results: int
    ) -> List[Dict[str, Any]]:
        """
        Re-rank filtered results using Cross-Encoder for higher accuracy.
        
        Args:
            query: Original user query
            results: Pre-filtered results from vector search
            n_results: Final number of results to return
            
        Returns:
            Re-ranked and pruned results
        """
        if not results or not settings.CROSS_ENCODER_ENABLED:
            return results[:n_results]
        
        try:
            embedding_service = get_embedding_service()
            
            # Extract document texts for re-ranking
            doc_texts = [r.get("document", "") for r in results]
            
            # Re-rank using Cross-Encoder
            reranked = embedding_service.rerank(
                query=query,
                documents=doc_texts,
                top_k=n_results
            )
            
            # Map back to original result objects with updated scores
            reranked_results = []
            for original_idx, ce_score, _ in reranked:
                result = results[original_idx].copy()
                result["cross_encoder_score"] = ce_score
                reranked_results.append(result)
            
            self.logger.info(
                f"Re-ranked {len(results)} → {len(reranked_results)} results"
            )
            
            return reranked_results
            
        except Exception as e:
            self.logger.warning(
                f"Cross-Encoder re-ranking failed, using original order: {e}"
            )
            return results[:n_results]
    
    def _format_retrieved_documents(
        self,
        results: List[Dict[str, Any]]
    ) -> List[RetrievedDocument]:
        # Convert raw results to RetrievedDocument format
        retrieved_docs = []
        
        for result in results:
            metadata = result.get("metadata", {})
            
            doc = RetrievedDocument(
                document_id=metadata.get("document_id", 0),
                document_type=metadata.get("document_type", "other"),
                chunk_text=result.get("document", ""),
                similarity_score=result.get("similarity", 0.0),
                metadata=metadata
            )
            
            retrieved_docs.append(doc)
        
        return retrieved_docs
    
    def _build_context(self, documents: List[RetrievedDocument]) -> str:
        # Build context string from retrieved documents
        if not documents:
            return ""
        
        context_parts = []
        
        # Group by document type
        by_type: Dict[str, List[RetrievedDocument]] = {}
        for doc in documents:
            doc_type = doc["document_type"]
            if doc_type not in by_type:
                by_type[doc_type] = []
            by_type[doc_type].append(doc)
        
        # Format each group
        for doc_type, docs in by_type.items():
            context_parts.append(f"\n--- {doc_type.upper().replace('_', ' ')} ---\n")
            
            for i, doc in enumerate(docs, 1):
                # Extract filename if available
                filename = doc.get("metadata", {}).get("filename", "Unknown Document")
                
                # Add chunk with metadata (without chunk ID or technical similarity metrics)
                chunk_info = f"[Source Section from: {filename}]"
                context_parts.append(f"{chunk_info}\n{doc['chunk_text']}\n")
        
        return "\n".join(context_parts)
        
    def _perform_web_search(self, query: str) -> str:
        """Fallback to DuckDuckGo search to augment context."""
        try:
            if not DDGS:
                return ""
            
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=3))
            
            if not results:
                return ""
                
            web_parts = []
            for i, res in enumerate(results, 1):
                title = res.get("title", "")
                body = res.get("body", "")
                href = res.get("href", "")
                web_parts.append(f"[Web Source {i}: {title}] ({href})\n{body}\n")
                
            return "\n".join(web_parts)
        except Exception as e:
            self.logger.warning(f"Web search failed: {e}")
            return ""
    
    async def retrieve_by_document_type(
        self,
        state: GraphState,
        document_types: List[str],
        n_results: int = 10
    ) -> List[RetrievedDocument]:
        """
        Retrieve documents of specific types
        
        Args:
            state: Current graph state
            document_types: List of document types to retrieve
            n_results: Number of results per type
            
        Returns:
            Retrieved documents
        """
        if self.vector_store is None:
            self.vector_store = get_vector_store()
        
        all_results = []
        
        for doc_type in document_types:
            # Search with document type filter
            results = self.vector_store.search(
                query=state["query"],
                n_results=n_results,
                where={"document_type": doc_type}
            )
            
            formatted = self._format_retrieved_documents(results.get("results", []))
            all_results.extend(formatted)
        
        return all_results


# Global instance
_document_retriever = DocumentRetriever()


@traceable(name="node_retrieve_documents", run_type="chain")
async def retrieve_documents_node(state: GraphState) -> GraphState:
    """
    LangGraph node function for document retrieval
    
    Args:
        state: Current graph state
        
    Returns:
        Updated state with retrieved documents
    """
    return await _document_retriever.retrieve(state)


if __name__ == "__main__":
    import asyncio
    from langgraph_state import create_initial_state, Intent
    from vector_store_service import get_vector_store
    
    async def test():
        # Setup: Add some test documents to vector store
        vector_store = get_vector_store()
        
        test_docs = [
            "Machine learning is a subset of AI that focuses on learning from data.",
            "Marking Scheme Q1: Definition of ML (2 marks), Examples (3 marks)",
            "Neural networks are inspired by biological neurons in the brain."
        ]
        
        test_metadata = [
            {"document_type": "notes", "user_id": 1, "visibility": "public"},
            {"document_type": "marking_scheme", "user_id": 1, "visibility": "public"},
            {"document_type": "notes", "user_id": 1, "visibility": "public"},
        ]
        
        vector_store.add_documents(test_docs, test_metadata)
        
        # Test retrieval
        state = create_initial_state(
            user_id=1,
            query="Explain machine learning with examples"
        )
        state["intent"] = Intent.DOUBT_CLARIFICATION
        
        result = await retrieve_documents_node(state)
        
        print(f"\nRetrieved {len(result['retrieved_documents'])} documents")
        print(f"Document types: {result['document_types_available']}")
        print(f"\nContext preview:\n{result['context'][:500]}...")
    
    asyncio.run(test())
