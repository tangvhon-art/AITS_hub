"""
接口测试用例 AI 生成 Celery 任务
"""
import json
import logging
from app.celery_app import celery_app
from app.database import SessionLocal
from app.core.timezone import china_now_naive
from app.models.agent_task import AgentTask
from app.models.api_test import ApiDefinition
from app.services.api_case_generator import ApiCaseGenerator

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="generate_api_cases", max_retries=2)
def generate_api_cases_task(self, task_id: int):
    """
    AI生成接口测试用例任务
    """
    db = SessionLocal()
    try:
        task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if not task:
            logger.error(f"AgentTask not found: {task_id}")
            return

        # 更新状态为运行中
        task.status = "running"
        db.commit()

        input_params = task.input_params or {}
        api_id = input_params.get("api_id")
        strategy = input_params.get("strategy", "comprehensive")
        case_count = input_params.get("case_count", 5)
        coverage_scenarios = input_params.get("coverage_scenarios", [])
        assertion_depth = input_params.get("assertion_depth", "standard")

        # 获取接口定义
        api_definition = None
        if api_id:
            api_definition = db.query(ApiDefinition).filter(ApiDefinition.id == api_id).first()

        if not api_definition:
            task.status = "failed"
            task.error_message = "接口定义不存在"
            task.completed_at = china_now_naive()
            db.commit()
            return

        # 调用生成器
        generator = ApiCaseGenerator(db, llm_config_id=task.llm_config_id)

        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 在已运行的事件循环中，用新线程
                import threading
                result_container = {}

                def _run():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        result_container["result"] = new_loop.run_until_complete(
                            generator.generate_cases(
                                api_definition,
                                strategy=strategy,
                                case_count=case_count,
                                coverage_scenarios=coverage_scenarios,
                                assertion_depth=assertion_depth,
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
                generated_cases = result_container.get("result", [])
            else:
                generated_cases = loop.run_until_complete(
                    generator.generate_cases(
                        api_definition,
                        strategy=strategy,
                        case_count=case_count,
                        coverage_scenarios=coverage_scenarios,
                        assertion_depth=assertion_depth,
                    )
                )
        except RuntimeError:
            # 没有事件循环，创建新的
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                generated_cases = loop.run_until_complete(
                    generator.generate_cases(
                        api_definition,
                        strategy=strategy,
                        case_count=case_count,
                        coverage_scenarios=coverage_scenarios,
                        assertion_depth=assertion_depth,
                    )
                )
            finally:
                loop.close()

        # 转换结果
        cases_data = []
        for case in generated_cases:
            cases_data.append({
                "name": case.name,
                "priority": case.priority,
                "description": case.description,
                "request": case.request,
                "assertions": case.assertions,
            })

        # 更新任务结果
        task.status = "success"
        task.output_result = {"cases": cases_data, "count": len(cases_data)}
        task.completed_at = china_now_naive()
        db.commit()

        logger.info(f"AI生成用例任务完成: task_id={task_id}, count={len(cases_data)}")

    except Exception as e:
        logger.error(f"AI生成用例任务失败: task_id={task_id}, error={e}", exc_info=True)
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
