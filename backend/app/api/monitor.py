"""
任务监控 API

使用 Celery inspect 实时获取 Worker 状态和活跃任务，结合数据库 AgentTask 记录，
提供比 Flower 事件流更可靠的监控数据。
"""
import time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.celery_app import celery_app
from app.models.agent_task import AgentTask
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/monitor", tags=["monitor"])


def _inspect():
    """获取 Celery inspect 对象，超时 2 秒"""
    return celery_app.control.inspect(timeout=2)


@router.get("/workers")
def list_workers(current_user: User = Depends(get_current_user)):
    """获取 Worker 节点列表及实时统计"""
    result = {}
    insp = _inspect()

    # 只调用必要的 3 个 inspect 方法，避免多次远程调用累积超时
    try:
        ping = insp.ping() or {}
    except Exception:
        ping = {}
    try:
        active = insp.active() or {}
    except Exception:
        active = {}
    try:
        stats = insp.stats() or {}
    except Exception:
        stats = {}

    # 合并所有 worker 名称
    all_workers = set(list(ping.keys()) + list(active.keys()) + list(stats.keys()))

    for worker_name in all_workers:
        w_stats = stats.get(worker_name, {})
        w_active = active.get(worker_name, [])
        w_ping = ping.get(worker_name)

        # 已处理任务总数（total 是 task_name->count 的 dict）
        total_completed = 0
        if isinstance(w_stats.get("total"), dict):
            total_completed = sum(w_stats["total"].values())
        # 并发数
        concurrency = w_stats.get("pool", {}).get("max-concurrency", 1)
        # PID
        pid = w_stats.get("pid", "-")
        # 负载
        loadavg = w_stats.get("loadavg", [0, 0, 0])

        result[worker_name] = {
            "status": "online" if w_ping else (w_stats and "online" or "offline"),
            "active": w_active,
            "active_count": len(w_active),
            "processed": total_completed,
            "tasks_total": total_completed,
            "concurrency": concurrency,
            "pid": pid,
            "loadavg": loadavg,
            "timestamp": time.time(),
        }

    return result


@router.get("/tasks")
def list_tasks(limit: int = 100, state: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取任务列表（活跃任务 + 最近数据库记录）"""
    result = {}
    insp = _inspect()

    # 1. 实时活跃任务（来自 Celery inspect）
    try:
        active = insp.active() or {}
    except Exception:
        active = {}
    try:
        reserved = insp.reserved() or {}
    except Exception:
        reserved = {}

    now = time.time()
    for worker_name, task_list in active.items():
        for t in task_list:
            tid = t.get("id", "")
            if not tid:
                continue
            started = t.get("time_start", now)
            result[tid] = {
                "uuid": tid,
                "name": t.get("name", ""),
                "state": "STARTED",
                "worker": worker_name,
                "received": t.get("time_start", now),
                "started": started,
                "runtime": round(now - started, 2) if started else 0,
                "args": t.get("args", ""),
                "kwargs": t.get("kwargs", ""),
                "acknowledged": t.get("acknowledged", False),
            }

    for worker_name, task_list in reserved.items():
        for t in task_list:
            tid = t.get("id", "")
            if not tid or tid in result:
                continue
            result[tid] = {
                "uuid": tid,
                "name": t.get("name", ""),
                "state": "PENDING",
                "worker": worker_name,
                "received": t.get("time_start", now),
                "started": None,
                "runtime": 0,
                "args": t.get("args", ""),
                "kwargs": t.get("kwargs", ""),
            }

    # 2. 最近完成的任务（来自数据库 AgentTask）
    query = db.query(AgentTask).filter(AgentTask.is_deleted == False)
    if state:
        state_map = {"SUCCESS": "success", "FAILURE": "failed", "STARTED": "running", "PENDING": "pending"}
        db_state = state_map.get(state, state.lower())
        query = query.filter(AgentTask.status == db_state)
    query = query.order_by(AgentTask.created_at.desc()).limit(limit)
    db_tasks = query.all()

    for t in db_tasks:
        # Celery 状态映射
        state_map = {"pending": "PENDING", "running": "STARTED", "success": "SUCCESS", "failed": "FAILURE", "retrying": "RETRY"}
        celery_state = state_map.get(t.status, t.status.upper())
        # 如果已在活跃列表中，跳过（用实时数据）
        if str(t.id) in result:
            continue
        received_ts = t.created_at.timestamp() if t.created_at else 0
        completed_ts = t.completed_at.timestamp() if t.completed_at else None
        runtime = 0
        if received_ts and completed_ts:
            runtime = round(completed_ts - received_ts, 2)

        result[str(t.id)] = {
            "uuid": str(t.id),
            "name": t.agent_type or "",
            "state": celery_state,
            "worker": "-",
            "received": received_ts,
            "started": received_ts,
            "runtime": runtime,
            "result": t.output_result,
            "exception": t.error_message,
            "args": "",
            "kwargs": "",
            "project_id": t.project_id,
            "created_by": t.created_by,
        }

    # 按状态筛选
    if state:
        result = {k: v for k, v in result.items() if v.get("state") == state}

    return result


@router.get("/tasks/{task_id}")
def get_task(task_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取任务详情"""
    # 先查数据库
    try:
        tid_int = int(task_id)
        db_task = db.query(AgentTask).filter(AgentTask.id == tid_int, AgentTask.is_deleted == False).first()
        if db_task:
            state_map = {"pending": "PENDING", "running": "STARTED", "success": "SUCCESS", "failed": "FAILURE"}
            received_ts = db_task.created_at.timestamp() if db_task.created_at else 0
            completed_ts = db_task.completed_at.timestamp() if db_task.completed_at else None
            runtime = round((completed_ts - received_ts), 2) if completed_ts and received_ts else 0
            return {
                "uuid": str(db_task.id),
                "name": db_task.agent_type or "",
                "state": state_map.get(db_task.status, db_task.status.upper()),
                "worker": "-",
                "received": received_ts,
                "started": received_ts,
                "runtime": runtime,
                "result": db_task.output_result,
                "exception": db_task.error_message,
                "project_id": db_task.project_id,
            }
    except (ValueError, TypeError):
        pass

    # 查 Celery result backend
    try:
        async_result = celery_app.AsyncResult(task_id)
        return {
            "uuid": task_id,
            "name": "",
            "state": async_result.state,
            "worker": "-",
            "received": 0,
            "started": None,
            "runtime": 0,
            "result": async_result.result if async_result.successful() else None,
            "exception": str(async_result.result) if async_result.failed() else None,
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"任务不存在: {e}")


@router.post("/tasks/{task_id}/revoke")
def revoke_task(task_id: str, terminate: bool = False, current_user: User = Depends(get_current_user)):
    """撤销任务"""
    try:
        celery_app.control.revoke(task_id, terminate=terminate)
        return {"message": "撤销指令已发送", "task_id": task_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"撤销失败: {e}")
