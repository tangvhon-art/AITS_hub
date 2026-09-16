import json
from app.core.timezone import china_now_naive
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.core.deps import get_current_user, get_project
from app.core.audit import log_audit
from app.models.user import User
from app.models.test_run import TestRun
from app.models.agent_task import AgentTask
from app.schemas.test_run import ExecutionRequest, TestRunResponse

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
    启动 UI 自动化执行（异步 Celery 任务）
    立即返回 run_id，前端通过轮询 GET /runs/{run_id}/status 获取进度
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

    # 派发 Celery 异步任务（Chromium 在 worker 进程中运行，不占用 Web 服务器）
    from app.tasks.execution_tasks import run_ui_execution_task
    run_ui_execution_task.delay(
        run_id=test_run.id,
        agent_task_id=agent_task.id,
        project_id=project_id,
        instruction=exec_request.instruction,
        target_url=exec_request.target_url,
        headless=exec_request.headless,
        llm_config_id=exec_request.llm_config_id,
        case_id=exec_request.case_id,
        user_id=current_user.id,
    )

    return {
        "run_id": test_run.id,
        "status": "running",
        "message": "执行已提交",
    }


@router.get("/runs/{run_id}/status")
def get_run_status(
    project_id: int,
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """轮询获取执行状态和增量日志"""
    get_project(project_id, db, current_user)
    run = db.query(TestRun).filter(
        TestRun.id == run_id,
        TestRun.project_id == project_id,
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    # 解析执行日志
    log_data = run.execution_log
    if isinstance(log_data, str) and log_data:
        try:
            log_data = json.loads(log_data)
        except (json.JSONDecodeError, TypeError):
            log_data = []
    elif not isinstance(log_data, list):
        log_data = []

    return {
        "run_id": run.id,
        "status": run.status,
        "execution_log": log_data,
        "actual_result": run.actual_result or "",
        "error_message": run.error_message or "",
        "duration": run.duration or 0,
        "screenshot_url": run.screenshot_url or "",
        "completed": run.status in ("passed", "failed", "error"),
    }


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
