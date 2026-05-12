# AI Study Assistant

An intelligent study companion that lets you upload your notes, question papers, and marking schemes — then ask questions, get explanations, evaluate answers, and generate practice exams using AI.

Built with **FastAPI**, **LangGraph**, **Ollama**, **ChromaDB**, and a single-page **HTML/CSS/JS** frontend.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green?logo=fastapi)
![LangGraph](https://img.shields.io/badge/LangGraph-Workflow-orange)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## Features

- **Document Upload & Processing** — Upload PDF, DOCX, TXT, PPTX files. Content is chunked, embedded, and stored in ChromaDB for semantic retrieval.
- **Intent Classification** — Automatically detects what you want: answer generation, doubt clarification, answer evaluation, question generation, or exam paper creation.
- **Answer Generation** — Generates exam-oriented answers based on your uploaded marking schemes and notes.
- **Doubt Resolution** — Ask conceptual questions and get answers grounded in your uploaded notes.
- **Answer Evaluation** — Submit your answers and get them graded against marking schemes with point-wise feedback.
- **Question Generation** — Generate MCQs, short-answer, and long-answer practice questions from your study materials.
- **Streaming Responses** — Real-time token-by-token streaming via Server-Sent Events.
- **Conversation History** — Full conversation persistence with sidebar navigation and auto-generated titles.
- **Multi-Model Support** — Switch between any Ollama model at runtime.
- **Authentication** — JWT-based auth with registration, login, and password reset.

---

## Architecture

```
User Query
    │
    ▼
┌──────────────────┐
│ Intent Classifier │  ← Rule-based + LLM fallback
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Document Retriever│  ← ChromaDB semantic search
└────────┬─────────┘
         │
    ┌────┴────┬──────────┬────────────┐
    ▼         ▼          ▼            ▼
 Answer    Doubt      Answer      Question
Generator  Resolver  Evaluator   Generator
```

The workflow is orchestrated by **LangGraph** as a stateful directed graph with conditional routing.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, Uvicorn |
| AI Orchestration | LangGraph (StateGraph) |
| LLM | Ollama (Mistral, Llama, etc.) |
| Embeddings | Sentence-Transformers (MiniLM) |
| Vector Store | ChromaDB |
| Database | SQLite |
| Auth | JWT + bcrypt |
| Frontend | Vanilla HTML/CSS/JS (Single Page App) |

---

## Quick Start

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) installed and running
- A model pulled (e.g., `ollama pull mistral`)

### Installation

```bash
# Clone the repository
git clone https://github.com/divy-jn/AI_Study_Assistant.git
cd AI_Study_Assistant

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the project root:

```env
SECRET_KEY=your-secret-key-here
OLLAMA_MODEL=mistral
DATABASE_URL=sqlite:///./data/sqlite.db
```

### Run

```bash
# Start Ollama (if not already running)
ollama serve

# Start the application
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000/app` in your browser.

---

## Project Structure

```
├── app/
│   ├── main.py                 # FastAPI app entry point
│   ├── api/
│   │   ├── auth.py             # Authentication endpoints
│   │   ├── chat.py             # Chat & streaming endpoints
│   │   └── documents.py        # Document upload & management
│   ├── core/
│   │   ├── config.py           # Application settings
│   │   ├── state.py            # LangGraph state definitions
│   │   ├── prompts.py          # All LLM prompts
│   │   ├── exceptions.py       # Custom exception classes
│   │   └── models/             # Pydantic models
│   ├── nodes/
│   │   ├── intent_classifier.py
│   │   ├── document_retriever.py
│   │   ├── answer_generator.py
│   │   ├── answer_evaluator.py
│   │   ├── doubt_resolver.py
│   │   ├── question_generator.py
│   │   └── router.py           # Conditional routing logic
│   ├── services/
│   │   ├── llm_service.py      # Ollama LLM client
│   │   ├── embedding_service.py
│   │   ├── vector_store_service.py
│   │   └── document_processor.py
│   └── workflows/
│       └── graph.py            # LangGraph orchestration
├── static/
│   └── index.html              # Frontend SPA
├── scripts/                    # Setup & utility scripts
├── database_schema.sql         # SQLite schema
├── requirements.txt
└── .env                        # Environment variables
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/register` | Register new user |
| `POST` | `/api/auth/login` | Login and get JWT token |
| `POST` | `/api/auth/forgot-password` | Verify identity for password reset |
| `POST` | `/api/auth/reset-password` | Reset password with token |
| `GET` | `/api/auth/me` | Get current user info |
| `POST` | `/api/documents/upload` | Upload and process a document |
| `GET` | `/api/documents/` | List user's documents |
| `DELETE` | `/api/documents/{id}` | Delete a document |
| `POST` | `/api/chat/stream` | Stream a query response (SSE) |
| `POST` | `/api/chat/query` | Non-streaming query |
| `GET` | `/api/chat/conversations` | List conversations |
| `GET` | `/health` | System health check |

---

## License

This project is licensed under the MIT License.
