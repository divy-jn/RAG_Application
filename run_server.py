import uvicorn
import sys

if __name__ == "__main__":
    sys.stdout = open("server_log.txt", "w", buffering=1)
    sys.stderr = sys.stdout
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, log_level="debug")
