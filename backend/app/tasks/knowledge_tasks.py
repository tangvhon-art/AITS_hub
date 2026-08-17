"""
知识库处理相关的 Celery 任务
在独立 worker 进程中执行文档分块、向量化、存入FAISS
"""
import logging
from typing import Optional

from app.celery_app import celery_app
from app.core.task_base import BaseTask
from app.models.knowledge_doc import KnowledgeDoc
from app.models.agent_task import AgentTask
from app.services.knowledge_base import knowledge_base_service
from app.core.timezone import china_now_naive
from app.services.notification_service import notify_event, notify_ai_task_failed

logger = logging.getLogger(__name__)


class KnowledgeDocTask(BaseTask):
    """知识库文档处理任务"""

    task_name = "process_knowledge_doc"

    def execute(
        self,
        db,
        doc_id: int,
        project_id: int,
        agent_task_id: Optional[int] = None,
    ) -> dict:
        """
        处理知识库文档（文本分块 + 向量化 + 存入FAISS）

        Args:
            db: 数据库会话
            doc_id: 知识库文档ID
            project_id: 项目ID
            agent_task_id: 关联的 AgentTask ID（可选）
        """
        doc = db.query(KnowledgeDoc).filter(KnowledgeDoc.id == doc_id).first()
        if not doc:
            logger.error(f"知识库文档不存在: doc_id={doc_id}")
            return {"status": "failed", "error": "文档不存在", "doc_id": doc_id}

        logger.info(f"开始处理知识库文档: doc_id={doc_id}, title={doc.title}")

        # 调用知识库服务处理
        result = knowledge_base_service.add_document(
            project_id=project_id,
            doc_id=doc.id,
            title=doc.title,
            content=doc.content,
        )

        if result.get("success"):
            doc.status = "ready"
            doc.chunk_count = result.get("chunk_count", 0)
            logger.info(f"知识库文档处理成功: doc_id={doc_id}, chunks={doc.chunk_count}")
        else:
            doc.status = "failed"
            doc.error_message = result.get("error", "")
            logger.error(f"知识库文档处理失败: doc_id={doc_id}, error={doc.error_message}")

        # 更新关联的 AgentTask
        if agent_task_id:
            agent_task = db.query(AgentTask).filter(AgentTask.id == agent_task_id).first()
            if agent_task:
                if result.get("success"):
                    agent_task.status = "success"
                    agent_task.output_result = {"chunk_count": result.get("chunk_count", 0)}
                else:
                    agent_task.status = "failed"
                    agent_task.error_message = result.get("error", "")
                agent_task.completed_at = china_now_naive()

        db.commit()

        return {
            "status": "success" if result.get("success") else "failed",
            "doc_id": doc_id,
            "chunk_count": result.get("chunk_count", 0),
            "error": result.get("error", ""),
        }

    def on_success(
        self,
        db,
        result: dict,
        doc_id: int,
        project_id: int,
        agent_task_id: Optional[int] = None,
    ) -> None:
        """发送知识库文档处理完成通知"""
        if result.get("status") == "failed":
            # 业务层面失败（如文档不存在），不发送成功通知
            return

        try:
            doc = db.query(KnowledgeDoc).filter(KnowledgeDoc.id == doc_id).first()
            if not doc:
                return

            file_type = getattr(doc, "file_type", None) or "-"
            file_size = getattr(doc, "file_size", None)
            file_size_str = f"{round(file_size / 1024, 1)}KB" if file_size else "-"
            kb_triggered_by = None
            if agent_task_id:
                at = db.query(AgentTask).filter(AgentTask.id == agent_task_id).first()
                if at:
                    kb_triggered_by = at.created_by
            notify_event(
                project_id,
                "knowledge.doc_processed",
                {
                    "doc_id": doc.id,
                    "doc_name": doc.title,
                    "file_type": file_type,
                    "file_size": file_size_str,
                    "success": bool(result.get("status") == "success"),
                    "chunk_count": result.get("chunk_count", 0),
                    "error": result.get("error", ""),
                },
                triggered_by=kb_triggered_by,
            )
        except Exception as notify_e:
            logger.warning(f"发送知识库处理通知失败: {notify_e}")

    def on_failure(
        self,
        db,
        error: Exception,
        doc_id: int,
        project_id: int,
        agent_task_id: Optional[int] = None,
    ) -> None:
        """异常处理：更新文档和 AgentTask 状态为 failed，发送失败通知"""
        try:
            doc = db.query(KnowledgeDoc).filter(KnowledgeDoc.id == doc_id).first()
            if doc:
                doc.status = "failed"
                doc.error_message = str(error)
            if agent_task_id:
                agent_task = db.query(AgentTask).filter(AgentTask.id == agent_task_id).first()
                if agent_task:
                    agent_task.status = "failed"
                    agent_task.error_message = str(error)
                    agent_task.completed_at = china_now_naive()
                    notify_ai_task_failed(
                        project_id,
                        task_type="知识库文档处理",
                        error=str(error),
                        related_object=doc.title if doc else "知识库文档",
                        triggered_by=agent_task.created_by,
                    )
            db.commit()
        except Exception:
            pass


@celery_app.task(bind=True, name="process_knowledge_doc", max_retries=0)
def process_knowledge_doc_task(self, doc_id: int, project_id: int, agent_task_id: Optional[int] = None):
    """
    Celery 任务：处理知识库文档（文本分块 + 向量化 + 存入FAISS）

    Args:
        doc_id: 知识库文档ID
        project_id: 项目ID
        agent_task_id: 关联的 AgentTask ID（可选）
    """
    return KnowledgeDocTask().run(doc_id, project_id, agent_task_id=agent_task_id)
