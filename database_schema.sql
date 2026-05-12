-- AI Educational Document Reasoning System - Database Schema

-- Users Table
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    role VARCHAR(20) DEFAULT 'student',  -- student or teacher
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1
);

-- Documents Table
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_type VARCHAR(50) NOT NULL,  -- pdf, docx, txt
    document_type VARCHAR(50),  -- notes, marking_scheme, question_paper
    file_size INTEGER,  -- in bytes
    subject VARCHAR(100),
    topic VARCHAR(200),
    visibility VARCHAR(20) DEFAULT 'private',  -- private or public
    chunk_count INTEGER DEFAULT 0,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP,
    is_processed BOOLEAN DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Document Chunks Table (for tracking what's in ChromaDB)
CREATE TABLE IF NOT EXISTS document_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    chunk_embedding_id VARCHAR(100),  -- ChromaDB ID reference
    token_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

-- Conversations Table
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    session_id VARCHAR(100) NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Messages Table
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role VARCHAR(20) NOT NULL,  -- user or assistant
    content TEXT NOT NULL,
    intent VARCHAR(50),  -- answer_generation, evaluation, etc.
    metadata JSON,  -- stores sources, confidence, processing_time
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

-- Answer Evaluations Table (for tracking student progress)
CREATE TABLE IF NOT EXISTS answer_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    question TEXT NOT NULL,
    student_answer TEXT NOT NULL,
    score_obtained FLOAT,
    max_score FLOAT,
    evaluation_feedback TEXT,
    marking_scheme_doc_id INTEGER,
    evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (marking_scheme_doc_id) REFERENCES documents(id) ON DELETE SET NULL
);

-- Generated Questions Table
CREATE TABLE IF NOT EXISTS generated_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    question_type VARCHAR(50),  -- mcq, short, long, numerical
    question_text TEXT NOT NULL,
    difficulty_level VARCHAR(20),  -- easy, medium, hard
    marks INTEGER,
    subject VARCHAR(100),
    topic VARCHAR(200),
    source_document_ids TEXT,  -- comma-separated IDs
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Exam Papers Table
CREATE TABLE IF NOT EXISTS exam_papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title VARCHAR(200) NOT NULL,
    subject VARCHAR(100),
    total_marks INTEGER,
    duration_minutes INTEGER,
    question_ids TEXT,  -- comma-separated question IDs
    file_path VARCHAR(500),  -- path to generated PDF
    marking_scheme_path VARCHAR(500),
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Indexes for Performance
CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);
CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(document_type);
CREATE INDEX IF NOT EXISTS idx_documents_visibility ON documents(visibility);
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_evaluations_user_id ON answer_evaluations(user_id);
CREATE INDEX IF NOT EXISTS idx_questions_user_id ON generated_questions(user_id);

-- Triggers for automatic timestamp updates
CREATE TRIGGER IF NOT EXISTS update_user_timestamp 
AFTER UPDATE ON users
BEGIN
    UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;

CREATE TRIGGER IF NOT EXISTS update_conversation_timestamp 
AFTER INSERT ON messages
BEGIN
    UPDATE conversations SET last_message_at = CURRENT_TIMESTAMP 
    WHERE id = NEW.conversation_id;
END;
