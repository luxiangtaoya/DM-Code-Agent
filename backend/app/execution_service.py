"""测试执行服务 - 简化版（仅记录执行结果）"""

import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from threading import Thread

from dotenv import load_dotenv

from dm_agent import ReactAgent, create_llm_client, default_tools
from dm_agent.mcp import MCPManager, load_mcp_config
from dm_agent.screenshot import ScreenshotManager

# 加载环境变量（指定 .env 文件路径）
backend_dir = Path(__file__).parent.parent
env_file = backend_dir / '.env'
load_dotenv(dotenv_path=env_file)

# 配置日志
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


# ==================== 数据模型 ====================

@dataclass
class Step:
    """表示智能体的一个推理步骤"""
    thought: str                 # 智能体的思考过程
    step_abbreviation: str       # 步骤的简单描述，用于标识和跟踪进度
    action: str                  # 要执行的动作/工具名称
    action_input: Any            # 动作的输入参数
    observation: str             # 执行动作后的观察结果
    raw: str = ""                # 原始响应内容


@dataclass
class ExecutionResult:
    """执行结果"""
    exec_status: str             # "执行通过"/"执行不通过"/"执行失败"
    steps: List[Step]            # 执行步骤列表
    gif_path: Optional[str]      # GIF 路径
    final_answer: Optional[str]  # 最终答案
    error_message: Optional[str] = None  # 错误信息


# ==================== 全局状态 ====================

# 全局 Agent 池（单例模式）
_agent_pool = None


def get_agent_pool():
    """获取全局 Agent 池"""
    global _agent_pool
    if _agent_pool is None:
        _agent_pool = AgentPool()
    return _agent_pool


class AgentPool:
    """Agent 资源池 - 单例模式"""

    def __init__(self):
        self.mcp_manager = None
        self.mcp_config = None
        self.tools = None
        self._initialized = False

    def initialize(self):
        """初始化资源池（只调用一次）"""
        if self._initialized:
            return

        # 初始化 MCP
        self.mcp_config = load_mcp_config()
        self.mcp_manager = MCPManager(self.mcp_config)
        self.mcp_manager.start_all()

        # 获取工具
        mcp_tools = self.mcp_manager.get_tools()
        self.tools = default_tools(include_mcp=True, mcp_tools=mcp_tools)

        self._initialized = True
        logger.info("[AgentPool] 资源池已初始化")

    def get_client(self, provider: str, api_key: str, model: str, base_url: str):
        """获取 LLM 客户端"""
        return create_llm_client(
            provider=provider,
            api_key=api_key,
            model=model,
            base_url=base_url
        )

    def cleanup(self):
        """清理资源"""
        if self.mcp_manager:
            self.mcp_manager.stop_all()
        self._initialized = False


def run_agent_in_thread(
    execution_id: str,
    testcase_id: int,
    testcase_name: str,
    test_case: dict,
    model: str,
    provider: str,
    api_key: str,
    base_url: str,
    screenshot_dir: str,
) -> ExecutionResult:
    """在独立线程中运行 Agent，返回 ExecutionResult"""
    logger.info(f"[Agent] 开始执行：{testcase_name} (execution_id={execution_id})")

    steps_log: List[Step] = []
    gif_path = None

    try:
        # 初始化资源池
        pool = get_agent_pool()
        pool.initialize()

        # 获取客户端和工具
        client = pool.get_client(provider=provider, api_key=api_key, model=model, base_url=base_url)
        tools = pool.tools

        logger.info(f"[Agent] LLM 客户端已获取：{provider}/{model}")

        # 创建截图管理器
        task_screenshot_dir = os.path.join(screenshot_dir, execution_id)
        os.makedirs(task_screenshot_dir, exist_ok=True)

        screenshot_manager = ScreenshotManager(
            output_dir=screenshot_dir,  # 直接使用 screenshots 根目录
            enable_gif=True,
            gif_duration=1000
        )
        # 使用 execution_id 作为任务ID，目录结构：screenshots/execution_id/
        screenshot_manager.start_task(execution_id)
        logger.info(f"[Agent] 截图管理器已初始化：{task_screenshot_dir}")

        # 创建步骤回调函数，收集步骤信息
        def step_callback(step_num: int, step: Any) -> None:
            # 收集步骤信息（不记录日志，避免重复）
            step_info = Step(
                thought=getattr(step, 'thought', ''),
                step_abbreviation=getattr(step, 'step_abbreviation', ''),
                action=getattr(step, 'action', ''),
                action_input=getattr(step, 'action_input', ''),
                observation=getattr(step, 'observation', ''),
                raw=getattr(step, 'raw', '')
            )
            steps_log.append(step_info)

            # 截图逻辑
            if screenshot_manager and pool.mcp_manager:
                try:
                    playwright_client = pool.mcp_manager.clients.get("playwright")
                    if playwright_client and playwright_client.is_running():
                        screenshot_result = playwright_client.call_tool("browser_take_screenshot", {})

                        if screenshot_result:
                            path_match = re.search(r'\[Screenshot[^\]]*\]\(([^\)]+)\)', str(screenshot_result))

                            if path_match:
                                screenshot_path = path_match.group(1)
                                try:
                                    import base64
                                    with open(screenshot_path, 'rb') as f:
                                        image_data = f.read()

                                    base64_data = base64.b64encode(image_data).decode('utf-8')
                                    saved_path = screenshot_manager.add_screenshot_from_base64(
                                        step.step_abbreviation,
                                        base64_data
                                    )
                                    logger.info(f"[Agent] 截图已保存：{saved_path}")
                                except Exception as e:
                                    logger.error(f"[Agent] 截图保存失败：{e}")
                except Exception as e:
                    logger.error(f"[Agent] 截图失败：{e}")

        # 创建 Agent
        agent = ReactAgent(
            client,
            tools,
            max_steps=30,
            temperature=0.3,
            step_callback=step_callback,
            enable_planning=False,
            enable_compression=True
        )

        # 处理 steps
        steps = test_case.get("steps", [])
        if isinstance(steps, str):
            try:
                steps = json.loads(steps)
            except:
                steps = steps.split('\n') if steps else ["1. 打开应用"]

        # 构建任务描述
        task_description = f"""执行以下任务：{chr(10).join([f'{i+1}. {step}' for i, step in enumerate(steps)])}"""

        # 执行任务
        logger.info(f"[Agent] 开始执行任务...")
        result = agent.run(task_description)

        # 生成 GIF
        if screenshot_manager:
            gif_path = screenshot_manager.finish_task()
            logger.info(f"[Agent] GIF 已生成：{gif_path}")

        # 关闭浏览器（如果 playwright 正在运行）
        close_browser_if_running(pool)

        # name和steps和expected_result组成
        


        # name和steps和expected_result组成
        task_description = f"""任务名称：{test_case.get("name", "")}
任务描述：{test_case.get("steps", "")}
预期结果：{test_case.get("expected_result", "")}"""

        # 调用大模型判断是否通过
        exec_status, judged_answer = judge_execution_result(
            client=client,
            task_description=task_description,
            steps=steps_log
        )

        logger.info(f"[Agent] 任务完成：状态={exec_status}, 共执行 {len(steps_log)} 步")

        return ExecutionResult(
            exec_status=exec_status,
            steps=steps_log,
            gif_path=gif_path,
            final_answer=judged_answer
        )

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"[Agent] 执行失败：{e}\n{error_trace}")

        # 关闭浏览器（即使任务失败也要清理）
        close_browser_if_running(pool)

        return ExecutionResult(
            exec_status="执行失败",
            steps=steps_log,
            gif_path=gif_path,
            final_answer=None,
            error_message=str(e)
        )


# ==================== 辅助函数 ====================

def close_browser_if_running(pool):
    """
    关闭 playwright MCP 打开的浏览器页面

    注意：这只关闭 playwright MCP 自己打开的浏览器实例，不会影响系统中其他浏览器。

    Args:
        pool: AgentPool 实例，包含 mcp_manager
    """
    if pool.mcp_manager:
        try:
            playwright_client = pool.mcp_manager.clients.get("playwright")
            if playwright_client and playwright_client.is_running():
                # 先列出所有标签页，然后逐个关闭
                try:
                    tabs_result = playwright_client.call_tool("browser_tabs", {"action": "list"})
                    logger.debug(f"[Agent] 当前标签页: {tabs_result}")

                    # 关闭所有标签页
                    tabs = playwright_client.call_tool("browser_tabs", {"action": "list"})
                    # 如果有标签页，尝试关闭
                    close_result = playwright_client.call_tool("browser_close", {})
                    logger.info(f"[Agent] Playwright 浏览器页面已关闭")
                except Exception as e:
                    # 如果列出标签页失败，直接尝试关闭
                    try:
                        close_result = playwright_client.call_tool("browser_close", {})
                        logger.info(f"[Agent] Playwright 浏览器页面已关闭")
                    except Exception as e2:
                        logger.debug(f"[Agent] 关闭 Playwright 页面失败（可能已经关闭）：{e2}")
        except Exception as e:
            logger.debug(f"[Agent] 关闭 Playwright 浏览器失败：{e}")


def judge_execution_result(
    client,
    task_description: str,
    steps: List[Step],
) -> tuple:
    """
    调用大模型判断执行结果

    Returns:
        (exec_status, judged_answer):
        - exec_status: "执行通过" / "执行不通过" / "执行失败"
        - judged_answer: 大模型的判断说明
    """
    try:
        # 构建步骤摘要
        steps_summary = "\n".join([
            f"{i+1}. {step.step_abbreviation}\n"
            f"   思考：{step.thought}\n"
            f"   动作：{step.action}\n"
            f"   观察：{step.observation}\n"
            for i, step in enumerate(steps)
        ])

        # 构建判断提示
        judge_prompt = f"""你是一个测试评审专家，请根据以下信息判断测试用例是否通过：

【测试任务描述】
{task_description}

【执行步骤】
{steps_summary}

请分析以上信息，判断测试用例是否通过。判断标准：
1. 如果执行步骤完整，且结果符合预期，返回"执行通过"
2. 如果执行步骤完整，但结果不符合预期，返回"执行不通过"
3. 如果执行过程中出现错误或未完成，返回"执行失败"

请严格按照以下 JSON 格式返回：
{{
    "exec_status": "执行通过/执行不通过/执行失败",
    "reason": "判断理由说明"
}}
"""

        # 调用大模型
        response = client.complete(
            messages=[
                {"role": "system", "content": "你是一个专业的测试评审专家，负责判断测试用例的执行结果。"},
                {"role": "user", "content": judge_prompt}
            ],
            temperature=0.3
        )

        result_text = client.extract_text(response)

        # 解析结果
        try:
            result_json = json.loads(result_text)
            exec_status = result_json.get("exec_status", "执行失败")
            reason = result_json.get("reason", "")
        except:
            # 如果解析失败，尝试从文本中提取
            if "执行通过" in result_text:
                exec_status = "执行通过"
            elif "执行不通过" in result_text:
                exec_status = "执行不通过"
            elif "执行失败" in result_text:
                exec_status = "执行失败"
            else:
                exec_status = "执行失败"
            reason = result_text

        judged_answer = f"【AI 判断结果】{exec_status}\n【判断理由】{reason}"
        logger.info(f"[AI 判断] 结果：{exec_status}, 理由：{reason[:100]}...")

        return exec_status, judged_answer

    except Exception as e:
        logger.error(f"[AI 判断] 失败：{e}")
        # 降级处理：根据 final_answer 简单判断
        if "通过" in final_answer or "成功" in final_answer or "符合预期" in final_answer:
            return "执行通过", f"【降级判断】执行通过（基于 final_answer 关键词）"
        else:
            return "执行不通过", f"【降级判断】执行不通过（基于 final_answer 关键词）"


def update_testcase_status(
    testcase_id: int,
    exec_status: str,
    steps: List[Step],
    gif_path: Optional[str] = None,
    final_answer: Optional[str] = None,
    error_message: Optional[str] = None,
    execution_id: Optional[str] = None
):
    """更新测试用例状态到数据库"""
    try:
        from app.database import get_db_connection

        # 序列化 steps 为 JSON
        steps_json = json.dumps([asdict(step) for step in steps], ensure_ascii=False) if steps else "[]"

        # 将 GIF 路径转换为相对路径（用于前端访问）
        # 原始路径：E:\data\competition\DM-Code-Agent\backend\data\screenshots\<execution_id>\task_animation.gif
        # 相对路径：/screenshots/<execution_id>/task_animation.gif
        relative_gif_path = None
        if gif_path:
            # 使用 Path 处理路径，统一使用正斜杠
            from pathlib import Path
            gif_path_obj = Path(gif_path)
            # 查找 screenshots 目录
            try:
                screenshots_idx = gif_path_obj.parts.index('screenshots')
                # 从 screenshots 开始截取
                relative_parts = gif_path_obj.parts[screenshots_idx:]
                # 拼接路径，确保以 / 开头
                relative_gif_path = '/' + '/'.join(relative_parts).replace('\\', '/')
            except ValueError:
                # 如果找不到 screenshots，直接使用原路径（转换分隔符）
                relative_gif_path = str(gif_path).replace('\\', '/')
                # 如果不是以 / 开头，添加 /
                if not relative_gif_path.startswith('/'):
                    relative_gif_path = '/' + relative_gif_path

        # 计算耗时（独立查询，避免持有锁太久）
        duration = None
        if execution_id:
            conn_calc = get_db_connection()
            cursor_calc = conn_calc.cursor()
            cursor_calc.execute("SELECT start_time FROM test_executions WHERE id = ?", (execution_id,))
            row = cursor_calc.fetchone()
            conn_calc.close()
            if row and row['start_time']:
                try:
                    from datetime import datetime
                    start_str = str(row['start_time'])
                    # 处理各种时间格式
                    if 'T' in start_str:
                        start_str = start_str.replace('T', ' ').replace('Z', '')
                    if '.' in start_str:
                        start_str = start_str.split('.')[0]
                    start = datetime.strptime(start_str, '%Y-%m-%d %H:%M:%S')
                    # 使用 utcnow() 与 start_time 的 UTC 时间一致
                    duration = int((datetime.utcnow() - start).total_seconds())
                    logger.debug(f"[DB] 计算耗时：start={start}, now_utc={datetime.utcnow()}, duration={duration}s")
                except Exception as e:
                    logger.warning(f"[DB] 计算耗时失败：{e}")
                    duration = None

        # 获取当前日期
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")

        # 使用事务快速更新
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # 先更新 test_cases 表
            cursor.execute("""
                UPDATE test_cases
                SET status = ?,
                    gif_path = ?,
                    tester = ?,
                    test_date = ?
                WHERE id = ?
            """, (exec_status, relative_gif_path, "AI", today, testcase_id))

            # 立即提交以释放写锁（test_cases 的更新）
            conn.commit()

            # 然后更新 test_executions 表
            if execution_id:
                cursor.execute("""
                    UPDATE test_executions
                    SET status = ?,
                        result = ?,
                        gif_path = ?,
                        error_message = ?,
                        steps_log = ?,
                        end_time = CURRENT_TIMESTAMP,
                        duration = ?,
                        final_answer = ?
                    WHERE id = ?
                """, (
                    'completed' if exec_status in ['执行通过', '执行不通过'] else 'failed',
                    'passed' if exec_status == '执行通过' else 'failed',
                    relative_gif_path,
                    error_message,
                    steps_json,
                    duration,
                    final_answer,
                    execution_id
                ))
            else:
                # 如果没有 execution_id，更新最新的一条
                cursor.execute("""
                    UPDATE test_executions
                    SET status = ?,
                        result = ?,
                        gif_path = ?,
                        error_message = ?,
                        steps_log = ?,
                        end_time = CURRENT_TIMESTAMP,
                        duration = ?,
                        final_answer = ?
                    WHERE testcase_id = ?
                    ORDER BY start_time DESC
                    LIMIT 1
                """, (
                    'completed' if exec_status in ['执行通过', '执行不通过'] else 'failed',
                    'passed' if exec_status == '执行通过' else 'failed',
                    relative_gif_path,
                    error_message,
                    steps_json,
                    duration,
                    final_answer,
                    testcase_id
                ))

            conn.commit()

        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

        logger.info(f"[DB] 测试用例状态已更新：testcase_id={testcase_id}, execution_id={execution_id}, status={exec_status}")

    except Exception as e:
        logger.error(f"[DB] 更新测试用例状态失败：{e}")


# ==================== 任务调度器 ====================

class TaskScheduler:
    """任务调度器 - 顺序执行，支持动态添加任务"""

    def __init__(self):
        self.is_running = False
        self.current_task = None  # 当前正在执行的任务 ID

    async def start(self):
        """启动调度器"""
        self.is_running = True
        logger.info("[TaskScheduler] 调度器已启动")

    async def stop(self):
        """停止调度器"""
        self.is_running = False
        logger.info("[TaskScheduler] 调度器已停止")

    async def run_loop(self, screenshot_dir: str):
        """主循环 - 每 5 秒轮询一次"""
        while self.is_running:
            try:
                await self._check_and_execute(screenshot_dir)
            except Exception as e:
                logger.error(f"[TaskScheduler] 执行异常：{e}")

            await asyncio.sleep(5)  # 每 5 秒检查一次

    async def _check_and_execute(self, screenshot_dir: str):
        """检查并执行任务"""
        from app.database import get_db_connection

        conn = get_db_connection()
        cursor = conn.cursor()

        # 如果有任务正在执行，跳过
        if self.current_task is not None:
            conn.close()
            return

        # 查询"等待执行"的用例（按 created_at 排序，先来的先执行）
        cursor.execute("""
            SELECT id, project_id, name, steps, expected_result, description, precondition
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
        request = {
            "model": "qwen3.5-flash",
            "provider": "qwen"
        }

        try:
            # 创建执行记录
            execution_id = str(uuid.uuid4())
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO test_executions (id, project_id, testcase_id, status, model, provider, start_time)
                VALUES (?, ?, ?, 'running', ?, ?, CURRENT_TIMESTAMP)
            """, (execution_id, testcase['project_id'], testcase_id, request.get('model', 'qwen3.5-flash'), request.get('provider', 'qwen')))
            conn.commit()
            conn.close()

            # 执行测试用例
            result = await execute_single_testcase(
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
                final_answer=None,
                error_message=str(e),
                execution_id=execution_id
            )

        finally:
            # 清除当前任务标记
            self.current_task = None


# 全局调度器实例
_task_scheduler = None


def get_task_scheduler():
    """获取全局任务调度器"""
    global _task_scheduler
    if _task_scheduler is None:
        _task_scheduler = TaskScheduler()
    return _task_scheduler


def start_task_scheduler(screenshot_dir: str):
    """启动任务调度器"""
    scheduler = get_task_scheduler()

    async def start():
        await scheduler.start()
        await scheduler.run_loop(screenshot_dir)

    # 在后台运行
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start())


# ==================== API 函数 ====================

def update_execution_to_db(execution_id: str, status: str, result: str = None,
                           gif_path: str = None, final_answer: str = None,
                           error_message: str = None):
    """更新执行记录到数据库"""
    try:
        from app.database import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()

        # 计算耗时
        duration = None
        cursor.execute("SELECT start_time FROM test_executions WHERE id = ?", (execution_id,))
        row = cursor.fetchone()
        if row and row['start_time']:
            try:
                start_str = row['start_time'].replace('Z', '').replace('T', ' ')
                start = datetime.strptime(start_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
                # 使用 utcnow() 与 start_time 的 UTC 时间一致
                duration = int((datetime.utcnow() - start).total_seconds())
            except:
                duration = None

        cursor.execute("""
            UPDATE test_executions
            SET status = ?,
                result = ?,
                gif_path = ?,
                error_message = ?,
                end_time = CURRENT_TIMESTAMP,
                duration = ?
            WHERE id = ?
        """, (status, result, gif_path, error_message, duration, execution_id))

        conn.commit()
        conn.close()
        logger.info(f"[DB] 执行记录已更新：{execution_id}, status={status}, result={result}")
    except Exception as e:
        logger.error(f"[DB] 更新执行记录失败：{e}")


async def execute_single_testcase(
    testcase_id: int,
    testcase: dict,
    request: dict,
    screenshot_dir: str,
    execution_id: Optional[str] = None
) -> ExecutionResult:
    """执行单个测试用例（顺序执行）"""

    # 获取 API key
    api_key = os.getenv("API_KEY")
    if not api_key:
        logger.error(f"[执行] API key 未配置，无法执行：{testcase['name']}")
        return ExecutionResult(
            exec_status="执行失败",
            steps=[],
            gif_path=None,
            final_answer=None,
            error_message="API key 未配置"
        )

    base_url = os.getenv("BASE_URL", "")
    logger.info(f"[执行] 开始执行：testcase_id={testcase_id}, name={testcase['name']}")

    # 执行测试（使用全局 Agent 池）
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
        screenshot_dir=screenshot_dir
    )

    # 更新数据库
    update_testcase_status(
        testcase_id=testcase_id,
        exec_status=result.exec_status,
        steps=result.steps,
        gif_path=result.gif_path,
        final_answer=result.final_answer,
        error_message=result.error_message,
        execution_id=exec_id
    )

    logger.info(f"[执行] 执行完成：testcase_id={testcase_id}, status={result.exec_status}")

    return result


def get_logs() -> str:
    """获取执行日志"""
    log_file = LOG_DIR / "execution.log"
    if log_file.exists():
        with open(log_file, 'r', encoding='utf-8') as f:
            return f.read()
    return ""
