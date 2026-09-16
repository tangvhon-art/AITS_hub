"""
统一任务分发工具

封装 Celery 任务提交与线程降级逻辑，消除各路由中重复的
try: task.delay() except: Thread(target=...).start() 样板代码。

用法:
    from app.core.tasks import dispatch_task
    from app.tasks.test_plan_tasks import execute_test_plan_task

    dispatch_task(execute_test_plan_task, execution_id)
"""
import logging
import threading
from typing import Any, Callable, Optional, Tuple

logger = logging.getLogger(__name__)


def dispatch_task(
    task: Callable,
    *args: Any,
    callback: Optional[Callable[[bool, Optional[str]], None]] = None,
    **kwargs: Any,
) -> Tuple[bool, Optional[str]]:
    """
    提交 Celery 异步任务，失败时自动降级到后台线程同步执行。

    Args:
        task: Celery task 函数（需被 @celery_app.task 装饰）
        *args: 任务位置参数
        callback: 可选回调函数，签名为 callback(success: bool, celery_task_id: Optional[str])
        **kwargs: 任务关键字参数

    Returns:
        (use_celery, celery_task_id) 元组：
        - (True, task_id) 表示 Celery 提交成功
        - (False, None) 表示已降级到后台线程
    """
    try:
        task_result = task.delay(*args, **kwargs)
        celery_task_id = task_result.id
        logger.info(f"Celery 任务已提交: task={task.name}, task_id={celery_task_id}, args={args}")
        if callback:
            callback(True, celery_task_id)
        return True, celery_task_id
    except Exception as e:
        logger.warning(f"Celery 任务提交失败，降级到后台线程: task={getattr(task, 'name', task)}, error={e}")

        def _run_in_thread():
            try:
                # Celery task 对象可直接调用执行同步逻辑
                task(*args, **kwargs)
            except Exception as thread_e:
                logger.exception(f"后台线程执行任务失败: {thread_e}")

        thread = threading.Thread(target=_run_in_thread, daemon=True)
        thread.start()

        if callback:
            callback(False, None)
        return False, None
