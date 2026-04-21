"""Playwright 执行轨迹记录器 - 记录浏览器操作并生成可回放的 JavaScript 脚本

设计思路：
1. 从 observation 的 ```js 代码块中直接提取实际执行的 JS 代码
2. 保存完整代码到 step.extracted_code
3. 生成脚本时直接使用保存的代码，无需 ref 映射转换
4. 将步骤描述作为注释添加到每个步骤，方便人类阅读
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class PlaywrightStep:
    """单个执行步骤"""

    def __init__(
        self,
        action: str,
        args: Dict[str, Any],
        raw_response: str = "",
        step_description: str = ""
    ):
        self.action = action
        self.args = args
        self.raw_response = raw_response
        self.step_description = step_description  # 步骤描述，用作注释
        self.extracted_code = None  # 存储从 observation 提取的完整 JS 代码

    def extract_code_from_observation(self, observation: str) -> Optional[str]:
        """从 observation 中提取完整的 JS 代码"""
        if not observation:
            return None

        # 提取 ```js 代码块
        code_match = re.search(r'```js\s*\n(.*?)\n```', observation, re.DOTALL)
        if code_match:
            code = code_match.group(1).strip()
            self.extracted_code = code
            return code

        # 尝试更宽松的匹配（代码块后直接跟 ```）
        code_match = re.search(r'```js\s*\n(.*?)```', observation, re.DOTALL)
        if code_match:
            code = code_match.group(1).strip()
            self.extracted_code = code
            return code

        return None

    def _extract_action_name(self) -> str:
        """提取动作名称"""
        if isinstance(self.action, str):
            action = self.action.lower()
            # 去掉 mcp_playwright_ 前缀
            if action.startswith('mcp_playwright_'):
                action = action.replace('mcp_playwright_', '', 1)
            # 去掉 browser_ 前缀，如 "browser_fill_form" -> "fillform"
            action = action.replace("browser_", "").replace("_", "")
            return action
        return str(self.action).lower()

    def to_js_code(self) -> str:
        """转换为 Playwright JavaScript 代码"""

        # 优先：使用从 observation 提取的完整代码
        if self.extracted_code:
            code = self.extracted_code.rstrip(';')  # 去掉末尾分号避免双分号
            # 添加步骤描述作为注释
            comment = f"  // {self.step_description}" if self.step_description else ""
            return f'{comment}\n  {code};\n  await page.waitForTimeout(1000);'

        # 回退：根据 action 类型生成代码
        action_name = self._extract_action_name()

        # 导航类
        if action_name in ["goto", "navigate", "browser_navigate", "browser_goto"]:
            url = self.args.get("url", "")
            comment = f"  // {self.step_description}" if self.step_description else "  // 导航到页面"
            return f'{comment}\n  await page.goto("{url}");\n  await page.waitForTimeout(1000);'

        # 填写表单类
        elif action_name in ["fillform", "browser_fill_form"]:
            fields = self.args.get("fields", self.args.get("values", {}))
            comment = f"  // {self.step_description}" if self.step_description else "  // 填写表单"
            lines = [comment]
            if isinstance(fields, dict):
                for selector, value in fields.items():
                    lines.append(f'  await page.fill("{selector}", "{value}");')
            elif isinstance(fields, list):
                for field in fields:
                    if isinstance(field, dict):
                        sel = field.get("selector", field.get("field", ""))
                        val = field.get("value", "")
                        lines.append(f'  await page.fill("{sel}", "{val}");')
            lines.append('  await page.waitForTimeout(1000);')
            return '\n'.join(lines)

        # 点击类
        elif action_name in ["click", "browser_click"]:
            selector = self.args.get("selector", self.args.get("element", ""))
            comment = f"  // {self.step_description}" if self.step_description else "  // 点击元素"
            return f'{comment}\n  await page.click("{selector}");\n  await page.waitForTimeout(1000);'

        # 填充单个字段
        elif action_name in ["fill", "browser_fill"]:
            selector = self.args.get("selector", self.args.get("field", ""))
            value = self.args.get("value", self.args.get("text", ""))
            comment = f"  // {self.step_description}" if self.step_description else "  // 填充字段"
            return f'{comment}\n  await page.fill("{selector}", "{value}");\n  await page.waitForTimeout(1000);'

        # 选择下拉框
        elif action_name in ["select", "browser_select"]:
            selector = self.args.get("selector", "")
            value = self.args.get("value", self.args.get("values", ""))
            comment = f"  // {self.step_description}" if self.step_description else "  // 选择选项"
            return f'{comment}\n  await page.selectOption("{selector}", "{value}");\n  await page.waitForTimeout(1000);'

        # 键盘按键
        elif action_name in ["press", "browser_press", "type", "browser_type"]:
            key = self.args.get("key", self.args.get("text", ""))
            comment = f"  // {self.step_description}" if self.step_description else "  // 按键输入"
            if action_name in ["type", "browser_type"]:
                selector = self.args.get("selector", "")
                return f'{comment}\n  await page.fill("{selector}", "{key}");\n  await page.waitForTimeout(1000);'
            return f'{comment}\n  await page.keyboard.press("{key}");\n  await page.waitForTimeout(1000);'

        # 悬停
        elif action_name in ["hover", "browser_hover"]:
            selector = self.args.get("selector", self.args.get("element", ""))
            comment = f"  // {self.step_description}" if self.step_description else "  // 悬停元素"
            return f'{comment}\n  await page.hover("{selector}");\n  await page.waitForTimeout(1000);'

        # 执行JS
        elif action_name in ["evaluate", "browser_evaluate"]:
            script = self.args.get("script", self.args.get("expression", ""))
            comment = f"  // {self.step_description}" if self.step_description else "  // 执行脚本"
            return f'{comment}\n  await page.evaluate(() => {{\n    {script}\n  }});\n  await page.waitForTimeout(1000);'

        # 切换标签页（无代码块，需特殊处理）
        elif action_name in ["tabs", "browser_tabs"]:
            action_type = self.args.get("action", "")
            if action_type == "select":
                index = self.args.get("index", 0)
                comment = f"  // {self.step_description}" if self.step_description else f"  // 切换到第 {index} 个标签页"
                # 使用 pageIdx 计数器避免变量重复声明
                page_idx = getattr(self, '_pages_var_counter', 0)
                self._pages_var_counter = page_idx + 1
                var_name = f'pages{page_idx if page_idx > 0 else ""}'
                return (
                    f'{comment}\n'
                    f'  const {var_name} = await page.context().pages();\n'
                    f'  page = {var_name}[{index}];\n'
                    f'  await page.waitForLoadState("domcontentloaded");\n'
                    f'  await page.waitForTimeout(1000);'
                )

        # 等待类
        elif action_name in ["wait", "browser_wait", "wait_for"]:
            time_val = self.args.get("time", self.args.get("timeout", 1))
            comment = f"  // {self.step_description}" if self.step_description else "  // 等待"
            return f'{comment}\n  await page.waitForTimeout({time_val * 1000});'

        # 跳过的操作
        elif "snapshot" in action_name.lower():
            return f'  // {self.step_description} (snapshot - 回放时跳过)' if self.step_description else '  // snapshot (回放时跳过)'
        elif "screenshot" in action_name.lower():
            return f'  // {self.step_description} (screenshot - 回放时跳过)' if self.step_description else '  // screenshot (回放时跳过)'

        return f'  // {self.step_description} (Unknown action: {self.action})' if self.step_description else f'  // Unknown action: {self.action}'


class PlaywrightRecorder:
    """Playwright 执行记录器 - 记录浏览器操作并生成可回放脚本"""

    # Playwright 相关的工具名称
    PLAYWRIGHT_ACTIONS = {
        'browser_navigate', 'browser_goto', 'browser_click', 'browser_fill',
        'browser_fill_form', 'browser_select', 'browser_wait', 'browser_tabs',
        'browser_close', 'browser_take_screenshot', 'browser_snapshot',
        'browser_evaluate', 'browser_hover', 'browser_drag', 'browser_check',
        'browser_uncheck', 'browser_press', 'browser_type', 'browser_focus',
        'browser_install', 'browser_resize', 'browser_file_upload',
        'browser_handle_dialog', 'browser_network_requests',
        'browser_console_messages', 'browser_pdf_save',
    }

    def __init__(self, output_dir: str = "recorded_scripts"):
        """
        初始化记录器

        Args:
            output_dir: 脚本输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.steps: List[PlaywrightStep] = []
        self.task_id: Optional[str] = None

    @classmethod
    def is_playwright_action(cls, action: str) -> bool:
        """判断是否是 playwright 相关的操作"""
        if not action:
            return False
        action_lower = action.lower()
        # 支持 mcp_playwright_ 前缀，如 mcp_playwright_browser_fill_form
        if action_lower.startswith('mcp_playwright_'):
            action_lower = action_lower.replace('mcp_playwright_', '', 1)
        return any(pa in action_lower for pa in cls.PLAYWRIGHT_ACTIONS)

    @classmethod
    def is_snapshot_tool(cls, action: str) -> bool:
        """判断是否是 snapshot 工具（需要跳过记录）"""
        return 'snapshot' in action.lower() if action else False

    def start_task(self, task_id: Optional[str] = None) -> str:
        """
        开始一个新任务

        Args:
            task_id: 任务 ID，如果为 None 则自动生成

        Returns:
            任务 ID
        """
        if task_id is None:
            task_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.task_id = task_id
        self.steps = []
        self._pages_var_counter = 0  # 重置标签页变量计数器

        # 创建任务目录
        task_dir = self.output_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        return task_id

    def record_step(
        self,
        action: str,
        args: Dict[str, Any],
        raw_response: str = "",
        step_description: str = ""
    ):
        """
        记录一个执行步骤

        Args:
            action: 动作名称
            args: 动作参数
            raw_response: 原始响应（observation）
            step_description: 步骤描述，用作注释
        """
        step = PlaywrightStep(action, args, raw_response, step_description)
        # 核心逻辑：从 observation 提取 JS 代码
        step.extract_code_from_observation(raw_response)
        self.steps.append(step)

    def _deduplicate_goto_steps(self) -> List[PlaywrightStep]:
        """去重连续的 goto 操作（保留最后一个）"""
        if not self.steps:
            return []

        deduped = []
        prev_was_goto = False

        for step in self.steps:
            action_name = step._extract_action_name()
            is_goto = action_name in ["goto", "navigate", "browser_navigate", "browser_goto"]

            if is_goto:
                # 如果前一个也是 goto，移除前一个
                if prev_was_goto and deduped:
                    deduped.pop()
                deduped.append(step)
                prev_was_goto = True
            else:
                deduped.append(step)
                prev_was_goto = False

        return deduped

    def generate_replayable_script(self, task_name: str = "测试任务") -> str:
        """
        生成可回放的 JavaScript 脚本

        Args:
            task_name: 任务名称，用于注释

        Returns:
            生成的脚本文件路径
        """
        if self.task_id is None:
            raise RuntimeError("请先调用 start_task() 开始任务")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        script_name = f"replay_{timestamp}.js"

        # 处理任务名称：移除换行符避免注释格式错误
        clean_task_name = task_name.replace('\n', ' ').replace('\r', ' ')
        # 移除可能破坏注释的特殊字符
        clean_task_name = re.sub(r'[*/*/]', '', clean_task_name)

        code_lines = [
            "// =========================================",
            "// 自动生成的 Playwright 回放脚本",
            f"// 任务: {clean_task_name}",
            f"// 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "// =========================================",
            "",
            "const { chromium } = require('playwright');",
            "",
            "(async () => {",
            "  const browser = await chromium.launch({",
            "    channel: 'chrome',",
            "    headless: false",
            "  });",
            "  let page = await browser.newPage();",
            "  page.setDefaultTimeout(60000);",
            "",
        ]

        # 去重并生成每个步骤的代码
        deduped_steps = self._deduplicate_goto_steps()
        for step in deduped_steps:
            code_lines.append(step.to_js_code())

        code_lines.extend([
            "",
            "  await browser.close();",
            "})();",
        ])

        script_content = "\n".join(code_lines)
        script_path = self.output_dir / self.task_id / script_name

        # 确保目录存在
        script_path.parent.mkdir(parents=True, exist_ok=True)

        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)

        return str(script_path)

    def get_task_dir(self) -> Path:
        """获取当前任务目录"""
        if self.task_id is None:
            raise RuntimeError("请先调用 start_task() 开始任务")
        return self.output_dir / self.task_id

    def clear(self):
        """清空当前任务的所有步骤"""
        self.steps = []
        self.task_id = None
