"""测试用例生成服务"""

import json
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class GeneratedTestCase:
    """生成的测试用例"""
    name: str
    description: str
    precondition: str
    steps: List[str]
    expected_result: str
    priority: str


class TestCaseGenerator:
    """测试用例生成器"""

    SYSTEM_PROMPT = """你是一个专业的软件测试工程师，擅长根据需求文档生成高质量的测试用例。

你的任务是分析提供的需求文档内容，生成全面、有效的测试用例。

测试用例应包含以下字段：
1. name: 测试用例名称（简洁明确，以"测试"或"验证"开头）
2. description: 测试用例描述（说明测试的目的和范围）
3. precondition: 前置条件（执行测试前需要满足的条件）
4. steps: 测试步骤（详细的操作步骤，数组格式）
5. expected_result: 预期结果（执行测试后期望得到的结果）
6. priority: 优先级（high-高优先级，medium-中优先级，low-低优先级）

生成测试用例时，请遵循以下原则：
- 覆盖正常场景和异常场景
- 考虑边界条件
- 测试步骤要具体、可执行
- 预期结果要明确、可验证
- 核心功能和用户主要操作路径使用高优先级
- 辅助功能和次要场景使用中优先级
- 边缘情况和异常处理使用低优先级

请以 JSON 数组格式返回测试用例，格式如下：
[
  {
    "name": "测试用例名称",
    "description": "测试用例描述",
    "precondition": "前置条件",
    "steps": ["步骤1", "步骤2", "步骤3"],
    "expected_result": "预期结果",
    "priority": "high|medium|low"
  }
]

只返回 JSON 数组，不要包含其他说明文字。"""

    def __init__(self, llm_client):
        """初始化测试用例生成器

        Args:
            llm_client: LLM客户端实例
        """
        self.client = llm_client

    def generate_from_document(
        self,
        document_text: str,
        document_title: Optional[str] = None,
        max_cases: Optional[int] = None
    ) -> List[GeneratedTestCase]:
        """从需求文档生成测试用例

        Args:
            document_text: 需求文档文本内容
            document_title: 文档标题（可选）
            max_cases: 最大生成用例数量（可选）

        Returns:
            生成的测试用例列表
        """
        # 构建用户消息
        user_message = self._build_prompt(document_text, document_title, max_cases)

        # 调用 LLM
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]

        try:
            response = self.client.respond(messages, temperature=0.3)
            return self._parse_response(response)
        except Exception as e:
            raise Exception(f"测试用例生成失败: {str(e)}")

    def _build_prompt(
        self,
        document_text: str,
        document_title: Optional[str] = None,
        max_cases: Optional[int] = None
    ) -> str:
        """构建生成提示词"""
        prompt = "请分析以下需求文档，生成全面的测试用例：\n\n"

        if document_title:
            prompt += f"文档标题：{document_title}\n\n"

        prompt += f"需求文档内容：\n{document_text}\n\n"

        if max_cases:
            prompt += f"请生成最多 {max_cases} 个测试用例。\n"
        else:
            prompt += "请生成适量的测试用例，覆盖主要功能点和异常场景。\n"

        prompt += "请以 JSON 数组格式返回测试用例。"

        return prompt

    def _parse_response(self, response: str) -> List[GeneratedTestCase]:
        """解析 LLM 响应"""
        # 清理响应
        response = response.strip()

        # 提取 JSON 部分
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.rfind("```")
            response = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.rfind("```")
            response = response[start:end].strip()

        # 解析 JSON
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            # 尝试提取 JSON 数组
            start = response.find("[")
            end = response.rfind("]")
            if start != -1 and end != -1 and end > start:
                data = json.loads(response[start:end+1])
            else:
                raise ValueError("无法解析生成的测试用例")

        # 验证数据格式
        if not isinstance(data, list):
            data = [data]

        # 转换为 GeneratedTestCase 对象
        cases = []
        for item in data:
            if not isinstance(item, dict):
                continue

            # 验证必需字段
            if "name" not in item or "steps" not in item or "expected_result" not in item:
                continue

            # 补全缺失字段
            item.setdefault("description", "")
            item.setdefault("precondition", "")
            item.setdefault("priority", "medium")

            # 确保步骤是列表
            if isinstance(item["steps"], str):
                item["steps"] = [s.strip() for s in item["steps"].split("\n") if s.strip()]

            cases.append(GeneratedTestCase(
                name=item["name"],
                description=item.get("description", ""),
                precondition=item.get("precondition", ""),
                steps=item["steps"] if isinstance(item["steps"], list) else [],
                expected_result=item.get("expected_result", ""),
                priority=item.get("priority", "medium")
            ))

        return cases
