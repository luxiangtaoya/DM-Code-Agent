"""Agent 执行器模块"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from dm_agent import ReactAgent

from app.execution.agent_pool import AgentPool, get_agent_pool
from app.execution.result_collector import ResultCollector

logger = logging.getLogger(__name__)


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
    script_path: Optional[str]   # JS 脚本路径
    final_answer: Optional[str]  # 最终答案
    error_message: Optional[str] = None  # 错误信息
    network_path: Optional[str] = None   # 网络追踪路径


class AgentExecutor:
    """Agent 执行器

    负责执行单个测试用例，包括：
    - 初始化 Agent 和相关组件
    - 执行测试任务
    - 收集执行结果
    - AI 判断执行是否通过
    """

    def __init__(
        self,
        execution_id: str,
        testcase_id: int,
        testcase_name: str,
        test_case: dict,
        model: str,
        provider: str,
        api_key: str,
        base_url: str,
        screenshot_dir: str,
        options: Optional[dict] = None
    ):
        self.execution_id = execution_id
        self.testcase_id = testcase_id
        self.testcase_name = testcase_name
        self.test_case = test_case
        self.model = model
        self.provider = provider
        self.api_key = api_key
        self.base_url = base_url
        self.screenshot_dir = screenshot_dir
        self.options = options or {}

        self.enable_screenshots = self.options.get('enable_screenshots', True)
        self.enable_network_trace = self.options.get('enable_network_trace', False)
        self.enable_script = self.options.get('enable_script', True)

        self.steps_log: List[Step] = []
        self.pool: Optional[AgentPool] = None
        self.result_collector: Optional[ResultCollector] = None

    def execute(self) -> ExecutionResult:
        """执行测试用例

        Returns:
            ExecutionResult 执行结果
        """
        logger.info(f"[Agent] 开始执行：{self.testcase_name} (execution_id={self.execution_id})")
        logger.info(
            f"[Agent] 执行选项：screenshots={self.enable_screenshots}, "
            f"network_trace={self.enable_network_trace}, script={self.enable_script}"
        )

        try:
            # 初始化资源池
            self.pool = get_agent_pool()
            self.pool.initialize()

            # 获取客户端和工具
            client = self.pool.get_client(
                provider=self.provider,
                api_key=self.api_key,
                model=self.model,
                base_url=self.base_url
            )
            tools = self.pool.tools
            logger.info(f"[Agent] LLM 客户端已获取：{self.provider}/{self.model}")

            # 创建结果收集器
            self.result_collector = ResultCollector(
                execution_id=self.execution_id,
                screenshot_dir=self.screenshot_dir,
                enable_screenshots=self.enable_screenshots,
                enable_script=self.enable_script,
                enable_network_trace=self.enable_network_trace
            )
            self.result_collector.initialize(self.pool.mcp_manager)

            # 创建步骤回调函数
            def step_callback(step_num: int, step: Any) -> None:
                self._handle_step(step_num, step)

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
            steps = self.test_case.get("steps", [])
            if isinstance(steps, str):
                try:
                    steps = json.loads(steps)
                except:
                    steps = steps.split('\n') if steps else ["1. 打开应用"]

            # 构建任务描述
            task_description = f"执行以下任务：{chr(10).join([f'{i+1}. {step}' for i, step in enumerate(steps)])}"

            # 执行任务
            logger.info("[Agent] 开始执行任务...")
            result = agent.run(task_description)

            # 完成结果收集
            finalize_result = self.result_collector.finalize(
                steps=self.steps_log,
                testcase_name=self.testcase_name
            )

            # 关闭浏览器
            self._close_browser()

            # 构建任务描述用于 AI 判断
            task_desc_for_judge = (
                f"任务名称：{self.test_case.get('name', '')}\n"
                f"任务描述：{self.test_case.get('steps', '')}\n"
                f"预期结果：{self.test_case.get('expected_result', '')}"
            )

            # AI 判断执行结果
            exec_status, judged_answer = self._judge_execution_result(
                client=client,
                task_description=task_desc_for_judge,
                steps=self.steps_log
            )

            logger.info(
                f"[Agent] 任务完成：状态={exec_status}, 共执行 {len(self.steps_log)} 步"
            )

            return ExecutionResult(
                exec_status=exec_status,
                steps=self.steps_log,
                gif_path=finalize_result["gif_path"],
                script_path=finalize_result["script_path"],
                final_answer=judged_answer,
                network_path=finalize_result["network_path"]
            )

        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"[Agent] 执行失败：{e}\n{error_trace}")

            # 清理资源
            self._close_browser()
            if self.result_collector:
                self.result_collector.cleanup()

            return ExecutionResult(
                exec_status="执行失败",
                steps=self.steps_log,
                gif_path=None,
                script_path=None,
                final_answer=None,
                error_message=str(e)
            )

    def _handle_step(self, step_num: int, step: Any):
        """处理单个执行步骤

        Args:
            step_num: 步骤序号
            step: 步骤对象
        """
        step_info = Step(
            thought=getattr(step, 'thought', ''),
            step_abbreviation=getattr(step, 'step_abbreviation', ''),
            action=getattr(step, 'action', ''),
            action_input=getattr(step, 'action_input', ''),
            observation=getattr(step, 'observation', ''),
            raw=getattr(step, 'raw', '')
        )
        self.steps_log.append(step_info)

        # 使用结果收集器记录步骤
        if self.result_collector and self.pool:
            self.result_collector.record_step(
                step_num=step_num,
                step_abbreviation=step_info.step_abbreviation,
                action=step_info.action,
                action_input=step_info.action_input,
                observation=step_info.observation,
                mcp_manager=self.pool.mcp_manager
            )

    def _close_browser(self):
        """关闭浏览器"""
        if self.pool and self.pool.mcp_manager:
            try:
                playwright_client = self.pool.mcp_manager.clients.get("playwright")
                if playwright_client and playwright_client.is_running():
                    playwright_client.call_tool("browser_close", {})
                    logger.info("[Agent] Playwright 浏览器页面已关闭")
            except Exception as e:
                logger.debug(f"[Agent] 关闭浏览器失败：{e}")

    def _judge_execution_result(
        self,
        client: Any,
        task_description: str,
        steps: List[Step]
    ) -> Tuple[str, str]:
        """调用大模型判断执行结果

        Args:
            client: LLM 客户端
            task_description: 任务描述
            steps: 执行步骤列表

        Returns:
            (exec_status, judged_answer)
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
            # 降级处理
            return "执行失败", f"【AI 判断失败】{str(e)}"


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
    options: Optional[dict] = None,
) -> ExecutionResult:
    """在独立线程中运行 Agent，返回 ExecutionResult

    Args:
        options: 执行选项，如 {"enable_screenshots": True, "enable_network_trace": False, "enable_script": True}

    Returns:
        ExecutionResult 执行结果
    """
    executor = AgentExecutor(
        execution_id=execution_id,
        testcase_id=testcase_id,
        testcase_name=testcase_name,
        test_case=test_case,
        model=model,
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        screenshot_dir=screenshot_dir,
        options=options
    )
    return executor.execute()
