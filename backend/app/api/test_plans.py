"""
测试计划管理 API
"""
from datetime import datetime
from app.core.timezone import china_now_naive
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.deps import get_current_user
from app.core.audit import log_audit
from app.models.user import User
from app.models.test_plan import TestPlan, TestPlanCase, TestEnvironment
from app.models.test_case import TestCase
from app.schemas.test_plan import (
    TestPlanCreate, TestPlanUpdate, TestPlanResponse, TestPlanListResponse,
    TestPlanCaseUpdate, TestPlanCaseResponse,
    TestEnvironmentCreate, TestEnvironmentUpdate, TestEnvironmentResponse
)

router = APIRouter()
project_router = APIRouter(prefix="/api/projects/{project_id}")


# ==================== 测试环境管理 ====================

@project_router.get("/environments", response_model=list[TestEnvironmentResponse])
def list_environments(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取项目下的测试环境列表"""
    environments = db.query(TestEnvironment).filter(
        TestEnvironment.project_id == project_id
    ).order_by(TestEnvironment.is_default.desc(), TestEnvironment.created_at.desc()).all()
    return environments


@project_router.post("/environments", response_model=TestEnvironmentResponse)
def create_environment(project_id: int, data: TestEnvironmentCreate, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """创建测试环境"""
    if data.is_default:
        db.query(TestEnvironment).filter(
            TestEnvironment.project_id == project_id,
            TestEnvironment.is_default == True
        ).update({"is_default": False})

    env = TestEnvironment(
        project_id=project_id,
        name=data.name,
        base_url=data.base_url,
        description=data.description,
        config=data.config or {},
        is_default=data.is_default,
        created_by=current_user.id
    )
    db.add(env)
    db.flush()
    log_audit(
        db, action="create", resource_type="environment",
        resource_id=env.id, resource_name=env.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "name": env.name, "base_url": env.base_url},
    )
    db.commit()
    db.refresh(env)
    return env


@project_router.put("/environments/{env_id}", response_model=TestEnvironmentResponse)
def update_environment(project_id: int, env_id: int, data: TestEnvironmentUpdate, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """更新测试环境"""
    env = db.query(TestEnvironment).filter(
        TestEnvironment.id == env_id,
        TestEnvironment.project_id == project_id
    ).first()
    if not env:
        raise HTTPException(status_code=404, detail="测试环境不存在")

    if data.is_default:
        db.query(TestEnvironment).filter(
            TestEnvironment.project_id == project_id,
            TestEnvironment.is_default == True,
            TestEnvironment.id != env_id
        ).update({"is_default": False})

    old_data = {"name": env.name, "base_url": env.base_url, "is_default": env.is_default}
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(env, key, value)
    env.updated_at = china_now_naive()
    log_audit(
        db, action="update", resource_type="environment",
        resource_id=env.id, resource_name=env.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"before": old_data, "after": update_data},
    )
    db.commit()
    db.refresh(env)
    return env


@project_router.delete("/environments/{env_id}")
def delete_environment(project_id: int, env_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """删除测试环境"""
    env = db.query(TestEnvironment).filter(
        TestEnvironment.id == env_id,
        TestEnvironment.project_id == project_id
    ).first()
    if not env:
        raise HTTPException(status_code=404, detail="测试环境不存在")
    env_name = env.name
    env.soft_delete()
    log_audit(
        db, action="delete", resource_type="environment",
        resource_id=env_id, resource_name=env_name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return {"detail": "删除成功"}


# ==================== 测试计划管理 ====================

@project_router.get("/plans", response_model=TestPlanListResponse)
def list_plans(
    project_id: int,
    status: Optional[str] = None,
    version_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取测试计划列表"""
    query = db.query(TestPlan).filter(TestPlan.project_id == project_id)
    if status:
        query = query.filter(TestPlan.status == status)
    if version_id is not None:
        query = query.filter(TestPlan.version_id == version_id)

    total = query.count()
    plans = query.order_by(TestPlan.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return TestPlanListResponse(total=total, page=page, page_size=page_size, items=plans)


@project_router.get("/plans/{plan_id}", response_model=TestPlanResponse)
def get_plan(project_id: int, plan_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取测试计划详情"""
    plan = db.query(TestPlan).filter(
        TestPlan.id == plan_id,
        TestPlan.project_id == project_id
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="测试计划不存在")
    return plan


@project_router.post("/plans", response_model=TestPlanResponse)
def create_plan(project_id: int, data: TestPlanCreate, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """创建测试计划"""
    plan = TestPlan(
        project_id=project_id,
        name=data.name,
        description=data.description,
        priority=data.priority,
        start_date=data.start_date,
        end_date=data.end_date,
        environment_id=data.environment_id,
        config=data.config or {},
        schedule_type=data.schedule_type,
        schedule_cron=data.schedule_cron,
        version_id=data.version_id,
        total_cases=len(data.case_ids or []),
        created_by=current_user.id
    )
    db.add(plan)
    db.flush()

    if data.case_ids:
        for idx, case_id in enumerate(data.case_ids):
            case = db.query(TestCase).filter(TestCase.id == case_id, TestCase.project_id == project_id).first()
            if case:
                plan_case = TestPlanCase(plan_id=plan.id, case_id=case_id, sort_order=idx)
                db.add(plan_case)

    log_audit(
        db, action="create", resource_type="plan",
        resource_id=plan.id, resource_name=plan.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "name": plan.name, "case_count": len(data.case_ids or [])},
    )
    db.commit()
    db.refresh(plan)
    return plan


@project_router.put("/plans/{plan_id}", response_model=TestPlanResponse)
def update_plan(project_id: int, plan_id: int, data: TestPlanUpdate, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """更新测试计划"""
    plan = db.query(TestPlan).filter(
        TestPlan.id == plan_id,
        TestPlan.project_id == project_id
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="测试计划不存在")

    old_data = {"name": plan.name, "status": plan.status, "priority": plan.priority}
    update_data = data.model_dump(exclude_unset=True)

    # 处理关联用例更新
    case_ids_changed = False
    if "case_ids" in update_data:
        case_ids = update_data.pop("case_ids") or []
        # 删除旧的关联
        db.query(TestPlanCase).filter(TestPlanCase.plan_id == plan_id).update(
        {"is_deleted": True, "deleted_at": china_now_naive()}
    )
        # 创建新的关联
        for idx, case_id in enumerate(case_ids):
            case = db.query(TestCase).filter(TestCase.id == case_id, TestCase.project_id == project_id).first()
            if case:
                plan_case = TestPlanCase(plan_id=plan_id, case_id=case_id, sort_order=idx)
                db.add(plan_case)
        # 更新用例总数
        plan.total_cases = len(case_ids)
        case_ids_changed = True

    for key, value in update_data.items():
        setattr(plan, key, value)
    plan.updated_at = china_now_naive()
    log_audit(
        db, action="update", resource_type="plan",
        resource_id=plan.id, resource_name=plan.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"before": old_data, "after": update_data, "case_ids_changed": case_ids_changed},
    )
    db.commit()
    db.refresh(plan)
    return plan


@project_router.delete("/plans/{plan_id}")
def delete_plan(project_id: int, plan_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """删除测试计划"""
    plan = db.query(TestPlan).filter(
        TestPlan.id == plan_id,
        TestPlan.project_id == project_id
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="测试计划不存在")

    db.query(TestPlanCase).filter(TestPlanCase.plan_id == plan_id).update(
        {"is_deleted": True, "deleted_at": china_now_naive()}
    )
    plan_name = plan.name
    plan.soft_delete()
    log_audit(
        db, action="delete", resource_type="plan",
        resource_id=plan_id, resource_name=plan_name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return {"detail": "删除成功"}


@project_router.get("/plans/{plan_id}/cases", response_model=list[TestPlanCaseResponse])
def get_plan_cases(project_id: int, plan_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取计划关联的用例列表"""
    plan = db.query(TestPlan).filter(
        TestPlan.id == plan_id,
        TestPlan.project_id == project_id
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="测试计划不存在")

    plan_cases = db.query(TestPlanCase).filter(
        TestPlanCase.plan_id == plan_id
    ).order_by(TestPlanCase.sort_order).all()

    result = []
    for pc in plan_cases:
        case = db.query(TestCase).filter(TestCase.id == pc.case_id).first()
        result.append(TestPlanCaseResponse(
            id=pc.id,
            plan_id=pc.plan_id,
            case_id=pc.case_id,
            sort_order=pc.sort_order,
            status=pc.status,
            run_id=pc.run_id,
            case_title=case.title if case else None,
            case_priority=case.priority if case else None
        ))
    return result


@project_router.post("/plans/{plan_id}/cases", response_model=TestPlanResponse)
def update_plan_cases(project_id: int, plan_id: int, data: TestPlanCaseUpdate, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """更新计划关联的用例"""
    plan = db.query(TestPlan).filter(
        TestPlan.id == plan_id,
        TestPlan.project_id == project_id
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="测试计划不存在")

    db.query(TestPlanCase).filter(TestPlanCase.plan_id == plan_id).update(
        {"is_deleted": True, "deleted_at": china_now_naive()}
    )

    for idx, case_id in enumerate(data.case_ids):
        case = db.query(TestCase).filter(TestCase.id == case_id, TestCase.project_id == project_id).first()
        if case:
            plan_case = TestPlanCase(plan_id=plan_id, case_id=case_id, sort_order=idx)
            db.add(plan_case)

    plan.total_cases = len(data.case_ids)
    plan.updated_at = china_now_naive()
    log_audit(
        db, action="update", resource_type="plan",
        resource_id=plan.id, resource_name=plan.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"field": "cases", "case_count": len(data.case_ids)},
    )
    db.commit()
    db.refresh(plan)
    return plan


@project_router.post("/plans/{plan_id}/execute")
def execute_plan(project_id: int, plan_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """执行测试计划（标记为运行中，实际执行可异步）"""
    plan = db.query(TestPlan).filter(
        TestPlan.id == plan_id,
        TestPlan.project_id == project_id
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="测试计划不存在")

    plan.status = "running"
    plan.updated_at = china_now_naive()
    log_audit(
        db, action="execute", resource_type="plan",
        resource_id=plan.id, resource_name=plan.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "total_cases": plan.total_cases},
    )
    db.commit()

    return {"detail": "测试计划已启动", "plan_id": plan_id, "status": "running"}
