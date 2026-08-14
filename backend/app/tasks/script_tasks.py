"""
脚本执行相关的 Celery 任务
在独立 worker 进程中执行，完全不阻塞主服务
"""
import asyncio
import json
import time
import logging
from typing import Optional

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.test_run import TestRun
from app.models.automation_script import AutomationScript
from app.models.agent_task import AgentTask
from app.agents.script_generator import ScriptGenerator
from app.core.timezone import china_now_naive

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="run_automation_suite", max_retries=0)
def run_automation_suite_task(self, suite_run_id: int):
    """
    Celery 任务：执行自动化编排套件

    Args:
        suite_run_id: 编排执行记录ID
    """
    from app.agents.suite_executor import SuiteExecutor

    logger.info(f"开始执行编排任务: suite_run_id={suite_run_id}")
    try:
        executor = SuiteExecutor(suite_run_id)
        asyncio.run(executor.execute())
        logger.info(f"编排任务执行完成: suite_run_id={suite_run_id}")
        return {"status": "completed", "suite_run_id": suite_run_id}
    except Exception as e:
        logger.error(f"编排任务执行异常: suite_run_id={suite_run_id}, error={e}", exc_info=True)
        # 异常时更新执行记录状态
        db = SessionLocal()
        try:
            from app.models.automation_suite import AutomationSuiteRun
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


def _run_script_sync(
    content: str,
    script_id: int,
) -> tuple[bool, str]:
    """
    同步执行脚本（在独立事件循环中）
    返回 (是否成功, 错误信息)
    """
    try:
        local_vars = {}
        exec(compile(content, f"script_{script_id}.py", "exec"), local_vars)

        if "run_test" in local_vars and callable(local_vars["run_test"]):
            asyncio.run(local_vars["run_test"]())
        else:
            raise RuntimeError("脚本中未找到 run_test 函数")
        return True, ""
    except Exception as e:
        return False, str(e)


async def _execute_script_async(
    content: str,
    script_id: int,
) -> tuple[bool, str]:
    """异步执行脚本，使用线程池避免阻塞"""
    return await asyncio.to_thread(_run_script_sync, content, script_id)


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
    params: Optional[dict] = None,
):
    """
    Celery 任务：执行自动化脚本（支持AI自动修复）

    Args:
        run_id: 执行记录ID
        script_id: 脚本ID
        project_id: 项目ID
        script_content: 脚本内容
        script_name: 脚本名称
        target_url: 目标URL
        auto_fix: 是否自动修复
        max_retries: 最大重试次数
        params: 脚本参数
    """
    db = SessionLocal()
    try:
        run = db.query(TestRun).filter(TestRun.id == run_id).first()
        script = db.query(AutomationScript).filter(AutomationScript.id == script_id).first()
        if not run or not script:
            logger.error(f"任务执行失败: run={run_id} 或 script={script_id} 不存在")
            return {"status": "failed", "error": "执行记录或脚本不存在"}

        # 参数替换
        def apply_params(content: str) -> str:
            if params:
                for key, value in params.items():
                    content = content.replace(f"{{{{{key}}}}}", str(value))
            return content

        current_content = apply_params(script_content)
        start_time = time.time()
        start_datetime = run.started_at or china_now_naive()
        error_msg = ""
        status_result = "passed"
        retry_count = 0
        exec_log = [
            {
                "action": "script_run",
                "detail": f"执行脚本: {script_name}",
                "timestamp": start_time,
                "status": "running",
                "script_id": script_id,
                "worker": "celery",
            }
        ]

        # 首次执行
        success, error_msg = asyncio.run(_execute_script_async(current_content, script_id))
        duration = time.time() - start_time

        if success:
            exec_log.append({
                "action": "result",
                "detail": f"执行成功，耗时: {duration:.2f}s",
                "timestamp": time.time(),
                "status": "passed",
                "duration": round(duration, 3),
            })
        else:
            # 执行失败，记录首次失败
            exec_log.append({
                "action": "result",
                "detail": f"第1次执行失败，耗时: {duration:.2f}s, 错误: {error_msg}",
                "timestamp": time.time(),
                "status": "failed",
                "duration": round(duration, 3),
                "error": error_msg,
                "attempt": 1,
            })

            # 自动修复重试循环
            max_retries = max(0, max_retries)

            while not success and auto_fix and retry_count < max_retries:
                retry_count += 1
                logger.info(f"脚本 #{script_id} 执行失败，开始第 {retry_count} 次AI修复重试")
                exec_log.append({
                    "action": "ai_fix",
                    "detail": f"调用AI修复脚本（第{retry_count}次）",
                    "timestamp": time.time(),
                    "status": "running",
                    "attempt": retry_count,
                })

                # 创建 AgentTask 记录（AI修复脚本）
                fix_task = AgentTask(
                    project_id=project_id,
                    agent_type="script_fixer",
                    status="running",
                    input_params={
                        "script_id": script_id,
                        "script_name": script_name,
                        "run_id": run_id,
                        "attempt": retry_count,
                        "error_message": error_msg[:500],
                        "executor": "celery",
                    },
                    created_by=run.executed_by,
                )
                db.add(fix_task)
                db.flush()
                fix_task_id = fix_task.id
                db.commit()

                try:
                    # 调用AI修复脚本（异步调用）
                    fixed_content = asyncio.run(
                        ScriptGenerator.fix_script_with_ai(
                            script_content=current_content,
                            error_message=error_msg,
                            script_name=script_name,
                            target_url=target_url or "",
                            db_session=db,
                        )
                    )

                    if fixed_content == current_content:
                        exec_log.append({
                            "action": "ai_fix",
                            "detail": "AI修复未产生变化，停止重试",
                            "timestamp": time.time(),
                            "status": "skipped",
                            "attempt": retry_count,
                        })
                        fix_task = db.query(AgentTask).filter(AgentTask.id == fix_task_id).first()
                        if fix_task:
                            fix_task.status = "success"
                            fix_task.output_result = {"result": "no_change", "attempt": retry_count}
                            fix_task.completed_at = china_now_naive()
                            db.commit()
                        break

                    current_content = fixed_content
                    exec_log.append({
                        "action": "ai_fix",
                        "detail": f"AI修复完成，修复后脚本长度: {len(fixed_content)}",
                        "timestamp": time.time(),
                        "status": "success",
                        "attempt": retry_count,
                    })

                    # 使用修复后的脚本重新执行
                    retry_start = time.time()
                    success, error_msg = asyncio.run(_execute_script_async(current_content, script_id))
                    retry_duration = time.time() - retry_start

                    if success:
                        duration = time.time() - start_time
                        exec_log.append({
                            "action": "result",
                            "detail": f"第{retry_count + 1}次执行成功（修复后），耗时: {retry_duration:.2f}s",
                            "timestamp": time.time(),
                            "status": "passed",
                            "duration": round(retry_duration, 3),
                            "attempt": retry_count + 1,
                            "fixed": True,
                        })
                        status_result = "passed"
                        error_msg = ""

                        # 更新 AgentTask（修复成功）
                        fix_task = db.query(AgentTask).filter(AgentTask.id == fix_task_id).first()
                        if fix_task:
                            fix_task.status = "success"
                            fix_task.output_result = {"result": "fixed", "attempt": retry_count, "new_version": (script.version or 1) + 1}
                            fix_task.completed_at = china_now_naive()

                        # 修复成功后，更新脚本库中的脚本内容
                        try:
                            script.script_content = current_content
                            script.version = (script.version or 1) + 1
                            script.status = "active"
                            script.description = (script.description or "") + \
                                f"\n[自动修复] 执行失败后AI自动修复成功，版本升级至 v{script.version}"
                            db.commit()
                            exec_log.append({
                                "action": "script_updated",
                                "detail": f"脚本已自动更新至 v{script.version}",
                                "timestamp": time.time(),
                                "status": "success",
                                "new_version": script.version,
                            })
                            logger.info(f"脚本 #{script_id} 已自动修复并更新至 v{script.version}")
                        except Exception as update_e:
                            logger.warning(f"更新脚本库失败: {update_e}")
                            db.rollback()
                    else:
                        exec_log.append({
                            "action": "result",
                            "detail": f"第{retry_count + 1}次执行失败（修复后），耗时: {retry_duration:.2f}s, 错误: {error_msg}",
                            "timestamp": time.time(),
                            "status": "failed",
                            "duration": round(retry_duration, 3),
                            "error": error_msg,
                            "attempt": retry_count + 1,
                            "fixed": True,
                        })
                        fix_task = db.query(AgentTask).filter(AgentTask.id == fix_task_id).first()
                        if fix_task:
                            fix_task.status = "failed"
                            fix_task.error_message = f"修复后执行仍失败: {error_msg[:300]}"
                            fix_task.completed_at = china_now_naive()
                            db.commit()

                except Exception as fix_e:
                    error_msg = f"AI修复异常: {str(fix_e)}"
                    logger.error(f"AI修复脚本异常: {fix_e}", exc_info=True)
                    exec_log.append({
                        "action": "ai_fix",
                        "detail": f"AI修复异常: {str(fix_e)}",
                        "timestamp": time.time(),
                        "status": "failed",
                        "attempt": retry_count,
                    })
                    try:
                        fix_task = db.query(AgentTask).filter(AgentTask.id == fix_task_id).first()
                        if fix_task:
                            fix_task.status = "failed"
                            fix_task.error_message = str(fix_e)[:500]
                            fix_task.completed_at = china_now_naive()
                            db.commit()
                    except Exception:
                        pass
                    break

            if not success:
                status_result = "failed"
                duration = time.time() - start_time

        # 更新执行记录
        run.status = status_result
        run.error_message = error_msg
        run.duration = round(duration, 2)
        run.started_at = start_datetime
        run.completed_at = china_now_naive()
        run.execution_log = json.dumps(exec_log, ensure_ascii=False)
        db.commit()

        # 更新脚本统计
        script.total_runs = (script.total_runs or 0) + 1
        script.last_run_status = status_result
        script.last_run_at = china_now_naive()
        if status_result == "passed":
            script.pass_count = (script.pass_count or 0) + 1
        else:
            script.fail_count = (script.fail_count or 0) + 1
        db.commit()

        logger.info(
            f"脚本 #{script_id} Celery任务执行完成: "
            f"status={status_result}, duration={duration:.2f}s, retry_count={retry_count}"
        )

        return {
            "status": status_result,
            "run_id": run_id,
            "script_id": script_id,
            "duration": round(duration, 2),
            "error": error_msg,
            "auto_fixed": status_result == "passed" and retry_count > 0,
            "retry_count": retry_count,
        }

    except Exception as e:
        logger.error(f"Celery任务执行脚本异常: {e}", exc_info=True)
        try:
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
