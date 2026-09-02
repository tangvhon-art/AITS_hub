"""
UI 自动化执行 Celery 任务

将 ExecutionAgent 的浏览器启动逻辑从 Web 服务器进程隔离到 Celery worker，
执行日志增量写入数据库，前端通过轮询获取。
"""
import json
import time
import asyncio

from app.celery_app import celery_app
from app.core.timezone import china_now_naive
from app.services.agent_task_status import finalize_agent_task
from app.database import SessionLocal


@celery_app.task(bind=True, name="run_ui_execution", max_retries=0, queue="execution")
def run_ui_execution_task(
    self,
    run_id: int,
    agent_task_id: int,
    project_id: int,
    instruction: str,
    target_url: str,
    headless: bool,
    llm_config_id: int | None,
    case_id: int | None,
    user_id: int,
):
    """在 Celery worker 中执行 UI 自动化，日志增量写入数据库"""

    db = SessionLocal()
    start_time = time.time()
    final_status = "failed"
    final_result = ""
    error_message = ""
    execution_duration = 0.0
    all_events: list = []

    try:
        from app.agents.execution_agent import ExecutionAgent

        agent = ExecutionAgent(db_session=db, llm_config_id=llm_config_id, project_id=project_id)

        # 同步运行 async 生成器
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async def _run():
                nonlocal final_status, final_result, error_message, execution_duration
                async for event in agent.execute(
                    instruction=instruction,
                    target_url=target_url,
                    headless=headless,
                ):
                    all_events.append(event)

                    if event.get("type") == "finish":
                        final_status = event.get("status", "failed")
                        final_result = event.get("result", "")
                        if final_status == "failed":
                            error_message = final_result
                    elif event.get("type") == "complete":
                        execution_duration = event.get("duration", 0.0)
                    elif event.get("type") == "error":
                        error_message = event.get("message", "")

                    # 增量写入日志（每步都更新，前端轮询可见）
                    _update_run_log(db, run_id, all_events)

            loop.run_until_complete(_run())
        finally:
            loop.close()

        # 状态归一化
        if final_status.lower() in ("success", "ok", "pass", "passed", "complete", "completed"):
            final_status = "passed"
        elif final_status.lower() in ("fail", "failed", "error"):
            final_status = "failed"
        else:
            final_status = "failed" if error_message else "passed"

        # 自动生成脚本
        script_id = _save_generated_script(
            db, project_id, run_id, case_id, instruction,
            target_url, user_id, agent,
        )

        # 更新最终状态
        _finalize_run(db, run_id, agent_task_id, final_status, final_result,
                       error_message, execution_duration, agent, script_id)

    except Exception as e:
        error_message = f"执行异常终止: {str(e)}"
        _handle_failure(db, run_id, agent_task_id, error_message, time.time() - start_time)
    finally:
        db.close()


def _update_run_log(db, run_id: int, events: list):
    """增量更新执行日志"""
    try:
        from app.models.test_run import TestRun
        run = db.query(TestRun).filter(TestRun.id == run_id).first()
        if run:
            run.execution_log = json.dumps(events, ensure_ascii=False)
            db.commit()
    except Exception:
        db.rollback()


def _save_generated_script(db, project_id, run_id, case_id, instruction,
                           target_url, user_id, agent) -> int | None:
    """保存自动生成的脚本"""
    script_id = None
    try:
        from app.models.test_case import TestCase
        from app.models.automation_script import AutomationScript
        from app.agents.script_generator import ScriptGenerator

        execution_log = agent.get_execution_log()
        case_title = ""
        if case_id:
            case = db.query(TestCase).filter(TestCase.id == case_id).first()
            if case:
                case_title = case.title

        default_name = f"自动生成 - {case_title or instruction[:30]}"
        ai_script_name = default_name
        try:
            ai_script_name = ScriptGenerator.generate_script_name(
                description=case_title or instruction,
                target_url=target_url or "",
                db_session=db,
            )
            if not ai_script_name or len(ai_script_name) < 2:
                ai_script_name = default_name
        except Exception:
            ai_script_name = default_name
        ai_script_name = ai_script_name[:50]

        script_content = ScriptGenerator.generate_from_log(
            execution_log=execution_log,
            target_url=target_url,
            script_name=ai_script_name,
            case_title=case_title,
        )

        script = AutomationScript(
            project_id=project_id,
            name=ai_script_name,
            description=f"由执行记录 #{run_id} 自动生成\n指令: {instruction[:100]}",
            case_id=case_id,
            source_run_id=run_id,
            script_content=script_content,
            script_type="ai_generated",
            target_url=target_url,
            language="python",
            status="active",
            tags="auto-generated",
            created_by=user_id,
        )
        db.add(script)
        db.commit()
        db.refresh(script)
        script_id = script.id
    except Exception:
        db.rollback()
    return script_id


def _finalize_run(db, run_id, agent_task_id, status, result, error,
                   duration, agent, script_id):
    """更新执行记录最终状态"""
    try:
        from app.models.test_run import TestRun
        from app.models.agent_task import AgentTask

        run = db.query(TestRun).filter(TestRun.id == run_id).first()
        if run:
            run.status = status
            run.actual_result = result
            run.error_message = error
            run.execution_log = json.dumps(agent.get_execution_log(), ensure_ascii=False)
            # 截图路径转为 Web 可访问路径
            if agent.screenshot_path and "uploads/" in agent.screenshot_path:
                run.screenshot_url = agent.screenshot_path[agent.screenshot_path.index("uploads/"):]
            else:
                run.screenshot_url = agent.screenshot_path or ""
            run.duration = duration
            run.completed_at = china_now_naive()

        task = db.query(AgentTask).filter(AgentTask.id == agent_task_id).first()
        if task:
            finalize_agent_task(
                db, task,
                "success" if status == "passed" else "failed",
                error if status == "failed" else None,
            )
            task.output_result = {
                "status": status,
                "result": result,
                "error_message": error,
                "steps": len(agent.get_execution_log()),
                "script_id": script_id,
            }

        db.commit()
    except Exception:
        db.rollback()


def _handle_failure(db, run_id, agent_task_id, error_message, duration):
    """处理执行失败"""
    try:
        from app.models.test_run import TestRun
        from app.models.agent_task import AgentTask

        run = db.query(TestRun).filter(TestRun.id == run_id).first()
        if run:
            run.status = "failed"
            run.error_message = error_message
            run.duration = round(duration, 2)
            run.completed_at = china_now_naive()

        task = db.query(AgentTask).filter(AgentTask.id == agent_task_id).first()
        if task:
            finalize_agent_task(db, task, "failed", error_message)

        db.commit()
    except Exception:
        db.rollback()
