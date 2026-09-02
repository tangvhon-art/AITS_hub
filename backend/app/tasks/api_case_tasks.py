"""
接口测试用例 AI 生成 Celery 任务
"""
import asyncio
import logging
import threading

from app.celery_app import celery_app
from app.database import SessionLocal
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


@celery_app.task(bind=True, name="generate_api_cases", max_retries=2, queue="ai")
def generate_api_cases_task(self, task_id: int):
    """AI 生成接口测试用例任务"""
    db = SessionLocal()
    try:
        task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if not task:
            logger.error(f"AgentTask not found: {task_id}")
            return

        task.status = "running"
        db.commit()

        # 取消防护：任务已被用户取消则中止执行
        if not mark_running(db, task):
            db.commit()
            logger.info(f"接口用例生成任务已被取消，中止执行: task_id={task_id}")
            return

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
            return

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

        result_container = {}

        def _run():
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                result_container["result"] = new_loop.run_until_complete(
                    generator.generate(
                        api_dict,
                        strategy=strategy,
                        case_count=case_count,
                        coverage_scenarios=coverage_scenarios,
                        assertion_depth=assertion_depth,
                        system_prompt=system_prompt,
                    )
                )
            except Exception as e:
                result_container["error"] = str(e)
            finally:
                new_loop.close()

        thread = threading.Thread(target=_run)
        thread.start()
        thread.join(timeout=300)

        if "error" in result_container:
            raise Exception(result_container["error"])

        from app.services.content_extractor import ContentExtractor

        gen_result = result_container.get("result", {"raw_content": "", "token_usage": {}, "llm_config_id": None})

        # 提取接口用例（多策略提取，不做降级；创建由"保存"端点处理）
        cases = ContentExtractor.extract_api_cases(gen_result["raw_content"])

        finalize_agent_task(db, task, "success")
        task.output_result = {"cases": cases, "count": len(cases)}
        task.token_usage = gen_result.get("token_usage", {})
        task.llm_config_id = gen_result.get("llm_config_id")
        db.commit()

        logger.info(f"AI生成用例任务完成: task_id={task_id}, count={len(cases)}")

        # 发送AI接口用例生成完成通知
        try:
            duration = 0.0
            if task.created_at and task.completed_at:
                duration = round((task.completed_at - task.created_at).total_seconds(), 2)
            notify_event(
                task.project_id,
                "ai.api_case.generated",
                {
                    "source_name": api_def.name if api_def else "接口",
                    "strategy": strategy,
                    "success_count": len(cases),
                    "failed_count": 0,
                    "duration": duration,
                },
                triggered_by=task.created_by,
            )
        except Exception as notify_e:
            logger.warning(f"发送接口用例生成通知失败: {notify_e}")

    except Exception as e:
        logger.error(f"AI生成用例任务失败: task_id={task_id}, error={e}", exc_info=True)
        try:
            task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
            if task:
                finalize_agent_task(db, task, "failed", str(e))
                db.commit()
                notify_ai_task_failed(
                    task.project_id,
                    task_type="接口用例生成",
                    error=str(e),
                    related_object="接口测试用例生成",
                    triggered_by=task.created_by,
                )
        except Exception:
            pass
    finally:
        db.close()
