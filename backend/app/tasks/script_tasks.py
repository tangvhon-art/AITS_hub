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
from app.services.notification_service import notify_event

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="run_automation_suite", max_retries=0, queue="execution")
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

        # 发送套件完成通知
        try:
            db = SessionLocal()
            try:
                run = db.query(AutomationSuiteRun).filter(
                    AutomationSuiteRun.id == suite_run_id
                ).first()
                if run:
                    from app.models.automation_suite import AutomationSuite
                    suite = db.query(AutomationSuite).filter(
                        AutomationSuite.id == run.suite_id
                    ).first()
                    duration = 0.0
                    if run.started_at and run.completed_at:
                        duration = round((run.completed_at - run.started_at).total_seconds(), 2)
                    notify_event(
                        run.project_id,
                        "ui.suite.completed",
                        {
                            "suite_id": run.suite_id,
                            "suite_name": suite.name if suite else "未知套件",
                            "run_id": run.id,
                            "total_steps": run.total_steps or 0,
                            "passed_steps": run.passed_steps or 0,
                            "failed_steps": run.failed_steps or 0,
                            "duration": duration,
                            "ai_fix_count": getattr(run, "ai_fix_count", 0) or 0,
                        },
                        triggered_by=getattr(run, "triggered_by", None),
                    )
            finally:
                db.close()
        except Exception as notify_e:
            logger.warning(f"发送套件完成通知失败（不影响业务）: {notify_e}")

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


@celery_app.task(bind=True, name="run_automation_script", max_retries=0, queue="execution")
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

        # 单脚本执行失败时发送通知（成功不通知，避免刷屏）
        try:
            if result and not result.get("success", False):
                notify_event(
                    project_id,
                    "ui.script.failed",
                    {
                        "script_id": script_id,
                        "script_name": script_name,
                        "run_id": run_id,
                        "failed_step": result.get("failed_step", "-"),
                        "error": result.get("error") or result.get("error_message", "脚本执行失败"),
                        "ai_fix_triggered": bool(result.get("ai_fix_triggered", False)),
                        "ai_fix_result": result.get("ai_fix_result", "-"),
                        "duration": result.get("duration", 0),
                    },
                )
        except Exception as notify_e:
            logger.warning(f"发送脚本失败通知失败（不影响业务）: {notify_e}")

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

            # 异常也发送失败通知
            notify_event(
                project_id,
                "ui.script.failed",
                {
                    "script_id": script_id,
                    "script_name": script_name,
                    "run_id": run_id,
                    "failed_step": "-",
                    "error": str(e),
                    "ai_fix_triggered": False,
                    "ai_fix_result": "-",
                    "duration": 0,
                },
            )
        except Exception:
            pass
        return {"status": "failed", "error": str(e)}
    finally:
        db.close()
