@echo off
cd "c:\building projs\RAG AI Application"
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)
echo Starting RAG AI Application (Cloud LLM)...
python run_server.py
pause
