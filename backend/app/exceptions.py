"""统一错误处理模块"""

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class AppException(Exception):
    """应用基础异常"""

    def __init__(
        self,
        message: str = "操作失败",
        code: int = 500,
        detail: Optional[str] = None
    ):
        self.message = message
        self.code = code
        self.detail = detail
        super().__init__(self.message)


class NotFoundException(AppException):
    """资源未找到异常"""

    def __init__(self, resource: str = "资源", detail: Optional[str] = None):
        super().__init__(
            message=f"{resource}不存在",
            code=404,
            detail=detail
        )


class ValidationException(AppException):
    """数据验证异常"""

    def __init__(self, message: str = "数据验证失败", detail: Optional[str] = None):
        super().__init__(
            message=message,
            code=400,
            detail=detail
        )


class ConflictException(AppException):
    """资源冲突异常"""

    def __init__(self, message: str = "资源冲突", detail: Optional[str] = None):
        super().__init__(
            message=message,
            code=409,
            detail=detail
        )


class UnauthorizedException(AppException):
    """未授权异常"""

    def __init__(self, message: str = "未授权访问", detail: Optional[str] = None):
        super().__init__(
            message=message,
            code=401,
            detail=detail
        )


class ServiceUnavailableException(AppException):
    """服务不可用异常"""

    def __init__(self, message: str = "服务暂时不可用", detail: Optional[str] = None):
        super().__init__(
            message=message,
            code=503,
            detail=detail
        )


def create_error_response(code: int, message: str, detail: Optional[str] = None) -> Dict[str, Any]:
    """创建错误响应"""
    return {
        "code": code,
        "message": message,
        "detail": detail
    }


def register_exception_handlers(app: FastAPI):
    """注册全局异常处理器"""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        """处理应用自定义异常"""
        logger.warning(f"应用异常：{exc.message}, 路径：{request.url.path}")
        return JSONResponse(
            status_code=exc.code,
            content=create_error_response(exc.code, exc.message, exc.detail)
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """处理 HTTP 异常"""
        logger.warning(f"HTTP 异常：{exc.detail}, 路径：{request.url.path}")
        return JSONResponse(
            status_code=exc.status_code,
            content=create_error_response(
                exc.status_code,
                exc.detail if isinstance(exc.detail, str) else str(exc.detail)
            )
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """处理请求验证异常"""
        logger.warning(f"请求验证失败：{exc.errors()}, 路径：{request.url.path}")
        errors = []
        for error in exc.errors():
            field = ".".join(str(x) for x in error.get("loc", []))
            msg = error.get("msg", "")
            errors.append(f"{field}: {msg}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=create_error_response(
                400,
                "请求参数验证失败",
                "; ".join(errors)
            )
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """处理全局未捕获异常"""
        logger.error(f"未捕获异常：{exc}, 路径：{request.url.path}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=create_error_response(
                500,
                "服务器内部错误",
                "请稍后重试或联系管理员"
            )
        )
