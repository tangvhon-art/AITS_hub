"""
Celery 应用实例配置
使用 Redis 作为 broker 和 result backend
"""
from celery import Celery
from app.config import settings
import os

# 获取项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

celery_app = Celery(
    "aits_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.script_tasks",
        "app.tasks.api_case_tasks",
        "app.tasks.test_plan_tasks",
        "app.tasks.performance_tasks",
    ],
)

celery_app.autodiscover_tasks(["app.tasks"])

# Celery 配置
celery_app.conf.update(
    # 任务序列化
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # 时区
    timezone="Asia/Shanghai",
    enable_utc=False,
    # 任务执行超时（秒）
    task_time_limit=600,
    task_soft_time_limit=540,
    # 结果过期时间（1小时）
    result_expires=3600,
    # 并发 worker 数
    worker_concurrency=4,
    # 任务预取数
    worker_prefetch_multiplier=1,
    # 每个 worker 执行多少任务后重启（防止内存泄漏）
    worker_max_tasks_per_child=100,
    # 任务重试
    task_default_retry_delay=30,
    task_max_retries=3,
    # 日志
    worker_log_format="[%(asctime)s] [%(levelname)s] [%(processName)s] %(message)s",
    worker_task_log_format="[%(asctime)s] [%(levelname)s] [%(task_name)s:%(task_id)s] %(message)s",
)


@celery_app.task(bind=True)
def debug_task(self):
    """调试任务，用于测试 Celery 是否正常工作"""
    print(f"Request: {self.request!r}")
    return {"status": "ok", "task_id": self.request.id}
