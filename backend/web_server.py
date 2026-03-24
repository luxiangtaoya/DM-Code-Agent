"""启动 Web 服务器"""

import sys
import os
import io

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv

load_dotenv()

from dm_agent.web import app

if __name__ == "__main__":
    import uvicorn

    print("Starting DM Code Agent Web Server...")
    print("URL: http://localhost:8888")
    print("API Docs: http://localhost:8888/docs")
    print()

    uvicorn.run(
        "dm_agent.web.app:app",
        host="0.0.0.0",
        port=8888,
        reload=False,
        log_level="info"
    )
