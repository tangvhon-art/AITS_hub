"""
Celery 任务基类

统一 Celery 任务中的 Session 管理、状态更新、异常处理和失败通知。
消除各任务文件中重复的 try/except/finally 样板代码。

用法::

    from app.core.task_base import BaseTask
    from app.celery_app import celery_app

    class KnowledgeDocTask(BaseTask):
        task_name = "process_knowledge_doc"

        def execute(self, db, doc_id, project_id, agent_task_id=None):
            doc = db.query(KnowledgeDoc).filter(...).first()
            # 业务逻辑...
            return {"status": "success"}

    @celery_app.task(bind=True, name="process_knowledge_doc")
    def process_knowledge_doc_task(self, doc_id, project_id, agent_task_id=None):
        return KnowledgeDocTask().run(doc_id, project_id, agent_task_id=agent_task_id)
"""
import logging
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Optional

from app.database import SessionLocal

logger = logging.getLogger(__name__)


class BaseTask(ABC):
    """Celery 任务基类，统一 session 管理和异常处理。

    子类需实现 :meth:`execute` 方法编写具体业务逻辑。
    可选重写 :meth:`on_success` / :meth:`on_failure` 处理结果和通知。
    """

    task_name: str = "base_task"

    @contextmanager
    def get_db(self):
        """数据库会话上下文管理器，自动关闭会话。"""
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def run(self, *args: Any, **kwargs: Any) -> dict:
        """任务执行模板方法。

        流程：获取 session → 执行业务 → 成功回调 → 异常处理 → 关闭 session。

        Returns:
            统一格式的结果字典 {"status": "success"/"failed", ...}
        """
        try:
            with self.get_db() as db:
                result = self.execute(db, *args, **kwargs)
                self.on_success(db, result, *args, **kwargs)
                return result
        except Exception as e:
            logger.error(
                "[%s] 任务执行失败: %s",
                self.task_name,
                str(e),
                exc_info=True,
            )
            try:
                with self.get_db() as db:
                    self.on_failure(db, e, *args, **kwargs)
            except Exception as notify_e:
                logger.warning(
                    "[%s] 失败回调执行异常: %s",
                    self.task_name,
                    str(notify_e),
                )
            return {"status": "failed", "error": str(e)}

    @abstractmethod
    def execute(self, db: Any, *args: Any, **kwargs: Any) -> dict:
        """
        具体业务逻辑，子类必须实现。

        Args:
            db: 数据库会话
            *args, **kwargs: 任务参数

        Returns:
            结果字典，建议包含 "status" 字段
        """
        raise NotImplementedError

    def on_success(self, db: Any, result: dict, *args: Any, **kwargs: Any) -> None:
        """
        执行成功回调，可用于更新任务状态、发送通知等。

        默认不做任何操作，子类按需重写。

        Args:
            db: 数据库会话
            result: execute() 的返回值
        """
        pass

    def on_failure(self, db: Any, error: Exception, *args: Any, **kwargs: Any) -> None:
        """
        执行失败回调，可用于更新任务状态为 failed、发送失败通知等。

        默认不做任何操作，子类按需重写。

        Args:
            db: 数据库会话
            error: 捕获的异常对象
        """
        pass
