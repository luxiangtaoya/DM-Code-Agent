"""健康检查和日志 API"""

from fastapi import APIRouter, HTTPException

from app.execution_service import get_logs as service_get_logs, logger
from app.api import api_router


@api_router.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "AI 自动化测试平台"}


@api_router.get("/logs/execution")
async def get_execution_logs():
    """获取执行日志"""
    try:
        logs = service_get_logs()
        return {"logs": logs}
    except Exception as e:
        logger.error(f"获取日志失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))
