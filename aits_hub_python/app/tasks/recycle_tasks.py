"""
孤儿任务回收定时任务

由 sys_crontab 调度（interval 300s，queue=default），
把长时间停留在 running 的任务自动标记为 failed，防止僵尸任务污染执行中统计。
"""
import logging

from app.celery_app import celery_app
from app.services.orphan_recycle import recycle_orphan_tasks as _recycle_impl

logger = logging.getLogger(__name__)


@celery_app.task(name="recycle_orphan_tasks", max_retries=0, queue="default")
def recycle_orphan_tasks():
    """孤儿任务回收（幂等）：超时 running → failed"""
    return _recycle_impl()
