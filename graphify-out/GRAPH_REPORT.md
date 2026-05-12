# Graph Report - RAG AI Application  (2026-05-06)

## Corpus Check
- 39 files · ~170,259 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 703 nodes · 1155 edges · 61 communities (48 shown, 13 thin omitted)
- Extraction: 82% EXTRACTED · 18% INFERRED · 0% AMBIGUOUS · INFERRED: 207 edges (avg confidence: 0.66)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 59|Community 59]]

## God Nodes (most connected - your core abstractions)
1. `LogExecutionTime` - 40 edges
2. `OllamaLLMService` - 26 edges
3. `DocumentProcessor` - 22 edges
4. `VectorStoreService` - 22 edges
5. `EmbeddingService` - 21 edges
6. `DocumentRetriever` - 20 edges
7. `QuestionGenerator` - 18 edges
8. `AnswerEvaluator` - 16 edges
9. `WorkflowNodeException` - 15 edges
10. `AnswerGenerator` - 14 edges

## Surprising Connections (you probably didn't know these)
- `lifespan()` --calls--> `setup_logging()`  [INFERRED]
  app/main.py → app/core/logging_config.py
- `lifespan()` --calls--> `ensure_directories()`  [INFERRED]
  app/main.py → app/core/config.py
- `lifespan()` --calls--> `get_llm_service()`  [INFERRED]
  app/main.py → app/services/llm_service.py
- `health_check()` --calls--> `get_system_health()`  [INFERRED]
  app/main.py → app/core/health_check.py
- `get_stats()` --calls--> `get_vector_store()`  [INFERRED]
  app/main.py → app/services/vector_store_service.py

## Communities (61 total, 13 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (56): ensure_directories(), Environment, LogLevel, Enhanced Configuration System Provides validated, type-safe configuration with e, Application environment, Ensure all required directories exist     Creates directories if they don't exis, Validate configuration and check dependencies     Raises exceptions if configura, validate_chunk_overlap() (+48 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (51): cache_stats(), ChatRequest, ChatResponse, clear_cache(), ConversationResponse, create_conversation(), delete_conversation(), ensure_title_column() (+43 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (34): DocumentParsingException, DocumentTooLargeException, InvalidDocumentFormatException, Raised when document format is not supported, Raised when document exceeds size limit, Raised when document parsing fails, LoggerMixin, Mixin class to add logging capability to any class (+26 more)

### Community 3 - "Community 3"
Cohesion: 0.08
Nodes (21): Raised when a workflow node fails, WorkflowNodeException, DoubtResolver, Doubt resolution node. Handles conceptual question answering using retrieved doc, Generate an answer strictly from the provided document context., Reject the query and instruct the user to upload relevant documents., Apply header and footer formatting based on the answer source., LangGraph node entry point for doubt resolution. (+13 more)

### Community 4 - "Community 4"
Cohesion: 0.08
Nodes (19): Raised when vector search fails, VectorSearchException, _initialize_client(), Vector Store Service - ChromaDB Integration Manages document embeddings and sema, Get existing collection or create new one, Search for similar documents                  Args:             query: Search qu, Format ChromaDB search results into cleaner structure, Service for managing vector embeddings in ChromaDB     Provides document storage (+11 more)

### Community 5 - "Community 5"
Cohesion: 0.09
Nodes (18): generate_questions_node(), QuestionGenerator, Question Generation Node Generates practice questions (MCQ, short, long) from up, Parse question generation request from query                  Returns:, Generate questions using LLM                  Returns:             List of quest, Build prompt for MCQ generation, Build prompt for short answer questions, Build prompt for long answer questions (+10 more)

### Community 6 - "Community 6"
Cohesion: 0.11
Nodes (26): create_access_token(), forgot_password(), get_current_user(), get_current_user_info(), get_db(), get_password_hash(), get_user_by_id(), get_user_by_username() (+18 more)

### Community 7 - "Community 7"
Cohesion: 0.12
Nodes (24): delete_document(), get_db(), get_document(), list_documents(), process_document_internal(), Documents API Router Handles document upload, processing, and management, Update document processing status, Upload and process a document          Args:         file: Document file to uplo (+16 more)

### Community 8 - "Community 8"
Cohesion: 0.11
Nodes (14): AnswerEvaluator, evaluate_answer_node(), Answer Evaluation Node Evaluates student answers using semantic similarity with, Extract question and student answer from query                  Returns:, Extract marking scheme section from context, Parse marking scheme into individual points                  Returns:, Evaluate using semantic similarity                  Args:             student_an, Evaluates student answers against marking schemes using semantic similarity (+6 more)

### Community 9 - "Community 9"
Cohesion: 0.13
Nodes (15): GraphState, RetrievedDocument, DocumentRetriever, Document Retrieval Node Retrieves relevant document chunks based on user query a, Enhance query with intent-specific context and conversation history, Retrieves relevant documents from vector store based on query and intent, Re-rank filtered results using Cross-Encoder for higher accuracy., Retrieve documents of specific types                  Args:             state: C (+7 more)

### Community 10 - "Community 10"
Cohesion: 0.13
Nodes (13): AnswerGenerator, generate_answer_node(), Answer Generation Node Generates exam-oriented answers based on marking schemes, Extract the actual question from the query                  Args:             qu, Build prompt when marking scheme is available, Build prompt when only notes are available, Get system prompt for answer generation, Get system prompt for answer generation (+5 more)

### Community 11 - "Community 11"
Cohesion: 0.14
Nodes (12): AuthenticationException, InvalidCredentialsException, Base class for authentication-related exceptions, Raised when user credentials are invalid, Raised when authentication token has expired, Raised when authentication token is invalid, Raised when user is not found, Raised when attempting to create a user that already exists (+4 more)

### Community 12 - "Community 12"
Cohesion: 0.14
Nodes (12): create_initial_state(), get_workflow(), process_query(), process_user_query(), LangGraph workflow orchestration. Builds and executes the stateful AI pipeline f, Extract and structure the final response from the completed graph state., Return metadata about the workflow's available nodes and intents., Return the singleton workflow orchestrator instance. (+4 more)

### Community 13 - "Community 13"
Cohesion: 0.15
Nodes (11): ColoredFormatter, get_logger(), JSONFormatter, log_function_call(), Advanced Logging Configuration Provides structured logging with rotation, differ, Custom JSON formatter for structured logging, Get a logger instance with the given name          Args:         name: Logger na, Decorator to log function calls with execution time          Args:         log_a (+3 more)

### Community 14 - "Community 14"
Cohesion: 0.2
Nodes (12): LLMConnectionException, Raised when connection to LLM fails, chat(), check_model_availability(), generate(), _generate_with_protection(), get_llm_service(), LLM Service - Ollama Integration Provides robust interface to Ollama with retry (+4 more)

### Community 15 - "Community 15"
Cohesion: 0.14
Nodes (13): custom_exception_handler(), general_exception_handler(), health_check(), Application entry point and FastAPI server configuration. Defines middleware, ex, Service metadata and status., Detailed health check including database, LLM, and vector store status., Lightweight liveness probe., Serve the frontend application (+5 more)

### Community 16 - "Community 16"
Cohesion: 0.16
Nodes (11): Retry and Fallback Utilities Provides robust retry mechanisms with exponential b, Decorator for retry logic with exponential backoff          Args:         max_re, Decorator to add timeout to function execution          Args:         timeout_se, Retry decorator specifically for connection errors, Retry decorator specifically for LLM errors, retry_on_connection_error(), retry_on_llm_error(), retry_with_backoff() (+3 more)

### Community 17 - "Community 17"
Cohesion: 0.19
Nodes (9): InvalidWorkflowStateException, MissingDocumentsException, Custom Exception Hierarchy Provides specific exceptions for different error scen, Base class for workflow exceptions, Raised when workflow state is invalid, Raised when user intent cannot be determined, Raised when required documents are not available, UnknownIntentException (+1 more)

### Community 18 - "Community 18"
Cohesion: 0.15
Nodes (8): BaseSettings, Application settings with validation     Automatically loads from environment va, Get list of supported file formats, Get maximum upload size in bytes, Check if running in production, Check if running in development, Configure LangSmith tracing by setting environment variables.         Must be ca, Settings

### Community 19 - "Community 19"
Cohesion: 0.18
Nodes (7): OllamaLLMService, Generate with fallback to default response if all retries fail, Generate streaming text using Ollama                  Yields:              Text, Service for interacting with Ollama LLM     Includes retry logic, circuit breake, Chat completion with streaming, Async context manager entry, Async context manager exit

### Community 20 - "Community 20"
Cohesion: 0.19
Nodes (7): CircuitBreaker, Circuit breaker pattern implementation     Prevents cascading failures by tempor, Args:             failure_threshold: Number of failures before opening circuit, Execute function with circuit breaker protection, Check if enough time has passed to attempt recovery, Handle successful call, Initialize Ollama LLM Service                  Args:             base_url: Ollam

### Community 21 - "Community 21"
Cohesion: 0.2
Nodes (6): Generate hash for text (for caching), Generate embeddings for text(s)                  Args:             texts: Single, Internal method to encode texts in batches, Get embeddings from cache                  Returns:             (embeddings, unc, Update cache with new embeddings, Compute similarity between two texts or embeddings                  Args:

### Community 22 - "Community 22"
Cohesion: 0.18
Nodes (8): LLMException, LLMGenerationException, LLMModelNotFoundException, LLMRateLimitException, Base class for LLM-related exceptions, Raised when LLM model is not found, Raised when LLM generation fails, Raised when LLM rate limit is exceeded

### Community 23 - "Community 23"
Cohesion: 0.2
Nodes (5): LogExecutionTime, Context manager to log execution time of code blocks, Lazy-load the Cross-Encoder model on first use., Re-rank documents using Cross-Encoder for more accurate relevance scoring., Add documents to vector store                  Args:             documents: List

### Community 24 - "Community 24"
Cohesion: 0.18
Nodes (7): LoggerMixin, Store a query-response pair in the semantic cache.                  Args:, Clear all cached entries., Get cache statistics., Semantic caching using ChromaDB.     Stores query-response pairs and retrieves, Check if a semantically similar query exists in cache.                  Args:, SemanticCacheService

### Community 25 - "Community 25"
Cohesion: 0.18
Nodes (8): get_stats(), Retrieve vector store and embedding service statistics., Semantic Cache Service Caches query-response pairs in ChromaDB for instant resp, get_embedding_service(), Embedding Service Generates vector embeddings using sentence-transformers with G, Override the global instance (for testing), Get or create embedding service singleton.     Compatible with FastAPI Depends., set_embedding_service_override()

### Community 26 - "Community 26"
Cohesion: 0.24
Nodes (6): EmbeddingService, Service for generating text embeddings     Supports batch processing, GPU accele, Calculate cache hit rate, Clear embedding cache, Get embedding vector dimension, Get service statistics

### Community 27 - "Community 27"
Cohesion: 0.25
Nodes (6): DocumentException, DocumentNotFoundException, DocumentUploadException, Base class for document-related exceptions, Raised when document upload fails, Raised when document is not found

### Community 28 - "Community 28"
Cohesion: 0.25
Nodes (6): DatabaseConnectionException, DatabaseException, DatabaseQueryException, Base class for database exceptions, Raised when database connection fails, Raised when database query fails

### Community 29 - "Community 29"
Cohesion: 0.25
Nodes (7): Workflow Router Determines which node to execute next based on intent and state, Route to appropriate node after intent classification          Args:         sta, Route to task-specific node after document retrieval          Args:         stat, Determine if workflow should continue or end          Args:         state: Curre, route_after_intent(), route_after_retrieval(), should_continue()

### Community 30 - "Community 30"
Cohesion: 0.25
Nodes (5): Raised when vector embedding generation fails, VectorEmbeddingException, _load_model(), Initialize Embedding Service                  Args:             model_name: Sent, Auto-detect best available device

### Community 31 - "Community 31"
Cohesion: 0.25
Nodes (5): LLMTimeoutException, Raised when LLM request times out, Safe execution wrapper with multiple protection layers     Combines retry, circu, Execute function with all protection layers                  Args:             f, SafeExecutor

### Community 32 - "Community 32"
Cohesion: 0.33
Nodes (3): BaseAppException, Base exception class for all application exceptions, Convert exception to dictionary for API responses

### Community 33 - "Community 33"
Cohesion: 0.4
Nodes (4): Base class for vector store exceptions, Raised when connection to vector store fails, VectorStoreConnectionException, VectorStoreException

### Community 34 - "Community 34"
Cohesion: 0.4
Nodes (4): ConfigurationException, MissingConfigException, Base class for configuration exceptions, Raised when required configuration is missing

### Community 35 - "Community 35"
Cohesion: 0.5
Nodes (4): lifespan(), Application lifespan manager for startup and shutdown events., close_llm_service(), Close the global LLM service instance

## Knowledge Gaps
- **298 isolated node(s):** `Application entry point and FastAPI server configuration. Defines middleware, ex`, `Application lifespan manager for startup and shutdown events.`, `Handle application-specific exceptions with structured error responses.`, `Catch-all handler for unexpected server errors.`, `Service metadata and status.` (+293 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `LogExecutionTime` connect `Community 23` to `Community 2`, `Community 3`, `Community 4`, `Community 5`, `Community 7`, `Community 8`, `Community 9`, `Community 10`, `Community 12`, `Community 13`, `Community 14`, `Community 19`, `Community 21`, `Community 24`, `Community 26`, `Community 30`?**
  _High betweenness centrality (0.283) - this node is a cross-community bridge._
- **Why does `OllamaLLMService` connect `Community 19` to `Community 1`, `Community 2`, `Community 14`, `Community 20`, `Community 22`, `Community 23`, `Community 24`, `Community 31`?**
  _High betweenness centrality (0.142) - this node is a cross-community bridge._
- **Why does `DocumentRetriever` connect `Community 9` to `Community 0`, `Community 1`, `Community 3`, `Community 23`?**
  _High betweenness centrality (0.088) - this node is a cross-community bridge._
- **Are the 35 inferred relationships involving `LogExecutionTime` (e.g. with `AnswerEvaluator` and `AnswerGenerator`) actually correct?**
  _`LogExecutionTime` has 35 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `OllamaLLMService` (e.g. with `ChatRequest` and `ChatResponse`) actually correct?**
  _`OllamaLLMService` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `DocumentProcessor` (e.g. with `LoggerMixin` and `LogExecutionTime`) actually correct?**
  _`DocumentProcessor` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `VectorStoreService` (e.g. with `Settings` and `LoggerMixin`) actually correct?**
  _`VectorStoreService` has 6 INFERRED edges - model-reasoned connections that need verification._