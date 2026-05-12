"""
Semantic Cache Service
Caches query-response pairs in ChromaDB for instant responses to similar questions.
"""
import chromadb
from chromadb.config import Settings as ChromaSettings
import uuid
import json
import time
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime, timedelta

from app.core.logging_config import LoggerMixin, LogExecutionTime, get_logger
from app.core.config import settings
from .embedding_service import get_embedding_service


logger = get_logger(__name__)


class SemanticCacheService(LoggerMixin):
    """
    Semantic caching using ChromaDB.
    Stores query-response pairs and retrieves cached answers for semantically similar queries.
    """
    
    def __init__(self):
        self.enabled = settings.SEMANTIC_CACHE_ENABLED
        self.threshold = settings.SEMANTIC_CACHE_THRESHOLD
        self.ttl_hours = settings.SEMANTIC_CACHE_TTL_HOURS
        self.collection_name = settings.SEMANTIC_CACHE_COLLECTION
        
        if not self.enabled:
            self.logger.info("Semantic Cache is disabled")
            return
        
        self.logger.info(
            f"Initializing Semantic Cache | "
            f"Collection: {self.collection_name} | "
            f"Threshold: {self.threshold} | "
            f"TTL: {self.ttl_hours}h"
        )
        
        # Reuse ChromaDB persistence directory
        persist_dir = settings.CHROMA_PERSIST_DIRECTORY
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        
        self.client = chromadb.PersistentClient(
            path=persist_dir,
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        
        self.embedding_service = get_embedding_service()
        
        # Stats
        self._hits = 0
        self._misses = 0
        
        count = self.collection.count()
        self.logger.info(f"Semantic Cache ready | {count} cached entries")
    
    def check_cache(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Check if a semantically similar query exists in cache.
        
        Args:
            query: The user's query
            
        Returns:
            Cached response dict if hit, None if miss
        """
        if not self.enabled:
            return None
        
        try:
            with LogExecutionTime(self.logger, "Semantic cache lookup"):
                # Embed the query
                query_embedding = self.embedding_service.encode(query)
                
                # Search for similar cached queries
                results = self.collection.query(
                    query_embeddings=[query_embedding.tolist()],
                    n_results=1,
                    include=["documents", "metadatas", "distances"]
                )
                
                # Check if we got a result
                if not results["ids"] or not results["ids"][0]:
                    self._misses += 1
                    return None
                
                distance = results["distances"][0][0]
                # Cosine similarity = 1 - (cosine distance / 2)
                similarity = 1.0 - (distance / 2.0)
                
                metadata = results["metadatas"][0][0]
                cached_query = results["documents"][0][0]
                
                # Check similarity threshold
                if similarity < self.threshold:
                    self._misses += 1
                    self.logger.debug(
                        f"Cache miss (similarity {similarity:.3f} < {self.threshold}) | "
                        f"Cached: '{cached_query[:50]}' vs Query: '{query[:50]}'"
                    )
                    return None
                
                # Check TTL
                cached_at = metadata.get("cached_at", "")
                if cached_at:
                    cached_time = datetime.fromisoformat(cached_at)
                    if datetime.utcnow() - cached_time > timedelta(hours=self.ttl_hours):
                        self._misses += 1
                        self.logger.info(f"Cache entry expired (TTL {self.ttl_hours}h)")
                        # Clean up expired entry
                        self.collection.delete(ids=[results["ids"][0][0]])
                        return None
                
                # Cache hit!
                self._hits += 1
                
                # Parse the cached response
                cached_response = json.loads(metadata.get("response_json", "{}"))
                
                self.logger.info(
                    f"✅ Cache HIT | Similarity: {similarity:.3f} | "
                    f"Query: '{query[:60]}'"
                )
                
                return cached_response
                
        except Exception as e:
            self.logger.warning(f"Semantic cache check failed: {e}")
            self._misses += 1
            return None
    
    def store_cache(
        self,
        query: str,
        response: Dict[str, Any],
        intent: str = ""
    ):
        """
        Store a query-response pair in the semantic cache.
        
        Args:
            query: The original user query
            response: The full response dict to cache
            intent: The classified intent (for metadata)
        """
        if not self.enabled:
            return
        
        try:
            # Embed the query
            query_embedding = self.embedding_service.encode(query)
            
            # Serialize the response
            response_json = json.dumps(response, default=str)
            
            # Store in ChromaDB
            self.collection.add(
                embeddings=[query_embedding.tolist()],
                documents=[query],
                metadatas=[{
                    "response_json": response_json,
                    "intent": intent,
                    "cached_at": datetime.utcnow().isoformat(),
                    "query_length": len(query)
                }],
                ids=[str(uuid.uuid4())]
            )
            
            self.logger.info(
                f"Cached response | Query: '{query[:60]}' | Intent: {intent}"
            )
            
        except Exception as e:
            self.logger.warning(f"Failed to cache response: {e}")
    
    def clear_cache(self):
        """Clear all cached entries."""
        try:
            self.client.delete_collection(self.collection_name)
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            self._hits = 0
            self._misses = 0
            self.logger.info("Semantic cache cleared")
        except Exception as e:
            self.logger.warning(f"Failed to clear cache: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        return {
            "enabled": self.enabled,
            "collection": self.collection_name,
            "cached_entries": self.collection.count() if self.enabled else 0,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{(self._hits / total * 100):.1f}%" if total > 0 else "N/A",
            "threshold": self.threshold,
            "ttl_hours": self.ttl_hours
        }


# Singleton
_cache_service_instance: Optional[SemanticCacheService] = None


def get_cache_service() -> SemanticCacheService:
    """Get or create the semantic cache singleton."""
    global _cache_service_instance
    if _cache_service_instance is None:
        _cache_service_instance = SemanticCacheService()
    return _cache_service_instance
