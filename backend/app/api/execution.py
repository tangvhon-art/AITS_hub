import json
import time
from datetime import datetime
from app.core.timezone import china_now_naive
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.project import Project
from app.models.test_run import TestRun
from app.models.test_case import TestCase
from app.models.agent_task import AgentTask
from app.schemas.test_run import ExecutionRequest, TestRunResponse
from app.agents.execution_agent import ExecutionAgent

router = APIRouter(prefix="/api/projects/{project_id}/execution", tags=["UI 自动化执行"])


def _check_project_access(project_id: int, db: Session, user: User) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.owner_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="无权访问该项目")
    return project


@router.post("/run")
async def run_execution(
    project_id: int,
    exec_request: ExecutionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    启动 UI 自动化执行，SSE 流式输出执行过程
    """
    _check_project_access(project_id, db, current_user)

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
    db.commit()
    db.refresh(test_run)
    db.refresh(agent_task)

    async def event_generator():
        agent = ExecutionAgent(
            db_session=db,
            llm_config_id=exec_request.llm_config_id,
        )

        final_status = "failed"
        final_result = ""
        error_message = ""

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
                elif event.get("type") == "error":
                    error_message = event.get("message", "")
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            # 更新执行记录
            test_run.status = final_status
            test_run.actual_result = final_result
            test_run.error_message = error_message
            test_run.execution_log = json.dumps(agent.get_execution_log(), ensure_ascii=False)
            test_run.screenshot_url = agent.screenshot_path
            test_run.completed_at = china_now_naive()

            # 更新 Agent 任务记录
            agent_task.status = "success" if final_status == "passed" else "failed"
            agent_task.output_result = {
                "status": final_status,
                "result": final_result,
                "error_message": error_message,
                "steps": len(agent.get_execution_log()),
            }
            agent_task.error_message = error_message if final_status == "failed" else None
            agent_task.completed_at = china_now_naive()
            db.commit()

        except Exception as e:
            error_message = f"执行异常终止: {str(e)}"
            test_run.status = "failed"
            test_run.error_message = error_message
            test_run.completed_at = china_now_naive()
            agent_task.status = "failed"
            agent_task.error_message = error_message
            agent_task.completed_at = china_now_naive()
            db.commit()
            yield f"data: {json.dumps({'type': 'error', 'message': error_message}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'finish', 'status': 'failed', 'result': error_message}, ensure_ascii=False)}\n\n"

        yield f"data: {json.dumps({'type': 'done', 'run_id': test_run.id, 'status': final_status}, ensure_ascii=False)}\n\n"

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
    _check_project_access(project_id, db, current_user)
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
    _check_project_access(project_id, db, current_user)
    run = db.query(TestRun).filter(
        TestRun.id == run_id,
        TestRun.project_id == project_id,
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    return run
