"""
接口测试用例 AI 生成 Celery 任务
"""
import logging

from app.celery_app import celery_app
from app.core.task_base import BaseTask
from app.core.timezone import china_now_naive
from app.models.agent_task import AgentTask
from app.models.api_test import ApiDefinition
from app.services.api_case_generator import ApiCaseGenerator
from app.services.notification_service import notify_event, notify_ai_task_failed
from app.services.agent_task_status import mark_running, finalize_agent_task

logger = logging.getLogger(__name__)


def _api_definition_to_dict(api: ApiDefinition) -> dict:
    """将 ApiDefinition ORM 对象转为字典，供 LLM prompt 使用"""
    return {
        "id": api.id,
        "name": api.name,
        "method": api.method,
        "path": api.path,
        "description": api.description or "",
        "tags": api.tags or "",
        "status": api.status or "draft",
        "headers": api.headers or [],
        "query_params": api.query_params or [],
        "path_params": api.path_params or [],
        "body_type": api.body_type or "none",
        "body_content": api.body_content or {},
        "response_examples": api.response_examples or [],
    }


class ApiCaseTask(BaseTask):
    """接口测试用例 AI 生成任务"""

    task_name = "generate_api_cases"

    def execute(self, db, task_id: int) -> dict:
        task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if not task:
            logger.error(f"AgentTask not found: {task_id}")
            return {"status": "aborted", "reason": "agent_task_not_found"}

        task.status = "running"
        db.commit()

        # 取消防护：任务已被用户取消则中止执行
        if not mark_running(db, task):
            db.commit()
            logger.info(f"接口用例生成任务已被取消，中止执行: task_id={task_id}")
            return {"status": "aborted", "reason": "cancelled"}

        input_params = task.input_params or {}
        api_id = input_params.get("api_id")
        strategy = input_params.get("strategy", "comprehensive")
        case_count = input_params.get("case_count", 5)
        coverage_scenarios = input_params.get("coverage_scenarios", [])
        assertion_depth = input_params.get("assertion_depth", "standard")
        prompt_id = input_params.get("prompt_id")

        api_def = db.query(ApiDefinition).filter(ApiDefinition.id == api_id).first() if api_id else None
        if not api_def:
            finalize_agent_task(db, task, "failed", "接口定义不存在")
            db.commit()
            return {"status": "failed", "reason": "api_def_not_found"}

        # 获取自定义 Prompt
        system_prompt = ""
        if prompt_id:
            from app.models.prompt import Prompt
            prompt_obj = db.query(Prompt).filter(Prompt.id == prompt_id).first()
            if prompt_obj:
                system_prompt = prompt_obj.system_prompt or ""
                logger.info(f"使用自定义 Prompt: {prompt_obj.name}")

        api_dict = _api_definition_to_dict(api_def)
        generator = ApiCaseGenerator(db, llm_config_id=task.llm_config_id)

        # 统一异步桥接：run_async 自动判断——当前线程无 running loop 时直接执行，
        # 有 running loop（eventlet 并发 greenlet 撞车）时调度到真实 OS 线程隔离执行，
        # 彻底规避 "Cannot run the event loop while another loop is running"。
        # （macOS 上 Celery worker 用 eventlet 协程池，threading.Thread 被 patch 成
        #   greenlet，所有任务挤在同一 OS 线程，见 app/core/async_runner.py）
        from app.core.async_runner import run_async

        gen_result = run_async(
            generator.generate,
            api_dict,
            strategy=strategy,
            case_count=case_count,
            coverage_scenarios=coverage_scenarios,
            assertion_depth=assertion_depth,
            system_prompt=system_prompt,
        )

        from app.services.content_extractor import ContentExtractor

        # 提取接口用例（多策略提取）
        cases = ContentExtractor.extract_api_cases(gen_result["raw_content"])

        # 自动落库：与需求/用例生成任务一致，把 AI 生成的接口用例直接写入 api_test_cases 表
        # （含请求头/参数/请求体/断言；此前仅存 output_result 等待前端手动"保存"，
        #   导致生成结果不落库）
        saved_case_ids = []
        if cases:
            from app.services.ai_creation_service import AICreationService
            saved_cases = AICreationService.create_api_cases(
                db,
                project_id=task.project_id,
                cases=cases,
                api_id=api_id,
                module_id=None,
                created_by=task.created_by,
            )
            saved_case_ids = [c.id for c in saved_cases]
            logger.info(f"AI接口用例已自动落库: task_id={task_id}, saved={len(saved_cases)}")

        finalize_agent_task(db, task, "success")
        task.output_result = {
            "cases": cases,
            "count": len(cases),
            "cases_saved": len(saved_case_ids),
            "saved_case_ids": saved_case_ids,
        }
        task.token_usage = gen_result.get("token_usage", {})
        task.llm_config_id = gen_result.get("llm_config_id")
        db.commit()

        logger.info(f"AI生成用例任务完成: task_id={task_id}, count={len(cases)}, saved={len(saved_case_ids)}")

        return {
            "status": "success",
            "task_id": task_id,
            "project_id": task.project_id,
            "created_by": task.created_by,
            "source_name": api_def.name if api_def else "接口",
            "strategy": strategy,
            "success_count": len(cases),
        }

    def on_success(self, db, result: dict, task_id: int) -> None:
        if result.get("status") != "success":
            return

        try:
            task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
            if not task:
                return
            duration = 0.0
            if task.created_at and task.completed_at:
                duration = round((task.completed_at - task.created_at).total_seconds(), 2)
            notify_event(
                result.get("project_id"),
                "ai.api_case.generated",
                {
                    "source_name": result.get("source_name") or "接口",
                    "strategy": result.get("strategy"),
                    "success_count": result.get("success_count", 0),
                    "failed_count": 0,
                    "duration": duration,
                },
                triggered_by=result.get("created_by"),
            )
        except Exception as notify_e:
            logger.warning(f"发送接口用例生成通知失败: {notify_e}")

    def on_failure(self, db, error: Exception, task_id: int) -> None:
        logger.error(f"AI生成用例任务失败: task_id={task_id}, error={error}", exc_info=True)
        try:
            task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
            if task:
                finalize_agent_task(db, task, "failed", str(error))
                db.commit()
                notify_ai_task_failed(
                    task.project_id,
                    task_type="接口用例生成",
                    error=str(error),
                    related_object="接口测试用例生成",
                    triggered_by=task.created_by,
                )
        except Exception:
            pass


@celery_app.task(bind=True, name="generate_api_cases", max_retries=2, queue="ai")
def generate_api_cases_task(self, task_id: int):
    """AI 生成接口测试用例任务"""
    return ApiCaseTask().run(task_id)
