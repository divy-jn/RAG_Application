"""
Semantic Cache Service
Stores highly confident past answers to save compute and time.
"""
import uuid
from typing import Optional, Dict, Any, List
from app.core.logging_config import get_logger, LogExecutionTime
from app.services.vector_store_service import get_vector_store
from app.core.config import settings
from app.services.embedding_service import get_embedding_service

logger = get_logger(__name__)

class SemanticCacheService:
    def __init__(self):
        self.logger = logger
        self.vector_store = get_vector_store()
        self.embedding_service = get_embedding_service()
        
        # We use a separate collection in the same Chroma client
        try:
            self.collection = self.vector_store.client.get_or_create_collection(
                name="golden_qa_cache",
                metadata={"hnsw:space": "cosine"}
            )
            self.logger.info(f"Initialized Semantic Cache. Entries: {self.collection.count()}")
        except Exception as e:
            self.logger.error(f"Failed to initialize Semantic Cache: {e}")
            self.collection = None

    def search_cache(self, query: str, threshold: float = 0.95) -> Optional[Dict[str, Any]]:
        """
        Search for a highly similar past query.
        Returns the cached answer if distance < (1.0 - threshold).
        """
        if not self.collection:
            return None
            
        with LogExecutionTime(self.logger, "Cache Lookup"):
            try:
                # We need embeddings since we are querying the raw collection directly
                query_embedding = self.embedding_service.get_embedding(query)
                
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=1,
                    include=["metadatas", "documents", "distances"]
                )
                
                if not results["documents"] or not results["documents"][0]:
                    return None
                    
                distance = results["distances"][0][0]
                similarity = 1.0 - distance
                
                if similarity >= threshold:
                    self.logger.info(f"🎯 Cache Hit! Similarity: {similarity:.3f}")
                    metadata = results["metadatas"][0][0]
                    return {
                        "query": results["documents"][0][0],
                        "answer": metadata.get("answer"),
                        "intent": metadata.get("intent", "unknown"),
                        "similarity": similarity
                    }
                    
                self.logger.info(f"Missed Cache. Highest similarity: {similarity:.3f}")
                return None
                
            except Exception as e:
                self.logger.error(f"Cache search failed: {e}")
                return None

    def add_to_cache(self, query: str, answer: str, intent: str):
        """Add a highly confident answer to the cache."""
        if not self.collection:
            return
            
        try:
            cache_id = str(uuid.uuid4())
            query_embedding = self.embedding_service.get_embedding(query)
            
            self.collection.add(
                ids=[cache_id],
                embeddings=[query_embedding],
                documents=[query],
                metadatas=[{"answer": answer, "intent": intent}]
            )
            self.logger.info("Added new QA pair to Semantic Cache")
        except Exception as e:
            self.logger.error(f"Failed to add to cache: {e}")

# Singleton instance
_semantic_cache_instance = None

def get_semantic_cache() -> SemanticCacheService:
    global _semantic_cache_instance
    if _semantic_cache_instance is None:
        _semantic_cache_instance = SemanticCacheService()
    return _semantic_cache_instance
