"""
全局异常处理器注册

统一错误响应格式::

    {"code": <int>, "message": <str>, "detail": <any>}

同时保留 ``detail`` 字段以兼容现有前端代码。
"""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import BizException

logger = logging.getLogger(__name__)


async def biz_exception_handler(request: Request, exc: BizException) -> JSONResponse:
    """处理业务异常"""
    logger.warning(
        "业务异常 %s %s -> code=%s message=%s detail=%s",
        request.method,
        request.url.path,
        exc.code,
        exc.message,
        exc.detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "detail": exc.detail if exc.detail is not None else exc.message,
        },
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """处理 HTTP 异常（兼容现有 raise HTTPException 的代码）"""
    logger.info(
        "HTTP异常 %s %s -> status=%s detail=%s",
        request.method,
        request.url.path,
        exc.status_code,
        exc.detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": str(exc.detail),
            "detail": exc.detail,
        },
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """处理请求参数校验异常"""
    errors = []
    for err in exc.errors():
        errors.append({
            "field": ".".join(str(x) for x in err.get("loc", [])),
            "message": err.get("msg", ""),
            "type": err.get("type", ""),
        })
    logger.warning(
        "参数校验失败 %s %s -> %d 个错误",
        request.method,
        request.url.path,
        len(errors),
    )
    return JSONResponse(
        status_code=422,
        content={
            "code": 1422,
            "message": "请求参数校验失败",
            "detail": "请求参数校验失败",
            "errors": errors,
        },
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """处理未捕获的通用异常（兜底）"""
    logger.exception(
        "未处理异常 %s %s -> %s: %s",
        request.method,
        request.url.path,
        type(exc).__name__,
        exc,
    )
    return JSONResponse(
        status_code=500,
        content={
            "code": 1500,
            "message": "服务器内部错误",
            "detail": f"服务器内部错误: {str(exc)}",
            "type": type(exc).__name__,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器到 FastAPI 应用"""
    app.add_exception_handler(BizException, biz_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
