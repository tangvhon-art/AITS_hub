"""
脚本执行相关的 Celery 任务
在独立 worker 进程中执行，完全不阻塞主服务
"""
import asyncio
import logging

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.automation_suite import AutomationSuiteRun
from app.core.timezone import china_now_naive
from app.services.script_runner import (
    apply_headless_mode as _apply_headless_mode,
    execute_script_with_ai_fix,
)

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="run_automation_suite", max_retries=0)
def run_automation_suite_task(self, suite_run_id: int, headless: bool = True):
    """
    Celery 任务：执行自动化编排套件

    Args:
        suite_run_id: 编排执行记录ID
    """
    from app.agents.suite_executor import SuiteExecutor

    logger.info(f"开始执行编排任务: suite_run_id={suite_run_id}, headless={headless}")
    try:
        executor = SuiteExecutor(suite_run_id, headless=headless)
        asyncio.run(executor.execute())
        logger.info(f"编排任务执行完成: suite_run_id={suite_run_id}")
        return {"status": "completed", "suite_run_id": suite_run_id}
    except Exception as e:
        logger.error(f"编排任务执行异常: suite_run_id={suite_run_id}, error={e}", exc_info=True)
        db = SessionLocal()
        try:
            run = db.query(AutomationSuiteRun).filter(
                AutomationSuiteRun.id == suite_run_id
            ).first()
            if run and run.status == "running":
                run.status = "failed"
                run.error_message = f"Celery任务异常: {str(e)}"
                run.completed_at = china_now_naive()
                db.commit()
        except Exception:
            pass
        finally:
            db.close()
        return {"status": "failed", "suite_run_id": suite_run_id, "error": str(e)}


@celery_app.task(bind=True, name="run_automation_script", max_retries=0)
def run_automation_script_task(
    self,
    run_id: int,
    script_id: int,
    project_id: int,
    script_content: str,
    script_name: str,
    target_url: str = "",
    auto_fix: bool = True,
    max_retries: int = 2,
    params: dict = None,
    headless: bool = True,
):
    """
    Celery 任务：执行自动化脚本（支持AI自动修复）
    委托给 script_runner 统一服务执行
    """
    db = SessionLocal()
    try:
        result = asyncio.run(
            execute_script_with_ai_fix(
                db=db,
                run_id=run_id,
                script_id=script_id,
                project_id=project_id,
                script_content=script_content,
                script_name=script_name,
                target_url=target_url,
                auto_fix=auto_fix,
                max_retries=max_retries,
                params=params,
                headless=headless,
                executor="celery",
            )
        )
        return result
    except Exception as e:
        logger.error(f"Celery任务执行脚本异常: {e}", exc_info=True)
        try:
            from app.models.test_run import TestRun
            run = db.query(TestRun).filter(TestRun.id == run_id).first()
            if run:
                run.status = "failed"
                run.error_message = f"任务执行异常: {str(e)}"
                run.completed_at = china_now_naive()
                db.commit()
        except Exception:
            pass
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()
