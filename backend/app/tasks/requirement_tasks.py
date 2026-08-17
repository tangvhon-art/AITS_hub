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

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="generate_requirement", max_retries=2)
def generate_requirement_task(self, task_id: int):
    """AI 生成需求文档任务"""
    db = SessionLocal()
    try:
        task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if not task:
            logger.error(f"AgentTask not found: {task_id}")
            return

        task.status = "running"
        db.commit()

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

        # 保存需求
        requirement = TestRequirement(
            project_id=project_id,
            title=result.get("title", "AI 生成需求"),
            content=result.get("content", ""),
            source="ai",
            version_id=version_id,
            status="generated",
            created_by=task.created_by,
        )
        db.add(requirement)
        db.commit()
        db.refresh(requirement)

        task.status = "success"
        task.output_result = {
            "requirement_id": requirement.id,
            "title": requirement.title,
        }
        task.llm_config_id = result.get("llm_config_id")
        task.token_usage = result.get("token_usage", {})
        task.completed_at = china_now_naive()
        db.commit()

        logger.info(f"需求生成任务完成: task_id={task_id}, requirement_id={requirement.id}")

    except Exception as e:
        logger.error(f"需求生成任务失败: task_id={task_id}, error={e}", exc_info=True)
        try:
            task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
            if task:
                task.status = "failed"
                task.error_message = str(e)[:500]
                task.completed_at = china_now_naive()
                db.commit()
        except Exception:
            pass
    finally:
        db.close()
