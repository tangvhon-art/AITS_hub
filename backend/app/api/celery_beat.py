"""
任务调度管理（Celery Beat 可视化管理）API

数据源为 sys_crontab 表，Beat 的自定义 DatabaseScheduler 每 5 秒轮询，
增删改/启停保存后自动热生效，无需重启 beat/worker。
执行日志来自 sys_celery_task_log（worker 通过 celery signals 自动写入）。

⚠️ Beat 必须单实例运行，多个 beat 进程会重复派发任务。
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_user, require_admin
from app.core.audit import log_audit
from app.models.user import User
from app.models.sys_crontab import SysCrontab
from app.models.celery_task_log import CeleryTaskLog
from app.schemas.celery_beat import (
    BeatTaskCreate,
    BeatTaskUpdate,
    BeatTaskStatus,
    BeatTaskRunOnce,
    BeatTaskResponse,
    BeatTaskListResponse,
    BeatTaskLogResponse,
    BeatTaskLogListResponse,
)

router = APIRouter(
    prefix="/api/celery/beat",
    tags=["任务调度管理"],
    dependencies=[Depends(require_admin)],
)

ALLOWED_QUEUES = ("default", "ai", "execution", "eval")
ALLOWED_SCHEDULE_TYPES = ("interval", "cron")
ALLOWED_LOG_STATES = ("RUNNING", "SUCCESS", "FAILURE", "TIMEOUT")


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _parse_schedule_expr(schedule_type: str, schedule_expr: str) -> dict:
    """解析调度表达式为 sys_crontab 字段"""
    expr = (schedule_expr or "").strip()
    if not expr:
        raise HTTPException(400, "调度值不能为空")

    if schedule_type == "interval":
        try:
            seconds = int(expr)
        except ValueError:
            raise HTTPException(400, "固定间隔必须为正整数秒数")
        if seconds <= 0:
            raise HTTPException(400, "固定间隔必须为正整数秒数")
        return {"every_seconds": seconds}

    # cron：5 段标准表达式（分 时 日 月 周）
    parts = expr.split()
    if len(parts) != 5:
        raise HTTPException(400, "CRON 表达式必须为 5 段：分 时 日 月 周（如 0 2 * * *）")
    from celery.schedules import crontab as celery_crontab
    try:
        celery_crontab(
            minute=parts[0], hour=parts[1],
            day_of_month=parts[2], month_of_year=parts[3], day_of_week=parts[4],
        )
    except ValueError as e:
        raise HTTPException(400, f"CRON 表达式非法: {e}")
    return {
        "minute": parts[0], "hour": parts[1],
        "day_of_month": parts[2], "month_of_year": parts[3], "day_of_week": parts[4],
    }


def _build_schedule_expr(item: SysCrontab) -> str:
    """由 sys_crontab 字段生成展示用调度表达式"""
    if item.schedule_type == "interval":
        return str(item.every_seconds) if item.every_seconds else ""
    return f"{item.minute} {item.hour} {item.day_of_month} {item.month_of_year} {item.day_of_week}"


def _to_response(item: SysCrontab) -> BeatTaskResponse:
    return BeatTaskResponse(
        id=item.id,
        name=item.name,
        task_key=item.task_key,
        task=item.task,
        schedule_type=item.schedule_type,
        schedule_expr=_build_schedule_expr(item),
        queue=item.queue or "default",
        args=item.args or [],
        kwargs=item.kwargs or {},
        description=item.description or "",
        enabled=bool(item.enabled),
        last_run_at=item.last_run_at,
        total_run_count=item.total_run_count or 0,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _validate_task(task: str):
    """校验任务函数全路径已在 celery 注册"""
    from app.celery_app import celery_app
    if task not in celery_app.tasks:
        raise HTTPException(400, f"Celery 任务不存在: {task}")


def _check_task_key_unique(db: Session, task_key: str, exclude_id: Optional[int] = None):
    q = db.query(SysCrontab).filter(
        SysCrontab.task_key == task_key, SysCrontab.is_deleted == False  # noqa: E712
    )
    if exclude_id is not None:
        q = q.filter(SysCrontab.id != exclude_id)
    if q.first():
        raise HTTPException(400, f"任务唯一标识已存在: {task_key}")


def _get_task(task_id: int, db: Session) -> SysCrontab:
    item = db.query(SysCrontab).filter(
        SysCrontab.id == task_id, SysCrontab.is_deleted == False  # noqa: E712
    ).first()
    if not item:
        raise HTTPException(404, "定时任务不存在")
    return item


# ---------------------------------------------------------------------------
# 定时任务配置管理
# ---------------------------------------------------------------------------

@router.get("/list", response_model=BeatTaskListResponse)
def list_beat_tasks(
    page: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """定时任务分页列表"""
    query = db.query(SysCrontab).filter(SysCrontab.is_deleted == False)  # noqa: E712
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            (SysCrontab.name.like(like)) | (SysCrontab.task_key.like(like)) | (SysCrontab.task.like(like))
        )
    total = query.count()
    items = (
        query.order_by(SysCrontab.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return BeatTaskListResponse(
        total=total, page=page, page_size=page_size,
        items=[_to_response(i) for i in items],
    )


@router.post("/create", response_model=BeatTaskResponse)
def create_beat_task(
    data: BeatTaskCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """新增定时任务（保存后 beat 最长 5 秒内自动生效）"""
    if data.schedule_type not in ALLOWED_SCHEDULE_TYPES:
        raise HTTPException(400, f"调度类型必须为: {', '.join(ALLOWED_SCHEDULE_TYPES)}")
    if data.queue not in ALLOWED_QUEUES:
        raise HTTPException(400, f"执行队列必须为: {', '.join(ALLOWED_QUEUES)}")
    _check_task_key_unique(db, data.task_key)
    _validate_task(data.task)
    schedule_fields = _parse_schedule_expr(data.schedule_type, data.schedule_expr)

    item = SysCrontab(
        name=data.name,
        task_key=data.task_key,
        task=data.task,
        args=data.args or [],
        kwargs=data.kwargs or {},
        queue=data.queue,
        schedule_type=data.schedule_type,
        enabled=data.enabled,
        description=data.description,
        created_by=current_user.id,
    )
    if data.schedule_type == "cron":
        item.minute = "*"
        item.hour = "*"
        item.day_of_week = "*"
        item.day_of_month = "*"
        item.month_of_year = "*"
    for k, v in schedule_fields.items():
        setattr(item, k, v)
    db.add(item)
    db.flush()
    log_audit(
        db, action="create", resource_type="celery_beat",
        resource_id=item.id, resource_name=item.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"task_key": item.task_key, "task": item.task, "schedule_type": item.schedule_type},
    )
    db.commit()
    db.refresh(item)
    return _to_response(item)


@router.put("/update", response_model=BeatTaskResponse)
def update_beat_task(
    data: BeatTaskUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """编辑定时任务（保存后 beat 最长 5 秒内自动生效，无需重启）"""
    item = _get_task(data.id, db)
    update_data = data.model_dump(exclude_unset=True)
    update_data.pop("id", None)

    if "task_key" in update_data and update_data["task_key"] != item.task_key:
        _check_task_key_unique(db, update_data["task_key"], exclude_id=item.id)
    if "task" in update_data and update_data["task"] != item.task:
        _validate_task(update_data["task"])
    if "queue" in update_data and update_data["queue"] not in ALLOWED_QUEUES:
        raise HTTPException(400, f"执行队列必须为: {', '.join(ALLOWED_QUEUES)}")

    # 调度类型/表达式：以"已有配置 + 本次变更"合并后整体解析校验
    schedule_type = update_data.get("schedule_type", item.schedule_type)
    if schedule_type not in ALLOWED_SCHEDULE_TYPES:
        raise HTTPException(400, f"调度类型必须为: {', '.join(ALLOWED_SCHEDULE_TYPES)}")
    if "schedule_expr" in update_data or "schedule_type" in update_data:
        schedule_expr = update_data.get("schedule_expr") or _build_schedule_expr(item)
        schedule_fields = _parse_schedule_expr(schedule_type, schedule_expr)
        update_data.pop("schedule_expr", None)
        # 切换类型时先重置另一类字段，再写入本次解析结果
        if schedule_type == "interval":
            item.minute = item.hour = item.day_of_week = item.day_of_month = item.month_of_year = "*"
            item.every_seconds = None
        else:
            item.every_seconds = None
        for k, v in schedule_fields.items():
            setattr(item, k, v)
        item.schedule_type = schedule_type
        update_data.pop("schedule_type", None)

    before = {k: getattr(item, k) for k in update_data}
    for key, value in update_data.items():
        setattr(item, key, value)
    log_audit(
        db, action="update", resource_type="celery_beat",
        resource_id=item.id, resource_name=item.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"before": before, "after": update_data},
    )
    db.commit()
    db.refresh(item)
    return _to_response(item)


@router.patch("/status", response_model=BeatTaskResponse)
def toggle_beat_task_status(
    data: BeatTaskStatus,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """启用/禁用定时任务"""
    item = _get_task(data.id, db)
    item.enabled = data.enabled
    log_audit(
        db, action="update", resource_type="celery_beat",
        resource_id=item.id, resource_name=item.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"enabled": item.enabled},
    )
    db.commit()
    db.refresh(item)
    return _to_response(item)


@router.delete("/delete")
def delete_beat_task(
    id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除定时任务（软删除）"""
    item = _get_task(id, db)
    item.soft_delete()
    log_audit(
        db, action="delete", resource_type="celery_beat",
        resource_id=item.id, resource_name=item.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"task_key": item.task_key, "task": item.task},
    )
    db.commit()
    return {"message": "已删除"}


@router.post("/run-once")
def run_beat_task_once(
    data: BeatTaskRunOnce,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """手动执行一次任务（单次触发，不改动定时规则）"""
    item = _get_task(data.id, db)
    from app.celery_app import celery_app
    if item.task not in celery_app.tasks:
        raise HTTPException(400, f"Celery 任务不存在: {item.task}")
    result = celery_app.send_task(
        item.task, args=item.args or [], kwargs=item.kwargs or {},
        queue=item.queue or "default",
    )
    return {"message": "已触发", "task_id": result.id}


# ---------------------------------------------------------------------------
# 任务执行日志查询
# ---------------------------------------------------------------------------

@router.get("/logs", response_model=BeatTaskLogListResponse)
def list_beat_task_logs(
    page: int = 1,
    page_size: int = 20,
    task_name: Optional[str] = None,
    state: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """任务执行日志分页列表（支持时间范围/任务名称/状态筛选）"""
    query = db.query(CeleryTaskLog).filter(CeleryTaskLog.is_deleted == False)  # noqa: E712
    if task_name:
        like = f"%{task_name}%"
        query = query.filter(
            (CeleryTaskLog.task_name.like(like)) | (CeleryTaskLog.task_key.like(like))
        )
    if state:
        if state not in ALLOWED_LOG_STATES:
            raise HTTPException(400, f"执行状态必须为: {', '.join(ALLOWED_LOG_STATES)}")
        query = query.filter(CeleryTaskLog.state == state)
    if start_time:
        query = query.filter(CeleryTaskLog.created_at >= start_time)
    if end_time:
        query = query.filter(CeleryTaskLog.created_at <= end_time)
    total = query.count()
    items = (
        query.order_by(CeleryTaskLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return BeatTaskLogListResponse(
        total=total, page=page, page_size=page_size,
        items=[BeatTaskLogResponse.model_validate(i) for i in items],
    )


@router.get("/log-detail/{task_id}", response_model=BeatTaskLogResponse)
def get_beat_task_log_detail(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """单条执行日志详情（含完整参数/日志/错误堆栈）"""
    item = db.query(CeleryTaskLog).filter(
        CeleryTaskLog.task_id == task_id, CeleryTaskLog.is_deleted == False  # noqa: E712
    ).order_by(CeleryTaskLog.id.desc()).first()
    if not item:
        raise HTTPException(404, "执行日志不存在")
    return BeatTaskLogResponse.model_validate(item)
