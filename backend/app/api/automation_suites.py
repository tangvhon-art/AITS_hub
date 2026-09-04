"""
自动化编排管理 API
"""
import json
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, status, BackgroundTasks, Body
from sqlalchemy.orm import Session
from app.database import get_db, SessionLocal
from app.core.deps import get_current_user, get_project
from app.core.audit import log_audit
from app.core.timezone import china_now_naive
from app.models.user import User
from app.models.project import Project
from app.models.automation_suite import (
    AutomationSuite,
    AutomationSuiteStep,
    AutomationSuiteRun,
    AutomationSuiteRunResult,
)
from app.models.automation_script import AutomationScript
from app.models.test_case import TestCase
from app.schemas.automation_suite import (
    AutomationSuiteCreate,
    AutomationSuiteUpdate,
    AutomationSuiteResponse,
    SuiteStepBase,
    SuiteStepResponse,
    SuiteStepsBatchUpdate,
    SuiteRunResponse,
    SuiteRunResultResponse,
    SuiteExecuteRequest,
)
from app.agents.suite_executor import SuiteExecutor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects/{project_id}/suites", tags=["自动化编排"])

@router.post("/search", response_model=List[AutomationSuiteResponse])
def list_suites(
    project_id: int,
    status: Optional[str] = Body(None),
    plan_id: Optional[int] = Body(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取编排套件列表"""
    get_project(project_id, db, current_user)
    query = db.query(AutomationSuite).filter(AutomationSuite.project_id == project_id)
    if status:
        query = query.filter(AutomationSuite.status == status)
    if plan_id:
        query = query.filter(AutomationSuite.plan_id == plan_id)
    return query.order_by(AutomationSuite.updated_at.desc()).all()

@router.get("/{suite_id}", response_model=AutomationSuiteResponse)
def get_suite(
    project_id: int,
    suite_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取套件详情"""
    get_project(project_id, db, current_user)
    suite = db.query(AutomationSuite).filter(
        AutomationSuite.id == suite_id,
        AutomationSuite.project_id == project_id,
    ).first()
    if not suite:
        raise HTTPException(status_code=404, detail="套件不存在")
    return suite

@router.post("", response_model=AutomationSuiteResponse, status_code=status.HTTP_201_CREATED)
def create_suite(
    project_id: int,
    data: AutomationSuiteCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建套件"""
    get_project(project_id, db, current_user)
    suite = AutomationSuite(
        project_id=project_id,
        name=data.name,
        description=data.description or "",
        plan_id=data.plan_id,
        environment_id=data.environment_id,
        status=data.status or "active",
        schedule_type=data.schedule_type or "manual",
        schedule_cron=data.schedule_cron or "",
        config=data.config or {},
        created_by=current_user.id,
    )
    db.add(suite)
    db.flush()
    log_audit(
        db, action="create", resource_type="suite",
        resource_id=suite.id, resource_name=suite.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "name": suite.name, "plan_id": suite.plan_id},
    )
    db.commit()
    db.refresh(suite)
    return suite

@router.put("/{suite_id}", response_model=AutomationSuiteResponse)
def update_suite(
    project_id: int,
    suite_id: int,
    data: AutomationSuiteUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新套件"""
    get_project(project_id, db, current_user)
    suite = db.query(AutomationSuite).filter(
        AutomationSuite.id == suite_id,
        AutomationSuite.project_id == project_id,
    ).first()
    if not suite:
        raise HTTPException(status_code=404, detail="套件不存在")

    old_data = {"name": suite.name, "status": suite.status}
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(suite, key, value)
    suite.updated_at = china_now_naive()
    log_audit(
        db, action="update", resource_type="suite",
        resource_id=suite.id, resource_name=suite.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"before": old_data, "after": update_data},
    )
    db.commit()
    db.refresh(suite)
    return suite

@router.delete("/{suite_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_suite(
    project_id: int,
    suite_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除套件"""
    get_project(project_id, db, current_user)
    suite = db.query(AutomationSuite).filter(
        AutomationSuite.id == suite_id,
        AutomationSuite.project_id == project_id,
    ).first()
    if not suite:
        raise HTTPException(status_code=404, detail="套件不存在")
    suite_name = suite.name
    # 级联删除步骤
    db.query(AutomationSuiteStep).filter(AutomationSuiteStep.suite_id == suite_id).update(
        {"is_deleted": True, "deleted_at": china_now_naive()}
    )
    suite.soft_delete()
    log_audit(
        db, action="delete", resource_type="suite",
        resource_id=suite_id, resource_name=suite_name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()

# ============ 步骤管理 ============
@router.get("/{suite_id}/steps", response_model=List[SuiteStepResponse])
def get_suite_steps(
    project_id: int,
    suite_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取套件步骤列表"""
    get_project(project_id, db, current_user)
    suite = db.query(AutomationSuite).filter(
        AutomationSuite.id == suite_id,
        AutomationSuite.project_id == project_id,
    ).first()
    if not suite:
        raise HTTPException(status_code=404, detail="套件不存在")
    return db.query(AutomationSuiteStep).filter(
        AutomationSuiteStep.suite_id == suite_id
    ).order_by(AutomationSuiteStep.sort_order.asc()).all()

@router.post("/{suite_id}/steps", response_model=List[SuiteStepResponse])
def batch_update_steps(
    project_id: int,
    suite_id: int,
    data: SuiteStepsBatchUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量更新步骤（全量替换）"""
    get_project(project_id, db, current_user)
    suite = db.query(AutomationSuite).filter(
        AutomationSuite.id == suite_id,
        AutomationSuite.project_id == project_id,
    ).first()
    if not suite:
        raise HTTPException(status_code=404, detail="套件不存在")

    # 删除旧步骤
    db.query(AutomationSuiteStep).filter(AutomationSuiteStep.suite_id == suite_id).update(
        {"is_deleted": True, "deleted_at": china_now_naive()}
    )

    # 创建新步骤
    new_steps = []
    for idx, step_data in enumerate(data.steps):
        step = AutomationSuiteStep(
            suite_id=suite_id,
            step_name=step_data.step_name,
            script_id=step_data.script_id,
            case_id=step_data.case_id,
            sort_order=step_data.sort_order if step_data.sort_order is not None else idx,
            step_type=step_data.step_type or "script",
            params=step_data.params or {},
            continue_on_failure=step_data.continue_on_failure or False,
            max_retries=step_data.max_retries or 0,
            timeout=step_data.timeout or 300,
            auto_fix=step_data.auto_fix or False,
        )
        db.add(step)
        new_steps.append(step)

    suite.total_steps = len(data.steps)
    suite.updated_at = china_now_naive()
    log_audit(
        db, action="update", resource_type="suite",
        resource_id=suite.id, resource_name=suite.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"field": "steps", "step_count": len(data.steps)},
    )
    db.commit()
    for step in new_steps:
        db.refresh(step)
    return new_steps

# ============ 执行编排 ============
@router.post("/{suite_id}/execute")
async def execute_suite(
    project_id: int,
    suite_id: int,
    req: SuiteExecuteRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """执行编排套件（异步）"""
    get_project(project_id, db, current_user)
    suite = db.query(AutomationSuite).filter(
        AutomationSuite.id == suite_id,
        AutomationSuite.project_id == project_id,
    ).first()
    if not suite:
        raise HTTPException(status_code=404, detail="套件不存在")

    steps = db.query(AutomationSuiteStep).filter(
        AutomationSuiteStep.suite_id == suite_id
    ).count()
    if steps == 0:
        raise HTTPException(status_code=400, detail="套件中没有步骤，无法执行")

    # 创建执行记录
    suite_run = AutomationSuiteRun(
        suite_id=suite_id,
        project_id=project_id,
        plan_id=suite.plan_id,
        status="pending",
        total_steps=steps,
        trigger_type=req.trigger_type or "manual",
        executed_by=current_user.id,
    )
    db.add(suite_run)
    db.flush()
    log_audit(
        db, action="execute", resource_type="suite",
        resource_id=suite.id, resource_name=suite.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "run_id": suite_run.id, "total_steps": steps},
    )
    db.commit()
    db.refresh(suite_run)

    # 后台异步执行（优先 Celery，降级 BackgroundTasks）
    use_celery = False
    celery_task_id = None
    try:
        from app.tasks.script_tasks import run_automation_suite_task
        task_result = run_automation_suite_task.delay(suite_run.id, headless=req.headless)
        celery_task_id = task_result.id
        use_celery = True
        logger.info(f"编排 #{suite.id} 已提交 Celery 任务: task_id={celery_task_id}, headless={req.headless}")
    except Exception as celery_e:
        logger.warning(f"Celery 任务提交失败，降级到 BackgroundTasks: {celery_e}")

        def _run_in_background(run_id: int):
            from app.core.async_runner import run_async
            executor = SuiteExecutor(run_id, headless=req.headless)
            run_async(executor.execute)

        background_tasks.add_task(_run_in_background, suite_run.id)

    return {
        "run_id": suite_run.id,
        "status": "pending",
        "message": "编排执行任务已提交",
        "total_steps": steps,
        "executor": "celery" if use_celery else "background",
        "celery_task_id": celery_task_id,
    }

# ============ 执行记录 ============
@router.get("/{suite_id}/runs", response_model=List[SuiteRunResponse])
def get_suite_runs(
    project_id: int,
    suite_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取套件执行历史"""
    get_project(project_id, db, current_user)
    return db.query(AutomationSuiteRun).filter(
        AutomationSuiteRun.suite_id == suite_id
    ).order_by(AutomationSuiteRun.created_at.desc()).limit(20).all()

@router.get("/runs/{run_id}", response_model=SuiteRunResponse)
def get_suite_run(
    project_id: int,
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取执行记录详情"""
    get_project(project_id, db, current_user)
    run = db.query(AutomationSuiteRun).filter(
        AutomationSuiteRun.id == run_id,
        AutomationSuiteRun.project_id == project_id,
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    return run

@router.get("/runs/{run_id}/results", response_model=List[SuiteRunResultResponse])
def get_suite_run_results(
    project_id: int,
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取单步执行结果列表"""
    get_project(project_id, db, current_user)
    run = db.query(AutomationSuiteRun).filter(
        AutomationSuiteRun.id == run_id,
        AutomationSuiteRun.project_id == project_id,
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    return db.query(AutomationSuiteRunResult).filter(
        AutomationSuiteRunResult.suite_run_id == run_id
    ).order_by(AutomationSuiteRunResult.sort_order.asc()).all()

# ============ 全局执行记录路由 ============
run_router = APIRouter(prefix="/api/projects/{project_id}/suite-runs", tags=["编排执行记录"])

@run_router.post("/search", response_model=List[SuiteRunResponse])
def list_all_suite_runs(
    project_id: int,
    status: Optional[str] = Body(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取项目下所有编排执行记录"""
    get_project(project_id, db, current_user)
    query = db.query(AutomationSuiteRun).filter(AutomationSuiteRun.project_id == project_id)
    if status:
        query = query.filter(AutomationSuiteRun.status == status)
    return query.order_by(AutomationSuiteRun.created_at.desc()).limit(50).all()
