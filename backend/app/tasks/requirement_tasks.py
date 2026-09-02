"""
需求文档 AI 生成 Celery 任务
"""
import logging

from app.celery_app import celery_app
from app.database import SessionLocal
from app.core.timezone import china_now_naive
from app.models.agent_task import AgentTask
from app.models.requirement import TestRequirement
from app.models.project import Project
from app.agents.requirement_generator import RequirementGeneratorAgent
from app.services.content_extractor import ContentExtractor
from app.services.ai_creation_service import AICreationService
from app.services.notification_service import notify_event, notify_ai_task_failed
from app.services.agent_task_status import mark_running, finalize_agent_task
from app.services.workflow_connector import WorkflowInvokeError
from app.services.workflow_runner import run as workflow_run
from app.services.agent_backend_dispatcher import resolve_backend

logger = logging.getLogger(__name__)

MODULE_ID = "requirement.generate"


@celery_app.task(bind=True, name="generate_requirement", max_retries=2, queue="ai")
def generate_requirement_task(self, task_id: int):
    """AI 生成需求文档任务"""
    db = SessionLocal()
    try:
        task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if not task:
            logger.error(f"AgentTask not found: {task_id}")
            return

        # ── 执行后端分发：页面选择优先 → 模块配置 → local ──
        page_choice = (task.input_params or {}).get("page_backend")
        backend = resolve_backend(db, MODULE_ID, task.project_id, page_choice=page_choice)
        task.backend = backend
        db.commit()

        if backend == "workflow":
            try:
                workflow_run(db, task, MODULE_ID)
                # 受理成功：任务挂起，等待 Webhook 回调（不执行本地 LLM）
                return
            except WorkflowInvokeError as e:
                logger.warning(f"需求生成 workflow 调用失败，降级 local: {e}")
                task.backend = "local"
                task.status = "pending"
                task.error_message = f"workflow 降级: {e}"[:500]
                db.commit()
                # fall through 到 local 逻辑

        task.status = "running"
        db.commit()

        # 取消防护：任务已被用户取消则中止执行
        if not mark_running(db, task):
            db.commit()
            logger.info(f"需求生成任务已被取消，中止执行: task_id={task_id}")
            return

        input_params = task.input_params or {}
        project_id = task.project_id
        description = input_params.get("description", "")
        prompt_id = input_params.get("prompt_id")
        version_id = input_params.get("version_id")

        # 获取项目名称
        project = db.query(Project).filter(Project.id == project_id).first()
        project_name = project.name if project else ""

        # 获取自定义 Prompt
        system_prompt = ""
        if prompt_id:
            from app.models.prompt import Prompt
            prompt_obj = db.query(Prompt).filter(
                Prompt.id == prompt_id,
            ).first()
            if prompt_obj:
                system_prompt = prompt_obj.system_prompt or ""
                logger.info(f"使用自定义 Prompt: {prompt_obj.name}")

        # 执行生成
        agent = RequirementGeneratorAgent(db_session=db, llm_config_id=task.llm_config_id, project_id=project_id)
        result = agent.generate(
            user_input=description,
            project_name=project_name,
            system_prompt=system_prompt,
        )

        # 提取内容并创建需求（多策略提取，不做降级）
        extracted = ContentExtractor.extract_requirement(result["raw_content"])
        requirement = AICreationService.create_requirement(
            db,
            project_id=project_id,
            title=extracted["title"],
            content=extracted["content"],
            version_id=version_id,
            created_by=task.created_by,
        )

        finalize_agent_task(db, task, "success")
        task.output_result = {
            "requirement_id": requirement.id,
            "title": requirement.title,
        }
        task.llm_config_id = result.get("llm_config_id")
        task.token_usage = result.get("token_usage", {})
        db.commit()

        logger.info(f"需求生成任务完成: task_id={task_id}, requirement_id={requirement.id}")

        # 发送AI需求生成完成通知
        try:
            duration = 0.0
            if task.created_at and task.completed_at:
                duration = round((task.completed_at - task.created_at).total_seconds(), 2)
            version_name = "-"
            if version_id:
                from app.models.project_version import ProjectVersion
                ver = db.query(ProjectVersion).filter(ProjectVersion.id == version_id).first()
                if ver:
                    version_name = ver.name
            notify_event(
                project_id,
                "ai.requirement.generated",
                {
                    "requirement_id": requirement.id,
                    "requirement_title": requirement.title,
                    "version_name": version_name,
                    "success": True,
                    "duration": duration,
                },
                triggered_by=task.created_by,
            )
        except Exception as notify_e:
            logger.warning(f"发送需求生成通知失败: {notify_e}")

    except Exception as e:
        logger.error(f"需求生成任务失败: task_id={task_id}, error={e}", exc_info=True)
        try:
            task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
            if task:
                finalize_agent_task(db, task, "failed", str(e))
                db.commit()
                # 发送AI任务失败通知
                notify_ai_task_failed(
                    task.project_id,
                    task_type="需求生成",
                    error=str(e),
                    related_object="需求文档生成",
                    triggered_by=task.created_by,
                )
        except Exception:
            pass
    finally:
        db.close()
