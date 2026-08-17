"""
测试用例 AI 生成 Celery 任务
"""
import json
import logging

from app.celery_app import celery_app
from app.database import SessionLocal
from app.core.timezone import china_now_naive
from app.models.agent_task import AgentTask
from app.models.test_case import TestCase
from app.models.project import Project
from app.models.requirement import TestRequirement
from app.agents.case_generator import CaseGeneratorAgent
from app.services.content_extractor import ContentExtractor
from app.services.ai_creation_service import AICreationService
from app.services.notification_service import notify_event, notify_ai_task_failed

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="generate_cases", max_retries=2)
def generate_cases_task(self, task_id: int):
    """AI 生成测试用例任务"""
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
        req_id = input_params.get("requirement_id")
        count = input_params.get("count", 10)
        content = input_params.get("content", "")
        prompt_id = input_params.get("prompt_id")

        # 获取需求信息
        requirement_content = content
        requirement_title = ""
        if req_id:
            req = db.query(TestRequirement).filter(
                TestRequirement.id == req_id,
                TestRequirement.project_id == project_id,
            ).first()
            if req:
                requirement_content = req.content or req.title or content
                requirement_title = req.title or ""

        # 获取项目名称
        project = db.query(Project).filter(Project.id == project_id).first()
        project_name = project.name if project else ""

        # 获取已有用例数
        existing_count = db.query(TestCase).filter(
            TestCase.project_id == project_id,
            TestCase.is_deleted == False,
        ).count()

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
        agent = CaseGeneratorAgent(db_session=db, llm_config_id=task.llm_config_id, project_id=project_id)
        result = agent.generate(
            requirement_content=requirement_content,
            count=count,
            requirement_title=requirement_title,
            project_name=project_name,
            existing_count=existing_count,
            system_prompt=system_prompt,
        )

        # 提取并创建用例（多策略提取，不做降级）
        cases = ContentExtractor.extract_test_cases(result["raw_content"])
        created_cases = AICreationService.create_test_cases(
            db,
            project_id=project_id,
            cases=cases,
            requirement_id=req_id,
            created_by=task.created_by,
        )

        task.status = "success"
        task.output_result = {
            "case_count": len(cases),
            "cases_saved": len(created_cases),
        }
        task.llm_config_id = result.get("llm_config_id")
        task.token_usage = result.get("token_usage", {})
        task.completed_at = china_now_naive()
        db.commit()

        logger.info(f"用例生成任务完成: task_id={task_id}, saved={len(created_cases)}")

        # 发送AI用例生成完成通知
        try:
            duration = 0.0
            if task.created_at and task.completed_at:
                duration = round((task.completed_at - task.created_at).total_seconds(), 2)
            source_name = requirement_title or "需求"
            notify_event(
                project_id,
                "ai.case.generated",
                {
                    "source_name": source_name,
                    "strategy": input_params.get("strategy", "comprehensive"),
                    "success_count": len(created_cases),
                    "failed_count": len(cases) - len(created_cases),
                    "duration": duration,
                },
                triggered_by=task.created_by,
            )
        except Exception as notify_e:
            logger.warning(f"发送用例生成通知失败: {notify_e}")

    except Exception as e:
        logger.error(f"用例生成任务失败: task_id={task_id}, error={e}", exc_info=True)
        try:
            task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
            if task:
                task.status = "failed"
                task.error_message = str(e)[:500]
                task.completed_at = china_now_naive()
                db.commit()
                notify_ai_task_failed(
                    task.project_id,
                    task_type="功能用例生成",
                    error=str(e),
                    related_object="测试用例生成",
                    triggered_by=task.created_by,
                )
        except Exception:
            pass
    finally:
        db.close()
