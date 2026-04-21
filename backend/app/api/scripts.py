"""脚本回放 API"""

import os
import subprocess
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.api import api_router

# 数据目录
backend_dir = Path(__file__).parent.parent.parent
DATA_DIR = backend_dir / "data"


@api_router.post("/scripts/execute")
async def execute_script(request: dict):
    """执行 Playwright 回放脚本"""

    script_path = request.get("script_path", "")
    if not script_path:
        raise HTTPException(status_code=400, detail="缺少 script_path 参数")

    if script_path.startswith("/screenshots/"):
        abs_script_path = str(DATA_DIR) + script_path
    else:
        raise HTTPException(status_code=400, detail="无效的脚本路径")

    if not os.path.exists(abs_script_path):
        raise HTTPException(status_code=404, detail=f"脚本文件不存在：{script_path}")

    result_holder = {"status": "running", "output": "", "error": ""}

    def run_script():
        try:
            proc = subprocess.Popen(
                ["node", abs_script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                cwd=str(DATA_DIR),
            )
            stdout, stderr = proc.communicate(timeout=120)
            result_holder["status"] = "success" if proc.returncode == 0 else "failed"
            result_holder["output"] = stdout
            result_holder["error"] = stderr
            result_holder["exit_code"] = proc.returncode
        except subprocess.TimeoutExpired:
            proc.kill()
            result_holder["status"] = "timeout"
            result_holder["error"] = "脚本执行超时（120 秒）"
        except FileNotFoundError:
            result_holder["status"] = "failed"
            result_holder["error"] = "未找到 node 命令，请确保已安装 Node.js"
        except Exception as e:
            result_holder["status"] = "failed"
            result_holder["error"] = str(e)

    thread = threading.Thread(target=run_script, daemon=True)
    thread.start()
    thread.join(timeout=130)

    if thread.is_alive():
        return {
            "status": "timeout",
            "output": "",
            "error": "脚本执行超时"
        }

    return {
        "status": result_holder["status"],
        "output": result_holder.get("output", ""),
        "error": result_holder.get("error", ""),
        "exit_code": result_holder.get("exit_code", -1)
    }
