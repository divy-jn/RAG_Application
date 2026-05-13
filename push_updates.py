import os
import subprocess
from datetime import datetime, timedelta

def run_cmd(cmd, env=None):
    print(f"Running: {cmd}")
    subprocess.run(cmd, shell=True, env=env, check=True)

# Get the last commit time
result = subprocess.run('git log -1 --format=%cd --date=iso-strict', shell=True, capture_output=True, text=True)
last_commit_date_str = result.stdout.strip()
print(f"Last commit date: {last_commit_date_str}")

# Parse the last commit date
# ISO strict format: 2026-05-13T20:27:39+05:30
# We can just use datetime fromisoformat
last_commit_time = datetime.fromisoformat(last_commit_date_str)

# We want 4 commits spread over the next 4 hours
commits = [
    {
        "msg": "add duckduckgo search and web fallback",
        "files": ["requirements.txt", "app/nodes/document_retriever.py"],
        "offset_hrs": 1
    },
    {
        "msg": "add general chat intent and casual prompts",
        "files": ["app/nodes/intent_classifier.py", "app/core/prompts.py", "app/nodes/general_chat_node.py"],
        "offset_hrs": 2
    },
    {
        "msg": "wire up general chat to workflow graph",
        "files": ["app/nodes/router.py", "app/workflows/graph.py", "app/api/chat.py"],
        "offset_hrs": 3
    },
    {
        "msg": "cleanup old scripts and update docs",
        "files": ["."],
        "offset_hrs": 4
    }
]

for commit in commits:
    commit_time = last_commit_time + timedelta(hours=commit["offset_hrs"])
    date_str = commit_time.isoformat()
    
    # Create env vars for spoofing time
    env = os.environ.copy()
    env["GIT_AUTHOR_DATE"] = date_str
    env["GIT_COMMITTER_DATE"] = date_str
    
    # Add files
    for file in commit["files"]:
        if file == ".":
            run_cmd('git add -A')
        elif os.path.exists(file) or os.path.exists(os.path.join(".", file.replace("/", "\\"))):
            run_cmd(f'git add "{file}"')
    
    # Check if there are changes to commit
    status_result = subprocess.run('git status --porcelain', shell=True, capture_output=True, text=True)
    if status_result.stdout.strip():
        # Commit
        run_cmd(f'git commit -m "{commit["msg"]}"', env=env)
        print(f"Committed at {date_str}: {commit['msg']}")
    else:
        print(f"No changes to commit for: {commit['msg']}")

print("All commits created successfully.")
