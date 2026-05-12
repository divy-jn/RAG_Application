"""
Vector Store Service - ChromaDB Integration
Manages document embeddings and semantic search with ChromaDB
"""
import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import List, Dict, Any, Optional, Tuple
import uuid
from pathlib import Path

from app.core.logging_config import LoggerMixin, LogExecutionTime, get_logger
from app.core.exceptions import (
    VectorStoreConnectionException,
    VectorSearchException,
    VectorEmbeddingException
)
from app.core.retry_utils import retry_with_backoff
from app.core.config import settings
from .embedding_service import get_embedding_service


logger = get_logger(__name__)


class VectorStoreService(LoggerMixin):
    """
    Service for managing vector embeddings in ChromaDB
    Provides document storage, retrieval, and semantic search
    """
    
    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: Optional[str] = None,
        distance_metric: str = "cosine"
    ):
        """
        Initialize Vector Store Service
        
        Args:
            persist_directory: Directory for ChromaDB persistence
            collection_name: Name of the collection
            distance_metric: Distance metric (cosine, l2, ip)
        """
        self.persist_directory = persist_directory or settings.CHROMA_PERSIST_DIRECTORY
        self.collection_name = collection_name or settings.CHROMA_COLLECTION_NAME
        self.distance_metric = distance_metric
        
        # Create persist directory
        Path(self.persist_directory).mkdir(parents=True, exist_ok=True)
        
        self.logger.info(
            f"🗄️ Initializing Vector Store | "
            f"Path: {self.persist_directory} | "
            f"Collection: {self.collection_name} | "
            f"Metric: {self.distance_metric}"
        )
        
        # Initialize ChromaDB client
        self.client = self._initialize_client()
        
        # Get or create collection
        self.collection = self._get_or_create_collection()
        
        # Get embedding service
        self.embedding_service = get_embedding_service()
        
        count = self.collection.count()
        self.logger.info(
            f"Vector Store ready | "
            f"Documents: {count} | "
            f"Embedding dim: {self.embedding_service.get_embedding_dimension()}"
        )
    
    @retry_with_backoff(max_retries=2, exceptions=(Exception,))
    def _initialize_client(self) -> chromadb.PersistentClient:
        """
        Initialize ChromaDB client with retry
        
        Returns:
            ChromaDB client
        """
        with LogExecutionTime(self.logger, "Initialize ChromaDB client"):
            try:
                client = chromadb.PersistentClient(
                    path=self.persist_directory,
                    settings=ChromaSettings(
                        anonymized_telemetry=False,
                        allow_reset=True
                    )
                )
                
                # Test connection
                client.heartbeat()
                
                return client
                
            except Exception as e:
                self.logger.error(f"Failed to initialize ChromaDB: {str(e)}", exc_info=True)
                raise VectorStoreConnectionException(
                    reason=f"ChromaDB initialization failed",
                    original_exception=e
                )
    
    def _get_or_create_collection(self):
        """Get existing collection or create new one"""
        with LogExecutionTime(self.logger, f"Get/create collection: {self.collection_name}"):
            try:
                collection = self.client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": self.distance_metric}
                )
                
                return collection
                
            except Exception as e:
                self.logger.error(f"Collection operation failed: {str(e)}", exc_info=True)
                raise VectorStoreConnectionException(
                    reason="Collection creation/retrieval failed",
                    original_exception=e
                )
    
    def add_documents(
        self,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
        batch_size: int = 100
    ) -> List[str]:
        """
        Add documents to vector store
        
        Args:
            documents: List of document texts
            metadatas: List of metadata dicts for each document
            ids: Optional list of document IDs
            batch_size: Batch size for processing
            
        Returns:
            List of document IDs
        """
        if not documents:
            self.logger.warning("No documents to add")
            return []
        
        # Generate IDs if not provided
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in documents]
        
        # Generate default metadata if not provided
        if metadatas is None:
            metadatas = [{} for _ in documents]
        
        self.logger.info(
            f"Adding {len(documents)} documents | "
            f"Batch size: {batch_size}"
        )
        
        with LogExecutionTime(self.logger, f"Add {len(documents)} documents"):
            try:
                # Generate embeddings
                with LogExecutionTime(self.logger, f"Generate embeddings for {len(documents)} docs"):
                    embeddings = self.embedding_service.encode(
                        documents,
                        batch_size=batch_size,
                        show_progress=len(documents) > 100
                    )
                
                # Add to ChromaDB in batches
                for i in range(0, len(documents), batch_size):
                    batch_end = min(i + batch_size, len(documents))
                    
                    self.collection.add(
                        embeddings=embeddings[i:batch_end].tolist(),
                        documents=documents[i:batch_end],
                        metadatas=metadatas[i:batch_end],
                        ids=ids[i:batch_end]
                    )
                    
                    self.logger.debug(
                        f"✓ Added batch {i//batch_size + 1} | "
                        f"Docs {i}-{batch_end}"
                    )
                
                self.logger.info(
                    f"Added {len(documents)} documents | "
                    f"Total in collection: {self.collection.count()}"
                )
                
                return ids
                
            except Exception as e:
                self.logger.error(f"Failed to add documents: {str(e)}", exc_info=True)
                raise VectorStoreConnectionException(
                    reason="Document addition failed",
                    original_exception=e
                )
    
    def search(
        self,
        query: str,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, str]] = None,
        include: List[str] = ["documents", "metadatas", "distances"]
    ) -> Dict[str, Any]:
        """
        Search for similar documents
        
        Args:
            query: Search query text
            n_results: Number of results to return
            where: Metadata filter
            where_document: Document content filter
            include: Fields to include in results
            
        Returns:
            Search results with documents, metadata, and distances
        """
        self.logger.debug(
            f"Searching | Query: '{query[:100]}' | "
            f"Results: {n_results}"
        )
        
        with LogExecutionTime(self.logger, f"Search query ({len(query)} chars)"):
            try:
                # Generate query embedding
                query_embedding = self.embedding_service.encode(query)
                
                # Search in ChromaDB
                results = self.collection.query(
                    query_embeddings=[query_embedding.tolist()],
                    n_results=n_results,
                    where=where,
                    where_document=where_document,
                    include=include
                )
                
                num_results = len(results.get('ids', [[]])[0])
                self.logger.info(
                    f"Search complete | Found {num_results} results"
                )
                
                # Format results
                formatted_results = self._format_search_results(results)
                
                return formatted_results
                
            except Exception as e:
                self.logger.error(f"Search failed: {str(e)}", exc_info=True)
                raise VectorSearchException(
                    query=query[:100],
                    original_exception=e
                )
    
    def _format_search_results(self, raw_results: Dict) -> Dict[str, Any]:
        """Format ChromaDB search results into cleaner structure"""
        if not raw_results or not raw_results.get('ids'):
            return {
                'results': [],
                'count': 0
            }
        
        # Extract first result list (ChromaDB returns nested lists)
        ids = raw_results['ids'][0] if raw_results.get('ids') else []
        documents = raw_results['documents'][0] if raw_results.get('documents') else []
        metadatas = raw_results['metadatas'][0] if raw_results.get('metadatas') else []
        distances = raw_results['distances'][0] if raw_results.get('distances') else []
        
        # Combine into result objects
        results = []
        for i in range(len(ids)):
            result = {
                'id': ids[i],
                'document': documents[i] if i < len(documents) else None,
                'metadata': metadatas[i] if i < len(metadatas) else {},
                'distance': distances[i] if i < len(distances) else None,
                'similarity': 1 - distances[i] if i < len(distances) else None
            }
            results.append(result)
        
        return {
            'results': results,
            'count': len(results)
        }
    
    def search_by_metadata(
        self,
        metadata_filter: Dict[str, Any],
        n_results: int = 10
    ) -> Dict[str, Any]:
        """
        Search documents by metadata only (no semantic search)
        
        Args:
            metadata_filter: Metadata filter criteria
            n_results: Number of results
            
        Returns:
            Matching documents
        """
        self.logger.debug(f"Metadata search | Filter: {metadata_filter}")
        
        try:
            results = self.collection.get(
                where=metadata_filter,
                limit=n_results,
                include=["documents", "metadatas"]
            )
            
            return self._format_get_results(results)
            
        except Exception as e:
            self.logger.error(f"Metadata search failed: {str(e)}", exc_info=True)
            raise VectorSearchException(
                query=str(metadata_filter),
                original_exception=e
            )
    
    def _format_get_results(self, raw_results: Dict) -> Dict[str, Any]:
        """Format ChromaDB get results"""
        ids = raw_results.get('ids', [])
        documents = raw_results.get('documents', [])
        metadatas = raw_results.get('metadatas', [])
        
        results = []
        for i in range(len(ids)):
            result = {
                'id': ids[i],
                'document': documents[i] if i < len(documents) else None,
                'metadata': metadatas[i] if i < len(metadatas) else {}
            }
            results.append(result)
        
        return {
            'results': results,
            'count': len(results)
        }
    
    def delete_documents(self, ids: List[str]) -> bool:
        """
        Delete documents by IDs
        
        Args:
            ids: List of document IDs to delete
            
        Returns:
            True if successful
        """
        self.logger.info(f"Deleting {len(ids)} documents")
        
        try:
            self.collection.delete(ids=ids)
            self.logger.info(f"Deleted {len(ids)} documents")
            return True
            
        except Exception as e:
            self.logger.error(f"Delete failed: {str(e)}", exc_info=True)
            return False
    
    def update_metadata(
        self,
        ids: List[str],
        metadatas: List[Dict[str, Any]]
    ) -> bool:
        """
        Update metadata for documents
        
        Args:
            ids: Document IDs
            metadatas: New metadata for each document
            
        Returns:
            True if successful
        """
        self.logger.info(f"Updating metadata for {len(ids)} documents")
        
        try:
            self.collection.update(
                ids=ids,
                metadatas=metadatas
            )
            self.logger.info(f"Updated metadata for {len(ids)} documents")
            return True
            
        except Exception as e:
            self.logger.error(f"Metadata update failed: {str(e)}", exc_info=True)
            return False
    
    def get_document_count(self) -> int:
        """Get total number of documents in collection"""
        return self.collection.count()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics"""
        return {
            "collection_name": self.collection_name,
            "persist_directory": self.persist_directory,
            "distance_metric": self.distance_metric,
            "document_count": self.get_document_count(),
            "embedding_dimension": self.embedding_service.get_embedding_dimension()
        }
    
    def reset_collection(self) -> bool:
        """
        Delete all documents in collection
        WARNING: This is irreversible!
        """
        self.logger.warning("Resetting collection - all data will be deleted!")
        
        try:
            self.client.delete_collection(self.collection_name)
            self.collection = self._get_or_create_collection()
            self.logger.info("Collection reset complete")
            return True
            
        except Exception as e:
            self.logger.error(f"Reset failed: {str(e)}", exc_info=True)
            return False


# Singleton instance
_vector_store_instance: Optional[VectorStoreService] = None



def set_vector_store_override(service: VectorStoreService):
    """Override the global instance (for testing)"""
    global _vector_store_instance
    _vector_store_instance = service


def get_vector_store() -> VectorStoreService:
    """
    Get or create vector store singleton.
    Compatible with FastAPI Depends.
    """
    global _vector_store_instance
    
    if _vector_store_instance is None:
        _vector_store_instance = VectorStoreService()
    
    return _vector_store_instance


if __name__ == "__main__":
    # Test vector store
    vector_store = VectorStoreService()
    
    # Add test documents
    documents = [
        "Machine learning is a subset of artificial intelligence.",
        "Deep learning uses neural networks with multiple layers.",
        "Natural language processing helps computers understand human language."
    ]
    
    metadatas = [
        {"topic": "ML", "type": "definition"},
        {"topic": "DL", "type": "definition"},
        {"topic": "NLP", "type": "definition"}
    ]
    
    ids = vector_store.add_documents(documents, metadatas)
    print(f"Added {len(ids)} documents")
    
    # Search
    results = vector_store.search("What is deep learning?", n_results=2)
    print(f"\nSearch results:")
    for result in results['results']:
        print(f"  - {result['document'][:80]}...")
        print(f"    Similarity: {result['similarity']:.4f}")
    
    # Get stats
    stats = vector_store.get_stats()
    print(f"\nStats: {stats}")
