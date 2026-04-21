"""测试执行服务 - 兼容层

为保持向后兼容，所有实际功能已迁移到 execution 子模块
"""

# 从新模块导入，保持向后兼容
from app.execution.agent_pool import AgentPool, get_agent_pool
from app.execution.agent_executor import ExecutionResult, Step, run_agent_in_thread
from app.execution.task_scheduler import (
    TaskScheduler,
    get_task_scheduler,
    start_task_scheduler,
    execute_testcase as execute_single_testcase,
)
from app.execution.db_updater import update_testcase_status

# 日志配置（保持原有行为）
import logging
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "execution.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_logs() -> str:
    """获取执行日志"""
    log_file = LOG_DIR / "execution.log"
    if log_file.exists():
        with open(log_file, 'r', encoding='utf-8') as f:
            return f.read()
    return ""


__all__ = [
    "AgentPool",
    "get_agent_pool",
    "ExecutionResult",
    "Step",
    "run_agent_in_thread",
    "TaskScheduler",
    "get_task_scheduler",
    "start_task_scheduler",
    "execute_single_testcase",
    "update_testcase_status",
    "get_logs",
    "logger",
]
