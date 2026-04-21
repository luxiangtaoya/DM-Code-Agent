"""任务调度器模块 - 顺序执行测试用例"""

import asyncio
import json
import logging
import threading
import uuid
from datetime import datetime
from typing import Optional

from app.database import get_db_connection
from app.execution.agent_executor import run_agent_in_thread, ExecutionResult
from app.execution.db_updater import update_testcase_status

logger = logging.getLogger(__name__)


# 全局调度器实例
_task_scheduler: Optional["TaskScheduler"] = None
_scheduler_thread: Optional[threading.Thread] = None


def get_task_scheduler() -> "TaskScheduler":
    """获取全局任务调度器"""
    global _task_scheduler
    if _task_scheduler is None:
        _task_scheduler = TaskScheduler()
    return _task_scheduler


def start_task_scheduler(screenshot_dir: str):
    """在独立线程中启动任务调度器（不阻塞主线程）

    Args:
        screenshot_dir: 截图保存目录
    """
    global _scheduler_thread

    scheduler = get_task_scheduler()

    def run_in_thread():
        """在线程中运行异步调度器"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def start():
            await scheduler.start()
            await scheduler.run_loop(screenshot_dir)

        try:
            loop.run_until_complete(start())
        except Exception as e:
            logger.error(f"[TaskScheduler] 线程运行异常：{e}")
        finally:
            loop.close()

    # 在后台线程启动
    _scheduler_thread = threading.Thread(target=run_in_thread, daemon=True)
    _scheduler_thread.start()
    logger.info("[TaskScheduler] 已在后台线程启动")


class TaskScheduler:
    """任务调度器 - 顺序执行，支持动态添加任务"""

    def __init__(self):
        self.is_running = False
        self.current_task: Optional[int] = None  # 当前正在执行的任务 ID

    async def start(self):
        """启动调度器"""
        self.is_running = True
        logger.info("[TaskScheduler] 调度器已启动")

    async def stop(self):
        """停止调度器"""
        self.is_running = False
        logger.info("[TaskScheduler] 调度器已停止")

    async def run_loop(self, screenshot_dir: str):
        """主循环 - 每 5 秒轮询一次

        Args:
            screenshot_dir: 截图保存目录
        """
        while self.is_running:
            try:
                await self._check_and_execute(screenshot_dir)
            except Exception as e:
                logger.error(f"[TaskScheduler] 执行异常：{e}")

            await asyncio.sleep(5)  # 每 5 秒检查一次

    async def _check_and_execute(self, screenshot_dir: str):
        """检查并执行任务

        Args:
            screenshot_dir: 截图保存目录
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        # 如果有任务正在执行，跳过
        if self.current_task is not None:
            conn.close()
            return

        # 查询"等待执行"的用例（按 created_at 排序，先来的先执行）
        cursor.execute("""
            SELECT id, project_id, name, steps, expected_result, description, precondition, execution_options
            FROM test_cases
            WHERE status = '等待执行'
            ORDER BY created_at ASC
            LIMIT 1
        """)

        testcase = cursor.fetchone()
        conn.close()

        if not testcase:
            return

        testcase_id = testcase['id']
        testcase_name = testcase['name']

        # 更新状态为"执行中"，防止重复执行
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE test_cases
            SET status = '执行中'
            WHERE id = ?
        """, (testcase_id,))
        conn.commit()
        conn.close()

        logger.info(f"[TaskScheduler] 开始执行：testcase_id={testcase_id}, name={testcase_name}")

        # 标记当前任务
        self.current_task = testcase_id

        # 准备执行参数
        exec_options = {}
        try:
            testcase_dict = dict(testcase) if testcase else {}
            options_str = testcase_dict.get('execution_options')
            if options_str:
                exec_options = json.loads(options_str) if isinstance(options_str, str) else options_str
            logger.info(f"[TaskScheduler] 执行选项：{exec_options}")
        except Exception as e:
            logger.warning(f"[TaskScheduler] 解析执行选项失败：{e}")

        request = {
            "model": exec_options.get("model", "qwen3.5-flash"),
            "provider": exec_options.get("provider", "qwen"),
            "options": {
                "enable_screenshots": exec_options.get("enable_screenshots", True),
                "enable_network_trace": exec_options.get("enable_network_trace", False),
                "enable_script": exec_options.get("enable_script", True),
            }
        }

        execution_id = None
        try:
            # 创建执行记录
            execution_id = str(uuid.uuid4())
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO test_executions (id, project_id, testcase_id, status, model, provider, start_time)
                VALUES (?, ?, ?, 'running', ?, ?, CURRENT_TIMESTAMP)
            """, (
                execution_id,
                testcase['project_id'],
                testcase_id,
                request.get('model', 'qwen3.5-flash'),
                request.get('provider', 'qwen')
            ))
            conn.commit()
            conn.close()

            # 执行测试用例
            result = await execute_testcase(
                testcase_id=testcase_id,
                testcase=dict(testcase),
                request=request,
                screenshot_dir=screenshot_dir,
                execution_id=execution_id
            )

            logger.info(f"[TaskScheduler] 执行完成：testcase_id={testcase_id}, status={result.exec_status}")

        except Exception as e:
            logger.error(f"[TaskScheduler] 执行异常：testcase_id={testcase_id}, {e}")

            # 执行失败，更新状态
            update_testcase_status(
                testcase_id=testcase_id,
                exec_status="执行失败",
                steps=[],
                gif_path=None,
                script_path=None,
                final_answer=None,
                error_message=str(e),
                execution_id=execution_id
            )

        finally:
            # 清除当前任务标记
            self.current_task = None


async def execute_testcase(
    testcase_id: int,
    testcase: dict,
    request: dict,
    screenshot_dir: str,
    execution_id: Optional[str] = None
) -> ExecutionResult:
    """执行单个测试用例

    Args:
        testcase_id: 测试用例 ID
        testcase: 测试用例数据
        request: 执行请求参数
        screenshot_dir: 截图目录
        execution_id: 执行记录 ID

    Returns:
        ExecutionResult 执行结果
    """
    import os
    from pathlib import Path
    from dotenv import load_dotenv

    # 加载环境变量
    backend_dir = Path(screenshot_dir).parent.parent  # 根据路径推断
    env_file = backend_dir / '.env'
    load_dotenv(dotenv_path=env_file)

    # 获取 API key
    api_key = os.getenv("API_KEY")
    if not api_key:
        logger.error(f"[执行] API key 未配置，无法执行：{testcase['name']}")
        return ExecutionResult(
            exec_status="执行失败",
            steps=[],
            gif_path=None,
            script_path=None,
            final_answer=None,
            error_message="API key 未配置"
        )

    base_url = os.getenv("BASE_URL", "")
    logger.info(f"[执行] 开始执行：testcase_id={testcase_id}, name={testcase['name']}")

    # 执行测试
    exec_id = execution_id or str(uuid.uuid4())
    result = run_agent_in_thread(
        execution_id=exec_id,
        testcase_id=testcase_id,
        testcase_name=testcase['name'],
        test_case=testcase,
        model=request.get("model", "qwen3.5-flash"),
        provider=request.get("provider", "qwen"),
        api_key=api_key,
        base_url=base_url,
        screenshot_dir=screenshot_dir,
        options=request.get("options", {})
    )

    # 更新数据库
    update_testcase_status(
        testcase_id=testcase_id,
        exec_status=result.exec_status,
        steps=result.steps,
        gif_path=result.gif_path,
        script_path=result.script_path,
        final_answer=result.final_answer,
        error_message=result.error_message,
        execution_id=exec_id,
        network_path=result.network_path
    )

    logger.info(f"[执行] 执行完成：testcase_id={testcase_id}, status={result.exec_status}")

    return result
