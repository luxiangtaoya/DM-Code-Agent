"""Agent 池管理模块"""

import logging
from typing import Any, Optional

from dm_agent import create_llm_client, default_tools
from dm_agent.mcp import MCPManager, load_mcp_config

logger = logging.getLogger(__name__)


# 全局 Agent 池单例
_agent_pool: Optional["AgentPool"] = None


def get_agent_pool() -> "AgentPool":
    """获取全局 Agent 池"""
    global _agent_pool
    if _agent_pool is None:
        _agent_pool = AgentPool()
    return _agent_pool


class AgentPool:
    """Agent 资源池 - 单例模式

    负责管理 MCP 管理器、工具和 LLM 客户端的生命周期
    """

    def __init__(self):
        self.mcp_manager: Optional[MCPManager] = None
        self.mcp_config: Optional[dict] = None
        self.tools: Optional[list] = None
        self._initialized: bool = False

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

    def get_client(
        self,
        provider: str,
        api_key: str,
        model: str,
        base_url: str
    ) -> Any:
        """获取 LLM 客户端

        Args:
            provider: 提供商名称
            api_key: API 密钥
            model: 模型名称
            base_url: API 基础 URL

        Returns:
            LLM 客户端实例
        """
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
        logger.info("[AgentPool] 资源已清理")
