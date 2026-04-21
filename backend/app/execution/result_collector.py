"""结果收集器模块 - 管理截图、脚本录制和网络追踪"""

import os
import re
import base64
import logging
from pathlib import Path
from typing import List, Optional, Any

from dm_agent.screenshot import ScreenshotManager
from dm_agent.recorders import PlaywrightRecorder, NetworkRecorder

logger = logging.getLogger(__name__)


class ResultCollector:
    """结果收集器

    负责管理：
    - 截图管理器（GIF 生成）
    - 脚本录制器（Playwright 回放脚本）
    - 网络追踪记录器
    """

    def __init__(
        self,
        execution_id: str,
        screenshot_dir: str,
        enable_screenshots: bool = True,
        enable_script: bool = True,
        enable_network_trace: bool = False
    ):
        self.execution_id = execution_id
        self.screenshot_dir = screenshot_dir
        self.enable_screenshots = enable_screenshots
        self.enable_script = enable_script
        self.enable_network_trace = enable_network_trace

        self.screenshot_manager: Optional[ScreenshotManager] = None
        self.script_recorder: Optional[PlaywrightRecorder] = None
        self.network_recorder: Optional[NetworkRecorder] = None

        self.task_screenshot_dir = os.path.join(screenshot_dir, execution_id)
        os.makedirs(self.task_screenshot_dir, exist_ok=True)

    def initialize(self, mcp_manager: Optional[Any] = None):
        """初始化所有收集器

        Args:
            mcp_manager: MCP 管理器实例，用于截图功能
        """
        # 创建截图管理器
        if self.enable_screenshots:
            self.screenshot_manager = ScreenshotManager(
                output_dir=self.screenshot_dir,
                enable_gif=True,
                gif_duration=1000
            )
            self.screenshot_manager.start_task(self.execution_id)
            logger.info("[ResultCollector] 截图管理器已初始化")

        # 创建脚本录制器
        if self.enable_script:
            self.script_recorder = PlaywrightRecorder(output_dir=self.screenshot_dir)
            self.script_recorder.start_task(self.execution_id)
            logger.info("[ResultCollector] 脚本录制器已初始化")

        # 创建网络追踪记录器
        if self.enable_network_trace and mcp_manager:
            project_root = str(Path(__file__).parent.parent.parent.parent)
            self.network_recorder = NetworkRecorder(
                output_dir=self.task_screenshot_dir,
                mcp_manager=mcp_manager,
                project_root=project_root
            )
            self.network_recorder.initialize()
            logger.info(f"[ResultCollector] 网络追踪器已初始化 (project_root={project_root})")

    def record_step(
        self,
        step_num: int,
        step_abbreviation: str,
        action: str,
        action_input: dict,
        observation: str,
        mcp_manager: Optional[Any] = None
    ):
        """记录执行步骤

        Args:
            step_num: 步骤序号
            step_abbreviation: 步骤简述
            action: 动作名称
            action_input: 动作参数
            observation: 观察结果
            mcp_manager: MCP 管理器实例
        """
        # 脚本录制
        if self.script_recorder and PlaywrightRecorder.is_playwright_action(action):
            if not PlaywrightRecorder.is_snapshot_tool(action):
                self.script_recorder.record_step(
                    action=action,
                    args=action_input or {},
                    raw_response=observation,
                    step_description=step_abbreviation or action
                )

        # 截图
        if self.screenshot_manager and mcp_manager:
            try:
                playwright_client = mcp_manager.clients.get("playwright")
                if playwright_client and playwright_client.is_running():
                    screenshot_result = playwright_client.call_tool("browser_take_screenshot", {})

                    if screenshot_result:
                        path_match = re.search(r'\[Screenshot[^\]]*\]\(([^\)]+)\)', str(screenshot_result))
                        if path_match:
                            screenshot_path = path_match.group(1)
                            with open(screenshot_path, 'rb') as f:
                                image_data = f.read()
                            base64_data = base64.b64encode(image_data).decode('utf-8')
                            self.screenshot_manager.add_screenshot_from_base64(
                                step_abbreviation,
                                base64_data
                            )
            except Exception as e:
                logger.error(f"[ResultCollector] 截图失败：{e}")

        # 网络追踪
        if self.network_recorder:
            try:
                self.network_recorder.collect_and_restart(step_num, step_abbreviation or action)
            except Exception as e:
                logger.error(f"[ResultCollector] 网络追踪失败（步骤 {step_num}）：{e}")

    def finalize(self, steps: List[Any], testcase_name: str) -> dict:
        """完成结果收集

        Args:
            steps: 执行步骤列表
            testcase_name: 测试用例名称

        Returns:
            包含 gif_path, script_path, network_path 的字典
        """
        result = {
            "gif_path": None,
            "script_path": None,
            "network_path": None
        }

        # 收集最后一步网络数据并保存
        if self.network_recorder and steps:
            last_step = steps[-1]
            last_action = getattr(last_step, 'step_abbreviation', '') or getattr(last_step, 'action', '')
            self.network_recorder.collect_final(len(steps), last_action)
            result["network_path"] = self.network_recorder.save_results()
            if result["network_path"]:
                logger.info(f"[ResultCollector] 网络追踪数据已保存：{result['network_path']}")

        # 生成 GIF
        if self.screenshot_manager:
            result["gif_path"] = self.screenshot_manager.finish_task()
            if result["gif_path"]:
                logger.info(f"[ResultCollector] GIF 已生成：{result['gif_path']}")

        # 生成回放脚本
        if self.script_recorder:
            try:
                steps_text = str(steps) if steps else ""
                result["script_path"] = self.script_recorder.generate_replayable_script(
                    task_name=f"{testcase_name}: {steps_text}"
                )
                logger.info(f"[ResultCollector] 回放脚本已生成：{result['script_path']}")
            except Exception as e:
                logger.warning(f"[ResultCollector] 生成回放脚本失败：{e}")

        return result

    def close_browser(self, mcp_manager: Optional[Any] = None):
        """关闭浏览器（如果正在运行）

        Args:
            mcp_manager: MCP 管理器实例
        """
        if not mcp_manager:
            return

        try:
            playwright_client = mcp_manager.clients.get("playwright")
            if playwright_client and playwright_client.is_running():
                playwright_client.call_tool("browser_close", {})
                logger.info("[ResultCollector] Playwright 浏览器页面已关闭")
        except Exception as e:
            logger.debug(f"[ResultCollector] 关闭浏览器失败：{e}")

    def cleanup(self):
        """清理资源"""
        self.screenshot_manager = None
        self.script_recorder = None
        self.network_recorder = None
