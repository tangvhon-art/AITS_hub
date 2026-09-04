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
        "app.tasks.cleanup_tasks",
        "app.tasks.workflow_tasks",
        "app.tasks.eval_tasks",
    ],
)

# 导入任务包，触发 __init__.py 注册全部任务（worker / FastAPI / 脚本均生效）
import app.tasks  # noqa: E402

from kombu import Queue

# Celery 配置
celery_app.conf.update(
    # 任务队列划分：ai(AI生成类) / execution(执行类) / eval(AI测评类) / default(后台轻量)
    task_queues=(
        Queue("default", routing_key="task.#"),
        Queue("ai", routing_key="ai.#"),
        Queue("execution", routing_key="execution.#"),
        Queue("eval", routing_key="eval.#"),
    ),
    task_default_queue="default",
    task_default_routing_key="task.default",
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
    # macOS 下使用 solo 池避免 fork 导致的 SIGABRT（solo 池不支持 autoscale，并发固定为1）
    worker_pool="solo" if platform.system() == "Darwin" else "prefork",
    # 默认并发数（仅作为未指定并发参数时的兼容兑底）：
    # Linux 生产环境命令行 --autoscale=MAX,MIN 会覆盖此值，动态扩缩容；
    # autoscale 数值不在此写死，由各队列 worker 启动命令自行指定
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
    # 任务开始执行时自动更新状态为 STARTED 并发送 STARTED 事件
    # （否则 Flower/TaskMonitor 中任务 state 停留在 PENDING/RECEIVED，无法正确统计“执行中”）
    task_track_started=True,
    # 定时任务：改用数据库驱动的自定义 Scheduler，任务清单存于 sys_crontab 表，
    # 新增/修改/删除/启停无需重启 beat（原固定 beat_schedule 已迁移入库，
    # 见 migrations/sys_crontab.sql）。⚠️ beat 必须单实例运行，否则会重复派发任务！
    beat_scheduler="app.services.crontab_scheduler:DatabaseScheduler",
)


@celery_app.task(bind=True)
def debug_task(self):
    """调试任务，用于测试 Celery 是否正常工作"""
    print(f"Request: {self.request!r}")
    return {"status": "ok", "task_id": self.request.id}


# ---------------------------------------------------------------------------
# 任务执行日志记录（sys_celery_task_log）
# worker 进程通过 celery signals 自动写入，供任务调度管理页面查询。
# 日志写入失败不影响任务本身执行（全部 try/except 兑底）。
# ---------------------------------------------------------------------------
import logging as _logging  # noqa: E402

from celery.signals import (  # noqa: E402
    task_prerun, task_postrun, task_failure, worker_ready,
    worker_init, worker_process_init,
)

_task_log_logger = _logging.getLogger(__name__)

# 不记录日志的内置/高频任务，避免噪音
_TASK_LOG_IGNORE_PREFIXES = ("celery.",)


def _task_log_db():
    from app.database import SessionLocal
    return SessionLocal()


@task_prerun.connect
def _log_task_prerun(sender=None, task_id=None, args=None, kwargs=None, request=None, **kw):
    """任务开始：插入 RUNNING 记录"""
    task_name = getattr(sender, "name", "") or ""
    if task_name.startswith(_TASK_LOG_IGNORE_PREFIXES):
        return
    try:
        from app.models.celery_task_log import CeleryTaskLog
        from app.core.timezone import china_now_naive
        queue = None
        try:
            # worker 消费时从任务当前请求上下文取真实 routing_key
            # （本版本 celery 无 get_current_request，用 Task.request 属性）
            req = getattr(sender, "request", None)
            delivery_info = getattr(req, "delivery_info", None) or {}
            queue = delivery_info.get("routing_key") or None
        except Exception:
            pass
        if not queue:
            try:
                delivery_info = getattr(request, "delivery_info", None) or {}
                queue = delivery_info.get("routing_key") or None
            except Exception:
                pass
        if not queue:
            try:
                queue = (getattr(sender, "queue", None)
                         or (getattr(sender, "options", None) or {}).get("queue")
                         or "default")
            except Exception:
                queue = "default"
        # 关联定时任务唯一标识（beat 派发的任务按任务名匹配 sys_crontab）
        task_key = None
        try:
            from app.models.sys_crontab import SysCrontab
            db_lookup = _task_log_db()
            try:
                row = db_lookup.query(SysCrontab).filter(
                    SysCrontab.task == task_name, SysCrontab.is_deleted == False  # noqa: E712
                ).first()
                task_key = row.task_key if row else None
            finally:
                db_lookup.close()
        except Exception:
            pass
        db = _task_log_db()
        try:
            db.add(CeleryTaskLog(
                task_name=task_name,
                task_key=task_key,
                task_id=str(task_id),
                args=list(args or []),
                kwargs=dict(kwargs or {}),
                queue=queue,
                state="RUNNING",
                started_at=china_now_naive(),
            ))
            db.commit()
        finally:
            db.close()
    except Exception as e:
        _task_log_logger.debug(f"任务日志写入失败(prerun): {e}")


@task_failure.connect
def _log_task_failure(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kw):
    """任务失败：记录异常信息与状态（超时异常标记为 TIMEOUT）"""
    task_name = getattr(sender, "name", "") or ""
    if task_name.startswith(_TASK_LOG_IGNORE_PREFIXES):
        return
    try:
        from app.models.celery_task_log import CeleryTaskLog
        from celery.exceptions import SoftTimeLimitExceeded, TimeLimitExceeded
        state = "TIMEOUT" if isinstance(exception, (SoftTimeLimitExceeded, TimeLimitExceeded)) else "FAILURE"
        db = _task_log_db()
        try:
            db.query(CeleryTaskLog).filter(CeleryTaskLog.task_id == str(task_id)).update(
                {
                    "state": state,
                    "exception": str(exception)[:2000] if exception else None,
                    "traceback": str(einfo or traceback)[:8000] if (einfo or traceback) else None,
                },
                synchronize_session=False,
            )
            db.commit()
        finally:
            db.close()
    except Exception as e:
        _task_log_logger.debug(f"任务日志写入失败(failure): {e}")


@task_postrun.connect
def _log_task_postrun(sender=None, task_id=None, state=None, **kw):
    """任务结束：回写结束时间/耗时；仅成功时置 SUCCESS，避免覆盖 FAILURE/TIMEOUT"""
    task_name = getattr(sender, "name", "") or ""
    if task_name.startswith(_TASK_LOG_IGNORE_PREFIXES):
        return
    try:
        from app.models.celery_task_log import CeleryTaskLog
        from app.core.timezone import china_now_naive
        now = china_now_naive()
        db = _task_log_db()
        try:
            q = db.query(CeleryTaskLog).filter(CeleryTaskLog.task_id == str(task_id))
            if state == "SUCCESS":
                q.update({"state": "SUCCESS", "finished_at": now}, synchronize_session=False)
            else:
                q.update({"finished_at": now}, synchronize_session=False)
            db.commit()
            # 补算耗时（单独更新，避免复杂 SQL）
            row = db.query(CeleryTaskLog).filter(CeleryTaskLog.task_id == str(task_id)).first()
            if row and row.started_at and row.finished_at:
                row.duration_ms = int((row.finished_at - row.started_at).total_seconds() * 1000)
                db.commit()
        finally:
            db.close()
    except Exception as e:
        _task_log_logger.debug(f"任务日志写入失败(postrun): {e}")


@worker_ready.connect
def _recycle_orphan_on_worker_ready(sender=None, **kw):
    """
    Worker 启动时兜底回收孤儿任务（幂等）：
    防止 worker 重启/中断后遗留的 running 任务污染“执行中”统计。
    超时判定（created_at 超过阈值）不会误伤其它仍在正常运行的 worker 任务。
    """
    try:
        from app.services.orphan_recycle import recycle_orphan_tasks
        recycle_orphan_tasks()
    except Exception as e:  # noqa: BLE001
        logger = __import__("logging").getLogger(__name__)
        logger.warning(f"worker_ready 孤儿任务回收失败: {e}")


# ---------------------------------------------------------------------------
# 统一 async 兜底保护：安装 asyncio.run 安全包装
# 规避 eventlet 协程池下「同一 OS 线程多个 running event loop」导致的
# "Cannot run the event loop while another loop is running"。
# worker_init：单进程池（solo/eventlet）主进程触发；
# worker_process_init：prefork 每个子进程触发。两者都注册以覆盖各池类型。
# 详见 app/core/async_runner.py。
# ---------------------------------------------------------------------------

def _install_worker_asyncio_guard(**kw):
    try:
        from app.core.async_runner import install_worker_asyncio_guard as _install
        _install()
    except Exception as e:  # noqa: BLE001
        _task_log_logger.warning(f"安装 asyncio 兜底保护失败（不影响任务执行）: {e}")


worker_init.connect(_install_worker_asyncio_guard)
worker_process_init.connect(_install_worker_asyncio_guard)
