"""
审计日志工具
提供统一的审计日志记录方法，在各 API 关键操作中调用
"""
from datetime import datetime, date
from functools import wraps
from typing import Optional, Any, Dict, Callable
from fastapi import Request
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog
from app.models.user import User


def _serialize_detail(value: Any) -> Any:
    """递归将 datetime/date 转换为 ISO 字符串，保证 detail 可 JSON 序列化"""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _serialize_detail(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize_detail(v) for v in value]
    return value


def log_audit(
    db: Session,
    action: str,
    resource_type: str,
    resource_id: Optional[int] = None,
    resource_name: Optional[str] = None,
    detail: Optional[Dict[str, Any]] = None,
    user: Optional[User] = None,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    status: str = "success",
    error_message: Optional[str] = None,
) -> AuditLog:
    """
    记录审计日志

    Args:
        db: 数据库会话
        action: 操作类型 create/update/delete/login/logout/export/import/execute/generate
        resource_type: 资源类型 project/requirement/case/run/defect/report/plan/environment/user/script/suite/llm_config/knowledge
        resource_id: 资源ID
        resource_name: 资源名称
        detail: 操作详情
        user: 当前用户对象（优先使用）
        user_id: 用户ID（user 为空时使用）
        username: 用户名（user 为空时使用）
        ip_address: IP地址
        user_agent: User-Agent
        status: 操作状态 success/failed
        error_message: 错误信息

    Returns:
        AuditLog 记录对象
    """
    if user is not None:
        user_id = user.id
        username = user.username

    log = AuditLog(
        user_id=user_id,
        username=username,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        resource_name=resource_name,
        detail=_serialize_detail(detail) if detail else {},
        ip_address=ip_address,
        user_agent=user_agent,
        status=status,
        error_message=error_message,
    )
    db.add(log)
    db.flush()
    return log


def audit(
    request: Request,
    db: Session,
    action: str,
    resource_type: str,
    user: Optional[User] = None,
    resource_id: Optional[int] = None,
    resource_name: Optional[str] = None,
    detail: Optional[Dict[str, Any]] = None,
    status: str = "success",
    error_message: Optional[str] = None,
) -> AuditLog:
    """
    审计日志便捷封装：自动从 Request 提取 IP 和 User-Agent。

    替代各路由中重复的:
        log_audit(db, action=..., resource_type=..., user=current_user,
                  ip_address=request.client.host if request.client else None,
                  user_agent=request.headers.get("user-agent"), ...)

    Args:
        request: FastAPI Request 对象
        db: 数据库会话
        action: 操作类型
        resource_type: 资源类型
        user: 当前用户对象
        resource_id: 资源ID
        resource_name: 资源名称
        detail: 操作详情
        status: 操作状态 success/failed
        error_message: 错误信息

    Returns:
        AuditLog 记录对象
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return log_audit(
        db,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        resource_name=resource_name,
        detail=detail,
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
        status=status,
        error_message=error_message,
    )


def audit_log(
    action: str,
    resource_type: str,
    resource_id_field: str = "id",
    resource_name_field: str = "name",
    detail: Optional[Dict[str, Any]] = None,
):
    """
    审计日志装饰器，自动记录操作日志。

    从被装饰函数的参数中自动提取 request / db / current_user，
    从返回值中提取 resource_id / resource_name，无需手动调用 log_audit。

    用法::

        @router.post("")
        @audit_log("create", "defect", resource_name_field="title")
        def create_defect(project_id, data, request, db, current_user):
            ...
            return defect

    Args:
        action: 操作类型 create/update/delete/execute/generate
        resource_type: 资源类型 defect/case/run/...
        resource_id_field: 返回对象中资源 ID 的字段名，默认 "id"
        resource_name_field: 返回对象中资源名称的字段名，默认 "name"
        detail: 额外详情字典
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = func(*args, **kwargs)

            # 从参数中提取 request / db / current_user
            request_obj = kwargs.get("request")
            if request_obj is None:
                request_obj = next(
                    (a for a in args if isinstance(a, Request)), None
                )

            db_session = kwargs.get("db")
            if db_session is None:
                db_session = next(
                    (a for a in args if isinstance(a, Session)), None
                )

            current_user = kwargs.get("current_user")
            if current_user is None:
                current_user = next(
                    (a for a in args if isinstance(a, User)), None
                )

            # 仅在所有必要对象都存在且有返回值时记录日志
            if all([request_obj, db_session, current_user]) and result is not None:
                resource_id = getattr(result, resource_id_field, None)
                resource_name = getattr(result, resource_name_field, "")
                log_audit(
                    db_session,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    resource_name=resource_name,
                    detail=detail,
                    user=current_user,
                    ip_address=request_obj.client.host if request_obj.client else None,
                    user_agent=request_obj.headers.get("user-agent"),
                )

            return result

        return wrapper

    return decorator
