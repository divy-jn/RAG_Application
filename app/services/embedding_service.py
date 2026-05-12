"""
Embedding Service
Generates vector embeddings using sentence-transformers with GPU acceleration and caching
"""
import numpy as np
from typing import List, Optional, Union, Dict, Tuple
from sentence_transformers import SentenceTransformer, CrossEncoder
import torch
from functools import lru_cache
import hashlib

from app.core.logging_config import LoggerMixin, LogExecutionTime, get_logger
from app.core.exceptions import VectorEmbeddingException
from app.core.retry_utils import retry_with_backoff
from app.core.config import settings


logger = get_logger(__name__)


class EmbeddingService(LoggerMixin):
    """
    Service for generating text embeddings
    Supports batch processing, GPU acceleration, and caching
    """
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
        batch_size: int = 32,
        enable_cache: bool = True
    ):
        """
        Initialize Embedding Service
        
        Args:
            model_name: Sentence transformer model name
            device: Device to use (cuda/cpu/mps)
            batch_size: Batch size for encoding
            enable_cache: Enable embedding caching
        """
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self.batch_size = batch_size
        self.enable_cache = enable_cache
        
        # Determine device
        if device:
            self.device = device
        else:
            self.device = self._detect_device()
        
        self.logger.info(
            f"🔢 Initializing Embedding Service | "
            f"Model: {self.model_name} | "
            f"Device: {self.device} | "
            f"Batch size: {self.batch_size}"
        )
        
        # Load model
        self.model = self._load_model()
        
        # Cross-encoder for re-ranking (lazy loaded)
        self._cross_encoder: Optional[CrossEncoder] = None
        self._cross_encoder_model_name = settings.CROSS_ENCODER_MODEL
        self._cross_encoder_enabled = settings.CROSS_ENCODER_ENABLED
        
        # Cache for embeddings (text hash -> embedding)
        self._embedding_cache: Dict[str, np.ndarray] = {}
        self._cache_hits = 0
        self._cache_misses = 0
        
        self.logger.info(
            f"Embedding Service ready | "
            f"Embedding dimension: {self.get_embedding_dimension()} | "
            f"Cross-Encoder: {'enabled' if self._cross_encoder_enabled else 'disabled'}"
        )
    
    def _detect_device(self) -> str:
        """Auto-detect best available device"""
        if settings.EMBEDDING_DEVICE == "cuda" and torch.cuda.is_available():
            device = "cuda"
            gpu_name = torch.cuda.get_device_name(0)
            self.logger.info(f"Using GPU: {gpu_name}")
        elif settings.EMBEDDING_DEVICE == "mps" and torch.backends.mps.is_available():
            device = "mps"
            self.logger.info("Using Apple Metal (MPS)")
        else:
            device = "cpu"
            self.logger.info("Using CPU")
        
        return device
    
    @retry_with_backoff(max_retries=2, exceptions=(Exception,))
    def _load_model(self) -> SentenceTransformer:
        """
        Load sentence transformer model with retry
        
        Returns:
            Loaded model
        """
        with LogExecutionTime(self.logger, f"Load model: {self.model_name}"):
            try:
                model = SentenceTransformer(self.model_name, device=self.device)
                
                # Move to device
                model.to(self.device)
                
                return model
                
            except Exception as e:
                self.logger.error(f"Failed to load model: {str(e)}", exc_info=True)
                raise VectorEmbeddingException(
                    text_sample=f"Model: {self.model_name}",
                    original_exception=e
                )
    
    def _get_text_hash(self, text: str) -> str:
        """Generate hash for text (for caching)"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def encode(
        self,
        texts: Union[str, List[str]],
        batch_size: Optional[int] = None,
        show_progress: bool = False,
        normalize_embeddings: bool = True
    ) -> np.ndarray:
        """
        Generate embeddings for text(s)
        
        Args:
            texts: Single text or list of texts
            batch_size: Batch size for processing
            show_progress: Show progress bar
            normalize_embeddings: Normalize embeddings to unit length
            
        Returns:
            Numpy array of embeddings
            
        Raises:
            VectorEmbeddingException: If embedding generation fails
        """
        # Convert single text to list
        is_single = isinstance(texts, str)
        if is_single:
            texts = [texts]
        
        batch_size = batch_size or self.batch_size
        
        self.logger.debug(
            f"🔢 Encoding {len(texts)} texts | "
            f"Batch size: {batch_size} | "
            f"Device: {self.device}"
        )
        
        with LogExecutionTime(self.logger, f"Encode {len(texts)} texts"):
            try:
                # Check cache if enabled
                if self.enable_cache:
                    embeddings, uncached_texts, uncached_indices = self._get_from_cache(texts)
                    
                    if uncached_texts:
                        # Encode uncached texts
                        new_embeddings = self._encode_batch(
                            uncached_texts,
                            batch_size,
                            show_progress,
                            normalize_embeddings
                        )
                        
                        # Update cache
                        self._update_cache(uncached_texts, new_embeddings)
                        
                        # Merge cached and new embeddings
                        for idx, emb in zip(uncached_indices, new_embeddings):
                            embeddings[idx] = emb
                    
                    self.logger.debug(
                        f"Cache stats | "
                        f"Hits: {self._cache_hits} | "
                        f"Misses: {self._cache_misses} | "
                        f"Hit rate: {self._get_cache_hit_rate():.1%}"
                    )
                else:
                    # Encode all texts without cache
                    embeddings = self._encode_batch(
                        texts,
                        batch_size,
                        show_progress,
                        normalize_embeddings
                    )
                
                # Return single embedding if input was single text
                if is_single:
                    return embeddings[0]
                
                return np.array(embeddings)
                
            except Exception as e:
                sample = texts[0] if texts else "empty"
                self.logger.error(
                    f"Embedding generation failed | Sample: {sample[:100]}",
                    exc_info=True
                )
                raise VectorEmbeddingException(
                    text_sample=sample[:100],
                    original_exception=e
                )
    
    def _encode_batch(
        self,
        texts: List[str],
        batch_size: int,
        show_progress: bool,
        normalize_embeddings: bool
    ) -> np.ndarray:
        """Internal method to encode texts in batches"""
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            normalize_embeddings=normalize_embeddings,
            device=self.device,
            convert_to_numpy=True
        )
        
        return embeddings
    
    def _get_from_cache(self, texts: List[str]) -> tuple:
        """
        Get embeddings from cache
        
        Returns:
            (embeddings, uncached_texts, uncached_indices)
        """
        embeddings = [None] * len(texts)
        uncached_texts = []
        uncached_indices = []
        
        for i, text in enumerate(texts):
            text_hash = self._get_text_hash(text)
            
            if text_hash in self._embedding_cache:
                embeddings[i] = self._embedding_cache[text_hash]
                self._cache_hits += 1
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)
                self._cache_misses += 1
        
        return embeddings, uncached_texts, uncached_indices
    
    def _update_cache(self, texts: List[str], embeddings: np.ndarray):
        """Update cache with new embeddings"""
        for text, embedding in zip(texts, embeddings):
            text_hash = self._get_text_hash(text)
            self._embedding_cache[text_hash] = embedding
    
    def _get_cache_hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total = self._cache_hits + self._cache_misses
        if total == 0:
            return 0.0
        return self._cache_hits / total
    
    def clear_cache(self):
        """Clear embedding cache"""
        cache_size = len(self._embedding_cache)
        self._embedding_cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        self.logger.info(f"Cleared {cache_size} cached embeddings")
    
    def get_embedding_dimension(self) -> int:
        """Get embedding vector dimension"""
        return self.model.get_sentence_embedding_dimension()
    
    def compute_similarity(
        self,
        text1: Union[str, np.ndarray],
        text2: Union[str, np.ndarray],
        metric: str = "cosine"
    ) -> float:
        """
        Compute similarity between two texts or embeddings
        
        Args:
            text1: First text or embedding
            text2: Second text or embedding
            metric: Similarity metric (cosine, euclidean, dot)
            
        Returns:
            Similarity score
        """
        # Get embeddings if texts provided
        emb1 = self.encode(text1) if isinstance(text1, str) else text1
        emb2 = self.encode(text2) if isinstance(text2, str) else text2
        
        if metric == "cosine":
            # Cosine similarity
            similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
        elif metric == "euclidean":
            # Euclidean distance (inverted for similarity)
            distance = np.linalg.norm(emb1 - emb2)
            similarity = 1 / (1 + distance)
        elif metric == "dot":
            # Dot product
            similarity = np.dot(emb1, emb2)
        else:
            raise ValueError(f"Unknown metric: {metric}")
        
        return float(similarity)
    
    def _get_cross_encoder(self) -> CrossEncoder:
        """Lazy-load the Cross-Encoder model on first use."""
        if self._cross_encoder is None:
            self.logger.info(f"Loading Cross-Encoder: {self._cross_encoder_model_name}")
            with LogExecutionTime(self.logger, f"Load Cross-Encoder: {self._cross_encoder_model_name}"):
                self._cross_encoder = CrossEncoder(
                    self._cross_encoder_model_name,
                    max_length=512,
                    device=self.device
                )
            self.logger.info("Cross-Encoder loaded successfully")
        return self._cross_encoder
    
    def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: Optional[int] = None
    ) -> List[Tuple[int, float, str]]:
        """
        Re-rank documents using Cross-Encoder for more accurate relevance scoring.
        
        Args:
            query: The user query
            documents: List of document texts to re-rank
            top_k: Number of top results to return (None = return all, sorted)
            
        Returns:
            List of (original_index, score, document_text) tuples, sorted by descending score
        """
        if not documents:
            return []
        
        if not self._cross_encoder_enabled:
            # Return documents in original order with dummy scores
            results = [(i, 1.0 - (i * 0.01), doc) for i, doc in enumerate(documents)]
            return results[:top_k] if top_k else results
        
        self.logger.info(f"Re-ranking {len(documents)} documents against query")
        
        with LogExecutionTime(self.logger, f"Cross-Encoder re-rank {len(documents)} docs"):
            cross_encoder = self._get_cross_encoder()
            
            # Create (query, document) pairs for scoring
            pairs = [[query, doc] for doc in documents]
            
            # Get relevance scores
            scores = cross_encoder.predict(pairs)
            
            # Combine with original indices
            scored_docs = [
                (i, float(score), doc)
                for i, (score, doc) in enumerate(zip(scores, documents))
            ]
            
            # Sort by score descending
            scored_docs.sort(key=lambda x: x[1], reverse=True)
            
            if top_k:
                scored_docs = scored_docs[:top_k]
            
            self.logger.info(
                f"Re-ranking complete | "
                f"Top score: {scored_docs[0][1]:.4f} | "
                f"Bottom score: {scored_docs[-1][1]:.4f}"
            )
            
            return scored_docs
    
    def get_stats(self) -> Dict[str, any]:
        """Get service statistics"""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "embedding_dimension": self.get_embedding_dimension(),
            "cross_encoder_model": self._cross_encoder_model_name,
            "cross_encoder_enabled": self._cross_encoder_enabled,
            "cross_encoder_loaded": self._cross_encoder is not None,
            "cache_enabled": self.enable_cache,
            "cache_size": len(self._embedding_cache),
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate": self._get_cache_hit_rate(),
            "batch_size": self.batch_size
        }


# Singleton instance
_embedding_service_instance: Optional[EmbeddingService] = None



def set_embedding_service_override(service: EmbeddingService):
    """Override the global instance (for testing)"""
    global _embedding_service_instance
    _embedding_service_instance = service


def get_embedding_service() -> EmbeddingService:
    """
    Get or create embedding service singleton.
    Compatible with FastAPI Depends.
    """
    global _embedding_service_instance
    
    if _embedding_service_instance is None:
        _embedding_service_instance = EmbeddingService()
    
    return _embedding_service_instance


if __name__ == "__main__":
    # Test embedding service
    embedding_service = EmbeddingService()
    
    # Test single text
    text = "This is a test sentence."
    embedding = embedding_service.encode(text)
    print(f"Single embedding shape: {embedding.shape}")
    
    # Test batch
    texts = [
        "First sentence.",
        "Second sentence.",
        "Third sentence."
    ]
    embeddings = embedding_service.encode(texts)
    print(f"Batch embeddings shape: {embeddings.shape}")
    
    # Test similarity
    similarity = embedding_service.compute_similarity(texts[0], texts[1])
    print(f"Similarity: {similarity:.4f}")
    
    # Test cache (encode same text again)
    embedding2 = embedding_service.encode(text)
    print(f"Cache hit: {np.allclose(embedding, embedding2)}")
    
    # Print stats
    stats = embedding_service.get_stats()
    print(f"\nStats:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
