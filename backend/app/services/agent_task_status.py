"""
AgentTask 状态防护工具

提供统一的 AgentTask 状态流转防护，支撑「手动取消」与「孤儿任务回收」：
- 用户手动取消后 AgentTask.status = canceled，任何任务函数在
  success/failed 收尾时都不得再覆盖该状态；
- 任务真正开始执行前检查是否已被取消，若已取消则直接中止，不再运行主逻辑。

用法（任务函数内）：
    from app.services.agent_task_status import mark_running, finalize_agent_task

    if not mark_running(db, task):   # 已被取消 → 中止
        db.commit()
        return
    ...
    finalize_agent_task(db, task, "success")
    db.commit()
"""
import logging

logger = logging.getLogger(__name__)


def mark_running(db, task) -> bool:
    """
    任务开始执行（pending/running -> running）。

    若任务已被用户取消（status == 'canceled'），返回 False 且不改状态，
    调用方应直接中止任务，避免执行已取消的任务。
    """
    if task is None or task.status == "canceled":
        return False
    task.status = "running"
    return True


def finalize_agent_task(db, task, status: str, error_message: str = None) -> bool:
    """
    设置 AgentTask 最终状态（success/failed）。

    防护：任务已被用户取消（status == 'canceled'）时不覆盖状态，返回 False。
    返回 True 表示状态已更新；返回 False 表示被取消/未更新。
    """
    if task is None:
        return False
    if task.status == "canceled":
        logger.info(f"AgentTask {getattr(task, 'id', '?')} 已被取消，跳过最终状态覆盖: {status}")
        return False
    if status not in ("success", "failed"):
        return False
    from app.core.timezone import china_now_naive
    task.status = status
    task.completed_at = china_now_naive()
    if status == "failed" and error_message:
        task.error_message = str(error_message)[:2000]
    return True
