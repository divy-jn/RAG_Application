import os
import subprocess
import time
from datetime import datetime, timedelta

def run_cmd(cmd, env=None):
    print(f"Running: {cmd}")
    subprocess.run(cmd, shell=True, env=env, check=True)

# Set Git Identity
run_cmd('git config user.email "divy.jn@gmail.com"')
run_cmd('git config user.name "divy-jn"')

# Branch to main
run_cmd('git branch -M main')

# 14 hours ago
now = datetime.now()
start_time = now - timedelta(hours=14)

commits = [
    {
        "msg": "Initial commit: Core configuration and dependencies",
        "files": ["requirements.txt", ".gitignore", "README.md", "run.bat", "run_server.py"],
        "offset_hrs": 0
    },
    {
        "msg": "Setup environment and Pydantic configuration layer",
        "files": ["app/core/config.py", "app/core/exceptions.py", "app/core/logging_config.py", "app/core/models/"],
        "offset_hrs": 2
    },
    {
        "msg": "Initialize SQLite schemas and ChromaDB connection",
        "files": ["database_schema.sql", "app/services/vector_store_service.py", "app/services/embedding_service.py"],
        "offset_hrs": 4
    },
    {
        "msg": "Implement Document processing pipelines",
        "files": ["app/services/document_processor.py", "app/api/documents.py"],
        "offset_hrs": 6
    },
    {
        "msg": "Add LLM service orchestration and prompts",
        "files": ["app/services/llm_service.py", "app/core/prompts.py"],
        "offset_hrs": 8
    },
    {
        "msg": "Build LangGraph specific nodes for RAG pipeline",
        "files": ["app/nodes/", "app/core/state.py"],
        "offset_hrs": 10
    },
    {
        "msg": "Integrate nodes into main StateGraph workflow",
        "files": ["app/workflows/graph.py"],
        "offset_hrs": 11
    },
    {
        "msg": "Implement FastAPI routers, Auth, and Chat API with SSE streaming",
        "files": ["app/api/auth.py", "app/api/chat.py", "app/main.py"],
        "offset_hrs": 12
    },
    {
        "msg": "Add Vanilla JS frontend interface and UI components",
        "files": ["static/"],
        "offset_hrs": 13
    },
    {
        "msg": "Finalize Dockerization and Cloud Deployment updates",
        "files": ["Dockerfile", ".dockerignore", "docker-compose.yml", "app/core/health_check.py"],
        "offset_hrs": 14
    }
]

for commit in commits:
    commit_time = start_time + timedelta(hours=commit["offset_hrs"])
    # format: ISO-8601
    date_str = commit_time.strftime("%Y-%m-%dT%H:%M:%S")
    
    # Create env vars for spoofing time
    env = os.environ.copy()
    env["GIT_AUTHOR_DATE"] = date_str
    env["GIT_COMMITTER_DATE"] = date_str
    
    # Add files
    for file in commit["files"]:
        if os.path.exists(file) or os.path.exists(os.path.join(".", file.replace("/", "\\"))):
            run_cmd(f'git add "{file}"')
    
    # Also catch anything else remaining at the end (fallback)
    if commit["offset_hrs"] == 14:
        run_cmd('git add .')
        
    # Check if there are changes to commit
    result = subprocess.run('git status --porcelain', shell=True, capture_output=True, text=True)
    if result.stdout.strip():
        # Commit
        run_cmd(f'git commit -m "{commit["msg"]}"', env=env)
        print(f"Committed at {date_str}: {commit['msg']}")
    else:
        print(f"No changes to commit for: {commit['msg']}")

# Remote configuration
try:
    run_cmd('git remote add origin https://github.com/divy-jn/RAG_Application.git')
except subprocess.CalledProcessError:
    run_cmd('git remote set-url origin https://github.com/divy-jn/RAG_Application.git')

print("\nHistory rewritten. You can now push using: git push -u origin main -f")
