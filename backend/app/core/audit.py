"""
审计日志工具
提供统一的审计日志记录方法，在各 API 关键操作中调用
"""
from datetime import datetime, date
from typing import Optional, Any, Dict
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
