"""
Celery 应用实例配置
使用 Redis 作为 broker 和 result backend
"""
import os
import platform

# macOS 下 fork + 线程/事件循环会导致 SIGABRT，禁用 fork 安全检查
if platform.system() == "Darwin":
    os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")

from celery import Celery
from app.config import settings

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
        "app.tasks.api_doc_tasks",
        "app.tasks.case_tasks",
        "app.tasks.notification_tasks",
        "app.tasks.requirement_tasks",
        "app.tasks.knowledge_tasks",
        "app.tasks.report_tasks",
        "app.tasks.review_tasks",
        "app.tasks.execution_tasks",
        "app.tasks.ui_healing_tasks",
    ],
)

# 导入任务包，触发 __init__.py 注册全部任务（worker / FastAPI / 脚本均生效）
import app.tasks  # noqa: E402

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
    # macOS 下使用 solo 池避免 fork 导致的 SIGABRT
    worker_pool="solo" if platform.system() == "Darwin" else "prefork",
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
    # 启用事件发送，Flower 依赖事件流检测 worker 和任务状态
    worker_send_task_events=True,
    task_send_sent_event=True,
    # 定时任务
    beat_schedule={
        "aggregate-ui-healing-knowledge": {
            "task": "app.tasks.ui_healing_tasks.aggregate_page_knowledge",
            "schedule": 3600.0,  # 每小时执行一次
            "args": (),
        },
    },
)


@celery_app.task(bind=True)
def debug_task(self):
    """调试任务，用于测试 Celery 是否正常工作"""
    print(f"Request: {self.request!r}")
    return {"status": "ok", "task_id": self.request.id}
