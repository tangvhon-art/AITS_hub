"""
审计日志 API
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.audit_log import AuditLog
from app.schemas.test_plan import AuditLogResponse, AuditLogListResponse

router = APIRouter(prefix="/api/audit-logs")


@router.post("/search", response_model=AuditLogListResponse)
def list_audit_logs(
    user_id: Optional[int] = Body(None),
    action: Optional[str] = Body(None),
    resource_type: Optional[str] = Body(None),
    status: Optional[str] = Body(None),
    page: int = Body(1),
    page_size: int = Body(20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取审计日志列表"""
    query = db.query(AuditLog)

    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)
    if status:
        query = query.filter(AuditLog.status == status)

    total = query.count()
    logs = query.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return AuditLogListResponse(total=total, page=page, page_size=page_size, items=logs)


@router.get("/{log_id}", response_model=AuditLogResponse)
def get_audit_log(log_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取审计日志详情"""
    log = db.query(AuditLog).filter(AuditLog.id == log_id).first()
    if not log:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="审计日志不存在")
    return log
