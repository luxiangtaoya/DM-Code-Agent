"""API 路由模块"""

from fastapi import APIRouter

api_router = APIRouter(prefix="/api/v1", tags=["API"])

# 导入各个子路由 - 必须在 api_router 定义之后
from . import health, projects, documents, testcases, executions, reports, scripts
