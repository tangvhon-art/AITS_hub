import json
import time
from datetime import datetime
from app.core.timezone import china_now_naive
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db, SessionLocal
from app.core.deps import get_current_user, get_project
from app.core.audit import log_audit
from app.models.user import User
from app.models.project import Project
from app.models.test_run import TestRun
from app.models.test_case import TestCase
from app.models.agent_task import AgentTask
from app.models.automation_script import AutomationScript
from app.schemas.test_run import ExecutionRequest, TestRunResponse
from app.agents.execution_agent import ExecutionAgent
from app.agents.script_generator import ScriptGenerator

router = APIRouter(prefix="/api/projects/{project_id}/execution", tags=["UI 自动化执行"])

@router.post("/run")
async def run_execution(
    project_id: int,
    exec_request: ExecutionRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    启动 UI 自动化执行，SSE 流式输出执行过程
    """
    get_project(project_id, db, current_user)

    # 创建执行记录
    test_run = TestRun(
        project_id=project_id,
        case_id=exec_request.case_id,
        status="running",
        started_at=china_now_naive(),
        executed_by=current_user.id,
    )
    db.add(test_run)

    # 创建 Agent 任务记录
    agent_task = AgentTask(
        project_id=project_id,
        agent_type="ui_execution",
        status="running",
        input_params={
            "instruction_length": len(exec_request.instruction),
            "target_url": exec_request.target_url,
            "headless": exec_request.headless,
            "case_id": exec_request.case_id,
        },
        llm_config_id=exec_request.llm_config_id,
        created_by=current_user.id,
    )
    db.add(agent_task)
    db.flush()

    # 审计日志
    log_audit(
        db, action="execute", resource_type="run",
        resource_id=test_run.id,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={
            "project_id": project_id,
            "target_url": exec_request.target_url,
            "case_id": exec_request.case_id,
            "agent_task_id": agent_task.id,
        },
    )
    db.commit()
    db.refresh(test_run)
    db.refresh(agent_task)

    # 保存用户ID，避免异步执行后current_user对象与Session解绑
    user_id = current_user.id

    async def event_generator():
        agent = ExecutionAgent(
            db_session=db,
            llm_config_id=exec_request.llm_config_id,
        )

        start_time = time.time()
        final_status = "failed"
        final_result = ""
        error_message = ""
        execution_duration = 0.0  # 记录真实执行耗时
        script_id = None

        try:
            async for event in agent.execute(
                instruction=exec_request.instruction,
                target_url=exec_request.target_url,
                headless=exec_request.headless,
            ):
                if event.get("type") == "finish":
                    final_status = event.get("status", "failed")
                    final_result = event.get("result", "")
                    if final_status == "failed":
                        error_message = final_result
                elif event.get("type") == "complete":
                    execution_duration = event.get("duration", 0.0)
                elif event.get("type") == "error":
                    error_message = event.get("message", "")
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            # 状态归一化：将 success/ok/pass 等统一为 passed
            if final_status.lower() in ("success", "ok", "pass", "passed", "complete", "completed"):
                final_status = "passed"
            elif final_status.lower() in ("fail", "failed", "error"):
                final_status = "failed"
            else:
                # 未知状态，根据是否有错误信息判断
                final_status = "failed" if error_message else "passed"

            # ===== 先整理执行过程，使用独立会话保存脚本到脚本库 =====
            script_id = None
            script_db = SessionLocal()
            try:
                execution_log = agent.get_execution_log()
                case_title = ""
                if exec_request.case_id:
                    case = script_db.query(TestCase).filter(TestCase.id == exec_request.case_id).first()
                    if case:
                        case_title = case.title

                # 通过 AI 生成脚本名称
                default_name = f"自动生成 - {case_title or exec_request.instruction[:30]}"
                ai_script_name = default_name
                try:
                    name_description = case_title or exec_request.instruction
                    ai_script_name = await ScriptGenerator.generate_script_name(
                        description=name_description,
                        target_url=exec_request.target_url or "",
                        db_session=script_db,
                    )
                    if not ai_script_name or len(ai_script_name) < 2:
                        ai_script_name = default_name
                except Exception as name_e:
                    print(f"AI生成脚本名称失败，使用默认名称: {name_e}")
                    ai_script_name = default_name

                # 限制名称长度
                ai_script_name = ai_script_name[:50]

                script_content = ScriptGenerator.generate_from_log(
                    execution_log=execution_log,
                    target_url=exec_request.target_url,
                    script_name=ai_script_name,
                    case_title=case_title,
                )

                script = AutomationScript(
                    project_id=project_id,
                    name=ai_script_name,
                    description=f"由执行记录 #{test_run.id} 自动生成\n指令: {exec_request.instruction[:100]}",
                    case_id=exec_request.case_id,
                    source_run_id=test_run.id,
                    script_content=script_content,
                    script_type="ai_generated",
                    target_url=exec_request.target_url,
                    language="python",
                    status="active",
                    tags="auto-generated",
                    created_by=user_id,
                )
                script_db.add(script)
                script_db.commit()
                script_db.refresh(script)
                script_id = script.id
                print(f"自动生成脚本成功: script_id={script_id}")
            except Exception as script_e:
                print(f"自动生成脚本失败: {script_e}")
                import traceback
                traceback.print_exc()
                script_db.rollback()
            finally:
                script_db.close()

            # ===== 脚本保存完成后，使用独立会话更新执行记录状态 =====
            status_db = SessionLocal()
            try:
                # 重新查询执行记录和任务
                run_update = status_db.query(TestRun).filter(TestRun.id == test_run.id).first()
                task_update = status_db.query(AgentTask).filter(AgentTask.id == agent_task.id).first()

                if run_update:
                    run_update.status = final_status
                    run_update.actual_result = final_result
                    run_update.error_message = error_message
                    run_update.execution_log = json.dumps(agent.get_execution_log(), ensure_ascii=False)
                    run_update.screenshot_url = agent.screenshot_path
                    run_update.duration = execution_duration
                    run_update.completed_at = china_now_naive()

                if task_update:
                    task_update.status = "success" if final_status == "passed" else "failed"
                    task_update.output_result = {
                        "status": final_status,
                        "result": final_result,
                        "error_message": error_message,
                        "steps": len(agent.get_execution_log()),
                        "script_id": script_id,
                    }
                    task_update.error_message = error_message if final_status == "failed" else None
                    task_update.completed_at = china_now_naive()

                status_db.commit()
                print(f"状态更新提交成功: status={final_status}")
            except Exception as status_e:
                print(f"状态更新提交失败: {status_e}")
                import traceback
                traceback.print_exc()
                status_db.rollback()
            finally:
                status_db.close()

        except Exception as e:
            error_message = f"执行异常终止: {str(e)}"
            test_run.status = "failed"
            test_run.error_message = error_message
            test_run.duration = round(time.time() - start_time, 2)
            test_run.completed_at = china_now_naive()
            agent_task.status = "failed"
            agent_task.error_message = error_message
            agent_task.completed_at = china_now_naive()
            db.commit()
            yield f"data: {json.dumps({'type': 'error', 'message': error_message}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'finish', 'status': 'failed', 'result': error_message}, ensure_ascii=False)}\n\n"

        yield f"data: {json.dumps({'type': 'done', 'run_id': test_run.id, 'status': final_status, 'script_id': script_id}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@router.get("/runs", response_model=List[TestRunResponse])
def list_runs(
    project_id: int,
    case_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取执行记录列表"""
    get_project(project_id, db, current_user)
    query = db.query(TestRun).filter(TestRun.project_id == project_id)
    if case_id:
        query = query.filter(TestRun.case_id == case_id)
    return query.order_by(TestRun.created_at.desc()).limit(50).all()

@router.get("/runs/{run_id}", response_model=TestRunResponse)
def get_run(
    project_id: int,
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取执行记录详情"""
    get_project(project_id, db, current_user)
    run = db.query(TestRun).filter(
        TestRun.id == run_id,
        TestRun.project_id == project_id,
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    return run
