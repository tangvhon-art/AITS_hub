"""
系统定时任务管理 API（sys_crontab）

动态 Celery Beat 的任务清单数据源：Beat 的自定义 DatabaseScheduler
每 5 秒轮询本表，增删改/启停后无需重启 beat 即可生效。

⚠️ Beat 必须单实例运行，多个 beat 进程会重复派发任务。
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.audit import log_audit
from app.models.user import User
from app.models.sys_crontab import SysCrontab
from app.schemas.crontab import (
    CrontabCreate,
    CrontabUpdate,
    CrontabResponse,
    CrontabListResponse,
)

router = APIRouter(
    prefix="/api/crontabs",
    tags=["定时任务"],
    dependencies=[Depends(require_admin)],
)

ALLOWED_QUEUES = ("default", "ai", "execution", "eval")
ALLOWED_SCHEDULE_TYPES = ("interval", "cron")


def _validate_schedule(data, partial: bool = False):
    """校验调度配置：类型、队列、间隔秒数、cron 表达式合法性"""
    queue = getattr(data, "queue", None)
    if queue is not None and queue not in ALLOWED_QUEUES:
        raise HTTPException(400, f"队列必须为: {', '.join(ALLOWED_QUEUES)}")

    schedule_type = getattr(data, "schedule_type", None)
    if schedule_type is not None and schedule_type not in ALLOWED_SCHEDULE_TYPES:
        raise HTTPException(400, f"调度类型必须为: {', '.join(ALLOWED_SCHEDULE_TYPES)}")

    if schedule_type == "interval":
        every = getattr(data, "every_seconds", None)
        if every is None or every <= 0:
            raise HTTPException(400, "interval 类型必须提供正整数 every_seconds（间隔秒数）")

    if schedule_type == "cron":
        from celery.schedules import crontab as celery_crontab
        try:
            celery_crontab(
                minute=data.minute or "*",
                hour=data.hour or "*",
                day_of_week=data.day_of_week or "*",
                day_of_month=data.day_of_month or "*",
                month_of_year=data.month_of_year or "*",
            )
        except ValueError as e:
            raise HTTPException(400, f"cron 表达式非法: {e}")

    task = getattr(data, "task", None)
    if task:
        from app.celery_app import celery_app
        if task not in celery_app.tasks:
            raise HTTPException(400, f"Celery 任务不存在: {task}")


def _get_crontab(crontab_id: int, db: Session) -> SysCrontab:
    item = db.query(SysCrontab).filter(
        SysCrontab.id == crontab_id, SysCrontab.is_deleted == False  # noqa: E712
    ).first()
    if not item:
        raise HTTPException(404, "定时任务不存在")
    return item


@router.get("", response_model=CrontabListResponse)
def list_crontabs(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """定时任务列表"""
    query = db.query(SysCrontab).filter(SysCrontab.is_deleted == False)  # noqa: E712
    total = query.count()
    items = (
        query.order_by(SysCrontab.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return CrontabListResponse(total=total, page=page, page_size=page_size, items=items)


@router.get("/{crontab_id}", response_model=CrontabResponse)
def get_crontab(
    crontab_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """定时任务详情"""
    return _get_crontab(crontab_id, db)


@router.post("", response_model=CrontabResponse)
def create_crontab(
    data: CrontabCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """新增定时任务（保存后 beat 最长 5 秒内自动生效）"""
    _validate_schedule(data)
    item = SysCrontab(
        name=data.name,
        task=data.task,
        args=data.args,
        kwargs=data.kwargs,
        queue=data.queue,
        schedule_type=data.schedule_type,
        every_seconds=data.every_seconds,
        minute=data.minute or "*",
        hour=data.hour or "*",
        day_of_week=data.day_of_week or "*",
        day_of_month=data.day_of_month or "*",
        month_of_year=data.month_of_year or "*",
        enabled=data.enabled,
        description=data.description,
        created_by=current_user.id,
    )
    db.add(item)
    db.flush()
    log_audit(
        db, action="create", resource_type="crontab",
        resource_id=item.id, resource_name=item.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"task": item.task, "schedule_type": item.schedule_type},
    )
    db.commit()
    db.refresh(item)
    return item


@router.put("/{crontab_id}", response_model=CrontabResponse)
def update_crontab(
    crontab_id: int,
    data: CrontabUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """编辑定时任务（保存后 beat 最长 5 秒内自动生效，无需重启）"""
    item = _get_crontab(crontab_id, db)
    update_data = data.model_dump(exclude_unset=True)

    # 用"已有配置 + 本次变更"合并后整体校验调度合法性
    class _Merged:
        pass
    merged = _Merged()
    for field in ("schedule_type", "every_seconds", "minute", "hour", "day_of_week",
                  "day_of_month", "month_of_year", "queue", "task"):
        setattr(merged, field, update_data.get(field, getattr(item, field)))
    _validate_schedule(merged)

    before = {k: getattr(item, k) for k in update_data}
    for key, value in update_data.items():
        setattr(item, key, value)
    log_audit(
        db, action="update", resource_type="crontab",
        resource_id=item.id, resource_name=item.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"before": before, "after": update_data},
    )
    db.commit()
    db.refresh(item)
    return item


@router.put("/{crontab_id}/toggle", response_model=CrontabResponse)
def toggle_crontab(
    crontab_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """启用/禁用定时任务"""
    item = _get_crontab(crontab_id, db)
    item.enabled = not item.enabled
    log_audit(
        db, action="update", resource_type="crontab",
        resource_id=item.id, resource_name=item.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"toggle_enabled": item.enabled},
    )
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{crontab_id}")
def delete_crontab(
    crontab_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除定时任务（软删除）"""
    item = _get_crontab(crontab_id, db)
    item.soft_delete()
    log_audit(
        db, action="delete", resource_type="crontab",
        resource_id=item.id, resource_name=item.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"task": item.task},
    )
    db.commit()
    return {"message": "已删除"}


@router.post("/{crontab_id}/run")
def run_crontab_now(
    crontab_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """立即手动触发一次（不影响调度计划）"""
    item = _get_crontab(crontab_id, db)
    from app.celery_app import celery_app
    if item.task not in celery_app.tasks:
        raise HTTPException(400, f"Celery 任务不存在: {item.task}")
    result = celery_app.send_task(
        item.task, args=item.args or [], kwargs=item.kwargs or {},
        queue=item.queue or "default",
    )
    return {"message": "已触发", "task_id": result.id}
