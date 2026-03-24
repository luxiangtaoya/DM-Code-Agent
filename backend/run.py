"""启动AI自动化测试平台后端服务"""

import os
import sys
from pathlib import Path

# 添加backend目录到Python路径
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
load_dotenv()

if __name__ == "__main__":
    import uvicorn

    print("🚀 启动AI自动化测试平台后端服务...")
    print("📡 API地址: http://localhost:8000")
    print("📚 API文档: http://localhost:8000/docs")
    print("🔧 WebSocket: ws://localhost:8000/api/v1/ws/executions/{execution_id}")
    print()

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
