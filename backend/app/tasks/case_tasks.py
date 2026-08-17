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

        # 执行生成
        agent = CaseGeneratorAgent(db_session=db, llm_config_id=task.llm_config_id)
        result = agent.generate(
            requirement_content=requirement_content,
            count=count,
            requirement_title=requirement_title,
            project_name=project_name,
            existing_count=existing_count,
        )

        # 保存用例
        cases_saved = 0
        for case_data in result.get("cases", []):
            try:
                case = TestCase(
                    project_id=project_id,
                    req_id=req_id,
                    title=case_data.get("title", ""),
                    module=case_data.get("module", "默认模块"),
                    priority=case_data.get("priority", "P2"),
                    case_type=case_data.get("case_type", "functional"),
                    preconditions=case_data.get("preconditions", ""),
                    steps=json.dumps(case_data.get("steps", []), ensure_ascii=False) if isinstance(case_data.get("steps"), list) else case_data.get("steps", "[]"),
                    expected_result=case_data.get("expected_result", ""),
                    bdd_content=case_data.get("bdd_content"),
                    created_by=task.created_by,
                )
                db.add(case)
                cases_saved += 1
            except Exception:
                continue

        db.commit()

        task.status = "success"
        task.output_result = {
            "case_count": len(result.get("cases", [])),
            "cases_saved": cases_saved,
        }
        task.llm_config_id = result.get("llm_config_id")
        task.token_usage = result.get("token_usage", {})
        task.completed_at = china_now_naive()
        db.commit()

        logger.info(f"用例生成任务完成: task_id={task_id}, saved={cases_saved}")

    except Exception as e:
        logger.error(f"用例生成任务失败: task_id={task_id}, error={e}", exc_info=True)
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
