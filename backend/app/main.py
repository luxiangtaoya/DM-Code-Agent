"""FastAPI 主应用 - AI 自动化测试平台"""

import os
import sys
import logging
import socket
import psutil
from pathlib import Path

from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# 添加 dm_agent 路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# 导入数据库和执行服务
from app.database import get_db_connection, init_database
from app.execution_service import (
    get_task_scheduler,
    start_task_scheduler,
    get_agent_pool,
)
from app.exceptions import register_exception_handlers

# 配置全局日志
from dm_agent.logger import setup_global_logging
setup_global_logging(logging.INFO)

logger = logging.getLogger(__name__)


# ==================== 创建 FastAPI 应用 ====================

app = FastAPI(
    title="AI 自动化测试平台",
    description="基于 Agent 的智能化测试平台",
    version="1.0.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 数据目录
DATA_DIR = backend_dir / "data"
SCREENSHOT_DIR = DATA_DIR / "screenshots"

# 确保目录存在
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

# 挂载静态文件目录（用于访问 GIF 截图）
app.mount("/screenshots", StaticFiles(directory=str(SCREENSHOT_DIR)), name="screenshots")

# 导入并注册 API 路由
from app.api import api_router
app.include_router(api_router)

# 注册异常处理器
register_exception_handlers(app)


# ==================== 应用生命周期管理 ====================

def recover_pending_testcases():
    """
    重启时重置所有未完成状态的测试用例
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    recovered_count = 0

    # 重置"等待执行"状态的用例
    cursor.execute("SELECT id, name FROM test_cases WHERE status = '等待执行'")
    for row in cursor.fetchall():
        cursor.execute("UPDATE test_cases SET status = '待测试' WHERE id = ?", (row['id'],))
        recovered_count += 1
        logger.info(f"[恢复] 重置测试用例：testcase_id={row['id']}, name={row['name']}")

    # 重置"执行中"状态的用例
    cursor.execute("SELECT id, name FROM test_cases WHERE status = '执行中'")
    for row in cursor.fetchall():
        cursor.execute("UPDATE test_cases SET status = '待测试' WHERE id = ?", (row['id'],))
        recovered_count += 1
        logger.info(f"[恢复] 重置测试用例：testcase_id={row['id']}, name={row['name']}")

    # 恢复 test_executions 表中 'running' 状态的记录
    cursor.execute("SELECT id, testcase_id FROM test_executions WHERE status = 'running'")
    for row in cursor.fetchall():
        cursor.execute("""
            UPDATE test_executions
            SET status = 'pending',
                error_message = '后端重启，任务中断',
                end_time = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (row['id'],))

    conn.commit()
    conn.close()

    if recovered_count > 0:
        logger.info(f"[恢复] 共重置 {recovered_count} 条中断的测试用例为「待测试」状态")
    else:
        logger.info("[恢复] 没有需要重置的测试用例")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("应用启动中...")

    # 1. 初始化 Agent 池
    pool = get_agent_pool()
    pool.initialize()
    logger.info("Agent 资源池已初始化")

    # 2. 恢复重启前的测试用例
    recover_pending_testcases()

    # 3. 启动任务调度器（在独立线程中运行）
    start_task_scheduler(str(SCREENSHOT_DIR))
    logger.info("任务调度器已启动")

    yield  # 应用运行中

    # 关闭时清理
    logger.info("应用关闭中...")
    scheduler = get_task_scheduler()
    await scheduler.stop()
    pool = get_agent_pool()
    pool.cleanup()
    logger.info("应用已关闭")


app.router.lifespan_context = lifespan


# ==================== 端口管理工具 ====================

def check_port(port: int) -> bool:
    """检查端口是否被占用"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex(('127.0.0.1', port))
            return result == 0
    except:
        return False


def kill_process_on_port(port: int) -> bool:
    """终止占用指定端口的进程"""
    try:
        for conn in psutil.net_connections():
            if conn.laddr.port == port and conn.status == 'LISTEN':
                try:
                    process = psutil.Process(conn.pid)
                    logger.warning(f"端口 {port} 被进程 {process.name()} (PID: {conn.pid}) 占用")
                    process.terminate()
                    logger.info(f"已终止进程 {conn.pid}")
                    return True
                except psutil.NoSuchProcess:
                    logger.warning(f"进程 {conn.pid} 已不存在")
                except psutil.AccessDenied:
                    logger.error(f"无权限终止进程 {conn.pid}")
                    return False
        return False
    except Exception as e:
        logger.error(f"检查端口 {port} 时出错：{e}")
        return False


def setup_port(port: int):
    """设置端口，检查并终止占用进程"""
    if check_port(port):
        logger.warning(f"端口 {port} 已被占用，正在尝试释放...")
        if kill_process_on_port(port):
            import time
            time.sleep(2)
            if not check_port(port):
                logger.info(f"端口 {port} 已成功释放")
            else:
                logger.error(f"端口 {port} 仍被占用")
        else:
            logger.warning(f"未能自动释放端口 {port}")
    else:
        logger.info(f"端口 {port} 可用")


# ==================== 应用入口 ====================

if __name__ == "__main__":
    import uvicorn

    setup_port(8080)
    uvicorn.run(app, host="0.0.0.0", port=8080)
