"""
孤儿任务回收

把「长时间停留在 running、但进程实际已中断/超时」的任务自动标记为 failed，
避免任务监控的“执行中”统计被僵尸任务污染。

判定口径：AgentTask.status == 'running' 且 created_at 早于当前时间 - 超时阈值
（任务创建后长时间未完成即视为异常中断；阈值需大于正常任务最长执行时长）。
eval_tasks 同理：status == 'running' 且 started_at 早于阈值。

触发方式：
1. Beat 周期任务（sys_crontab 注册 interval 任务，见 register 逻辑/已入库记录）；
2. worker 启动时（celery_app.py worker_ready 信号）兜底执行一次；
3. 手动调用 recycle_orphan_tasks()（幂等）。
"""
import logging
from datetime import timedelta

from app.core.timezone import china_now_naive
from app.database import SessionLocal
from app.models.agent_task import AgentTask
from app.models.eval import EvalTask

logger = logging.getLogger(__name__)

# 回收超时阈值（分钟）：正常任务（含 AI 测评长任务）一般远小于该值
RECYCLE_TIMEOUT_MINUTES = 30


def recycle_orphan_tasks(timeout_minutes: int = RECYCLE_TIMEOUT_MINUTES) -> dict:
    """
    回收孤儿任务（幂等，可重复执行）：
    - agent_tasks: running 且创建超过 timeout_minutes 分钟 → failed
    - eval_tasks:  running 且开始超过 timeout_minutes 分钟 → failed
    Returns: {"agent_tasks": n, "eval_tasks": m}
    """
    db = SessionLocal()
    recycled = {"agent_tasks": 0, "eval_tasks": 0}
    try:
        cutoff = china_now_naive() - timedelta(minutes=timeout_minutes)
        # ── AgentTask ──
        orphans = (
            db.query(AgentTask)
            .filter(AgentTask.status == "running", AgentTask.created_at < cutoff)
            .all()
        )
        for t in orphans:
            t.status = "failed"
            t.completed_at = china_now_naive()
            base = t.error_message or ""
            suffix = "任务超时/进程中断，已被孤儿任务回收机制标记为失败"
            t.error_message = (f"{base} | {suffix}") if base else suffix
            recycled["agent_tasks"] += 1
            logger.info(f"孤儿任务回收: agent_tasks id={t.id} type={t.agent_type} → failed")
        # ── EvalTask（AI 测评）──
        eval_orphans = (
            db.query(EvalTask)
            .filter(EvalTask.status == "running", EvalTask.started_at < cutoff)
            .all()
        )
        for t in eval_orphans:
            t.status = "failed"
            t.completed_at = china_now_naive()
            t.summary = (t.summary or "") + (" | " if t.summary else "") + "任务超时/进程中断，已被孤儿任务回收机制标记为失败"
            recycled["eval_tasks"] += 1
            logger.info(f"孤儿任务回收: eval_tasks id={t.id} → failed")
        db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("孤儿任务回收失败: %s", e)
    finally:
        db.close()
    if recycled["agent_tasks"] or recycled["eval_tasks"]:
        logger.info(f"孤儿任务回收完成: {recycled}")
    else:
        logger.info("孤儿任务回收：无超时任务")
    return recycled
