import logging
from app.celery_app import celery_app
from app.database import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="run_performance_test", max_retries=0)
def run_performance_test_task(
    self,
    run_id: int,
    test_config: dict,
    target_url: str,
    method: str,
    headers: dict,
    body: str = None,
    test_data: list = None,
):
    """异步执行性能测试"""
    db = SessionLocal()
    try:
        from app.services.performance_runner import PerformanceRunner
        runner = PerformanceRunner(db)
        result = runner.run(
            run_id=run_id,
            test_config=test_config,
            target_url=target_url,
            method=method,
            headers=headers,
            body=body,
            test_data=test_data,
        )
        logger.info(f"性能测试执行完成: run_id={run_id}, status={result.get('status')}")
        return result
    except Exception as e:
        logger.error(f"性能测试执行失败: run_id={run_id}, error={e}", exc_info=True)
        try:
            from app.models.performance_test import PerformanceTest, PerformanceTestRun
            from app.core.timezone import china_now_naive
            run = db.query(PerformanceTestRun).filter(PerformanceTestRun.id == run_id).first()
            if run:
                run.status = "failed"
                run.finished_at = china_now_naive()
                run.error_summary = {"error": str(e)[:500]}
                test = db.query(PerformanceTest).filter(PerformanceTest.id == run.test_id).first()
                if test:
                    test.status = "failed"
                db.commit()
        except Exception:
            pass
        return {"status": "failed", "error": str(e)}
    finally:
        # 安全防护：确保测试状态不卡在 running
        try:
            from app.models.performance_test import PerformanceTest, PerformanceTestRun
            run = db.query(PerformanceTestRun).filter(PerformanceTestRun.id == run_id).first()
            if run and run.test_id:
                test = db.query(PerformanceTest).filter(PerformanceTest.id == run.test_id).first()
                if test and test.status == "running":
                    running_count = db.query(PerformanceTestRun).filter(
                        PerformanceTestRun.test_id == test.id,
                        PerformanceTestRun.status == "running",
                    ).count()
                    if running_count == 0:
                        test.status = "completed"
                        db.commit()
                        logger.info(f"安全防护：测试 #{test.id} 状态从 running 修正为 completed")
        except Exception:
            pass
        db.close()
