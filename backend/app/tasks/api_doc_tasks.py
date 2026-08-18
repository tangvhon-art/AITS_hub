"""
接口文档 AI 生成 Celery 任务
"""
import asyncio
import logging
import threading

from app.celery_app import celery_app
from app.database import SessionLocal
from app.core.timezone import china_now_naive
from app.models.agent_task import AgentTask
from app.models.api_test import ApiDefinition
from app.services.api_doc_generator import ApiDocGenerator
from app.services.notification_service import notify_event, notify_ai_task_failed

logger = logging.getLogger(__name__)


def _api_definition_to_dict(api: ApiDefinition) -> dict:
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


@celery_app.task(bind=True, name="generate_api_doc", max_retries=2)
def generate_api_doc_task(self, task_id: int):
    """AI 生成接口文档任务"""
    db = SessionLocal()
    try:
        task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if not task:
            logger.error(f"AgentTask not found: {task_id}")
            return

        task.status = "running"
        db.commit()

        input_params = task.input_params or {}
        api_id = input_params.get("api_id")
        prompt_id = input_params.get("prompt_id")
        supplement_info = input_params.get("supplement_info", "")

        api_def = db.query(ApiDefinition).filter(ApiDefinition.id == api_id).first() if api_id else None
        if not api_def:
            task.status = "failed"
            task.error_message = "接口定义不存在"
            task.completed_at = china_now_naive()
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
        generator = ApiDocGenerator(db, llm_config_id=task.llm_config_id)

        result_container = {}

        def _run():
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                result_container["result"] = new_loop.run_until_complete(
                    generator.generate(api_dict, system_prompt=system_prompt, supplement_info=supplement_info)
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

        markdown_content, token_usage, used_config_id = result_container.get("result", ("", {}, None))

        if not markdown_content:
            raise ValueError("AI 返回的文档内容为空")

        # 跨线程后重新查询，确保 session 对象状态正常
        db.expire_all()
        api_def = db.query(ApiDefinition).filter(ApiDefinition.id == api_id).first()
        if not api_def:
            raise ValueError("接口定义不存在")

        # 回写到接口描述字段
        api_def.description = markdown_content
        api_def.updated_at = china_now_naive()

        task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        task.status = "success"
        task.output_result = {"documentation": markdown_content}
        task.token_usage = token_usage
        task.completed_at = china_now_naive()
        db.commit()
        db.refresh(api_def)

        logger.info(f"AI生成接口文档任务完成: task_id={task_id}, desc_len={len(markdown_content)}, saved_desc={api_def.description is not None}")

        # 发送AI接口文档生成完成通知
        try:
            duration = 0.0
            if task.created_at and task.completed_at:
                duration = round((task.completed_at - task.created_at).total_seconds(), 2)
            notify_event(
                task.project_id,
                "ai.api_doc.generated",
                {
                    "api_id": api_def.id if api_def else None,
                    "api_name": api_def.name if api_def else "接口",
                    "method": (api_def.method or "").upper() if api_def else "",
                    "path": api_def.path if api_def else "",
                    "success": True,
                    "duration": duration,
                },
                triggered_by=task.created_by,
            )
        except Exception as notify_e:
            logger.warning(f"发送接口文档生成通知失败: {notify_e}")

    except Exception as e:
        logger.error(f"AI生成接口文档任务失败: task_id={task_id}, error={e}", exc_info=True)
        try:
            task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
            if task:
                task.status = "failed"
                task.error_message = str(e)[:500]
                task.completed_at = china_now_naive()
                db.commit()
                notify_ai_task_failed(
                    task.project_id,
                    task_type="接口文档生成",
                    error=str(e),
                    related_object="接口文档生成",
                    triggered_by=task.created_by,
                )
        except Exception:
            pass
    finally:
        db.close()
