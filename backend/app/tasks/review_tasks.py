"""
用例评审 Celery 任务
"""
import logging

from app.celery_app import celery_app
from app.database import SessionLocal
from app.core.timezone import china_now_naive
from app.models.agent_task import AgentTask
from app.agents.case_reviewer import CaseReviewerAgent
from app.services.content_extractor import ContentExtractor
from app.services.notification_service import notify_event, notify_ai_task_failed

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="review_cases", max_retries=2)
def review_cases_task(self, task_id: int):
    """AI 用例评审任务"""
    db = SessionLocal()
    try:
        task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if not task:
            logger.error(f"AgentTask not found: {task_id}")
            return

        task.status = "running"
        db.commit()

        input_params = task.input_params or {}
        cases = input_params.get("cases", [])
        requirement = input_params.get("requirement", "")
        prompt_id = input_params.get("prompt_id")

        # 获取自定义 Prompt
        system_prompt = ""
        if prompt_id:
            from app.models.prompt import Prompt
            prompt_obj = db.query(Prompt).filter(Prompt.id == prompt_id).first()
            if prompt_obj:
                system_prompt = prompt_obj.system_prompt or ""
                logger.info(f"用例评审使用自定义 Prompt: {prompt_obj.name}")

        # 执行评审
        reviewer = CaseReviewerAgent(
            db, llm_config_id=task.llm_config_id, task_id=task.id, project_id=task.project_id
        )
        agent_result = reviewer.review(cases, requirement=requirement, system_prompt=system_prompt)

        from app.services.content_extractor import ContentExtractor
        extracted = ContentExtractor.extract_review(agent_result["raw_content"])
        result = {
            **extracted,
            "token_usage": agent_result.get("token_usage", {}),
            "llm_config_id": agent_result.get("llm_config_id"),
        }

        task.status = "success"
        task.output_result = result
        task.token_usage = result.get("token_usage", {})
        task.llm_config_id = result.get("llm_config_id")
        task.completed_at = china_now_naive()
        db.commit()

        logger.info(f"用例评审任务完成: task_id={task_id}, score={result.get('score')}")

        # 发送评审完成通知
        try:
            duration = 0.0
            if task.created_at and task.completed_at:
                duration = round((task.completed_at - task.created_at).total_seconds(), 2)
            notify_event(
                task.project_id,
                "ai.case_review.completed",
                {
                    "score": result.get("score"),
                    "passed": result.get("passed"),
                    "case_count": len(cases),
                    "duration": duration,
                },
                triggered_by=task.created_by,
            )
        except Exception as notify_e:
            logger.warning(f"发送用例评审通知失败: {notify_e}")

    except Exception as e:
        logger.error(f"用例评审任务失败: task_id={task_id}, error={e}", exc_info=True)
        try:
            task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
            if task:
                task.status = "failed"
                task.error_message = str(e)[:500]
                task.completed_at = china_now_naive()
                db.commit()
                notify_ai_task_failed(
                    task.project_id,
                    task_type="用例评审",
                    error=str(e),
                    related_object="用例评审",
                    triggered_by=task.created_by,
                )
        except Exception:
            pass
    finally:
        db.close()
