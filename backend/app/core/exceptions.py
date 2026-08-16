"""
统一异常定义

业务异常基类 BizException 及常见子类，统一错误响应格式 {code, message, detail}。
后续接口逐步从 raise HTTPException 迁移到 raise BizException 子类。
"""
from typing import Any, Optional


class BizException(Exception):
    """业务异常基类

    统一错误响应格式::

        {"code": <code>, "message": <message>, "detail": <detail>}

    - code: 业务错误码（0 表示成功，非 0 表示业务错误）
    - message: 面向用户的简短错误描述
    - detail: 额外详情（字符串、字典或列表）
    - status_code: HTTP 状态码（默认 400）
    """

    def __init__(
        self,
        message: str = "业务处理失败",
        code: int = 1000,
        detail: Any = None,
        status_code: int = 400,
    ):
        self.code = code
        self.message = message
        self.detail = detail
        self.status_code = status_code
        super().__init__(message)

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "detail": self.detail,
        }


class NotFoundException(BizException):
    """资源不存在"""

    def __init__(self, message: str = "资源不存在", detail: Any = None):
        super().__init__(message=message, code=1404, detail=detail, status_code=404)


class PermissionDeniedException(BizException):
    """权限不足"""

    def __init__(self, message: str = "权限不足", detail: Any = None):
        super().__init__(message=message, code=1403, detail=detail, status_code=403)


class ValidationException(BizException):
    """业务校验失败"""

    def __init__(self, message: str = "参数校验失败", detail: Any = None):
        super().__init__(message=message, code=1400, detail=detail, status_code=400)


class UnauthorizedException(BizException):
    """未认证 / 登录失效"""

    def __init__(self, message: str = "未登录或登录已过期", detail: Any = None):
        super().__init__(message=message, code=1401, detail=detail, status_code=401)


class ConflictException(BizException):
    """资源冲突"""

    def __init__(self, message: str = "资源冲突", detail: Any = None):
        super().__init__(message=message, code=1409, detail=detail, status_code=409)
