"""
全局异常处理模块
统一异常响应格式，确保前端能正确解析错误信息
"""
import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """处理 HTTP 异常"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "status_code": exc.status_code,
        },
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """处理请求参数校验异常"""
    errors = []
    for err in exc.errors():
        errors.append({
            "field": ".".join(str(x) for x in err.get("loc", [])),
            "message": err.get("msg", ""),
            "type": err.get("type", ""),
        })
    return JSONResponse(
        status_code=422,
        content={
            "detail": "请求参数校验失败",
            "errors": errors,
        },
    )


async def general_exception_handler(request: Request, exc: Exception):
    """处理通用异常（兜底）"""
    logger.exception(f"未处理的异常: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"服务器内部错误: {str(exc)}",
            "type": type(exc).__name__,
        },
    )
