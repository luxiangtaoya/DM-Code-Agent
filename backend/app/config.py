"""配置管理模块"""

import os
from pathlib import Path
from typing import Optional


class Settings:
    """应用配置管理"""

    def __init__(self):
        # 基础路径
        self.backend_dir = Path(__file__).parent.parent
        self.root_dir = self.backend_dir.parent

        # 数据目录
        self.data_dir = self.backend_dir / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 子目录
        self.screenshot_dir = self.data_dir / "screenshots"
        self.upload_dir = self.data_dir / "uploads" / "documents"
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

        # 数据库
        self.db_path = self.data_dir / "testing_platform.db"

        # 服务配置
        self.host = os.getenv("HOST", "0.0.0.0")
        self.port = int(os.getenv("PORT", "8080"))

        # LLM 配置
        self.api_key = os.getenv("API_KEY")
        self.base_url = os.getenv("BASE_URL", "")
        self.default_provider = os.getenv("DEFAULT_PROVIDER", "qwen")
        self.default_model = os.getenv("DEFAULT_MODEL", "qwen3.5-flash")

        # 执行配置
        self.enable_screenshots = os.getenv("ENABLE_SCREENSHOTS", "true").lower() == "true"
        self.enable_network_trace = os.getenv("ENABLE_NETWORK_TRACE", "false").lower() == "true"
        self.enable_script = os.getenv("ENABLE_SCRIPT", "true").lower() == "true"
        self.gif_duration = int(os.getenv("GIF_DURATION", "1000"))  # GIF 每帧显示时间（毫秒）

        # Agent 池配置
        self.agent_pool_size = int(os.getenv("AGENT_POOL_SIZE", "5"))

        # 执行配置
        self.execution_timeout = int(os.getenv("EXECUTION_TIMEOUT", "300"))  # 执行超时（秒）
        self.max_retries = int(os.getenv("MAX_RETRIES", "3"))  # 最大重试次数

    def get_screenshot_url(self, gif_path: str) -> str:
        """获取截图 URL"""
        if not gif_path:
            return ""
        # 转换为相对路径
        try:
            rel_path = Path(gif_path).relative_to(self.data_dir)
            return f"/screenshots/{rel_path.as_posix()}"
        except ValueError:
            return f"/screenshots/{Path(gif_path).name}"


# 单例实例
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """获取配置单例"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings():
    """重新加载配置（用于测试）"""
    global _settings
    _settings = Settings()
