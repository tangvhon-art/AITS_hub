"""
测试计划管理 API
计划CRUD + 环境管理 + 节点管理 + 异步执行 + 报告导出
"""
import json
import logging
from datetime import datetime
from app.core.timezone import china_now_naive
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.deps import get_current_user
from app.core.audit import log_audit
from app.models.user import User
from app.models.test_plan import (
    TestPlan, TestPlanCase, TestEnvironment,
    TestPlanItem, TestPlanExecution, TestPlanExecutionResult,
)
from app.models.test_case import TestCase
from app.models.api_test import ApiTestCase, ApiScenario
from app.models.automation_script import AutomationScript
from app.models.automation_suite import AutomationSuite
from app.schemas.test_plan import (
    TestPlanCreate, TestPlanUpdate, TestPlanResponse, TestPlanListResponse,
    TestPlanCaseUpdate, TestPlanCaseResponse,
    TestEnvironmentCreate, TestEnvironmentUpdate, TestEnvironmentResponse,
    TestPlanItemCreate, TestPlanItemUpdate, TestPlanItemResponse,
    TestPlanItemReorderRequest,
    TestPlanExecutionResponse, TestPlanExecutionStatusResponse,
    TestPlanExecutionListResponse, TestPlanExecutionDetailResponse,
    TestPlanExecutionResultResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()
project_router = APIRouter(prefix="/api/projects/{project_id}")
execution_router = APIRouter(prefix="/api/test-plan-executions")


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
    keyword: Optional[str] = None,
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
    if keyword:
        query = query.filter(TestPlan.name.like(f"%{keyword}%"))

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
        execution_config=data.execution_config or {},
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
                item = TestPlanItem(
                    plan_id=plan.id,
                    item_type="ui_case",
                    ref_id=case_id,
                    item_name=case.title,
                    sort_order=idx,
                    enabled=True,
                )
                db.add(item)

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
        db.query(TestPlanItem).filter(
            TestPlanItem.plan_id == plan_id,
            TestPlanItem.item_type == "ui_case",
        ).update({"is_deleted": True, "deleted_at": china_now_naive()})
        for idx, case_id in enumerate(case_ids):
            case = db.query(TestCase).filter(TestCase.id == case_id, TestCase.project_id == project_id).first()
            if case:
                item = TestPlanItem(
                    plan_id=plan_id,
                    item_type="ui_case",
                    ref_id=case_id,
                    item_name=case.title,
                    sort_order=idx,
                    enabled=True,
                )
                db.add(item)
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
    db.query(TestPlanItem).filter(TestPlanItem.plan_id == plan_id).update(
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
    """获取计划关联的用例列表（统一基于 TestPlanItem）"""
    plan = db.query(TestPlan).filter(
        TestPlan.id == plan_id,
        TestPlan.project_id == project_id
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="测试计划不存在")

    items = db.query(TestPlanItem).filter(
        TestPlanItem.plan_id == plan_id,
        TestPlanItem.item_type == "ui_case",
        TestPlanItem.is_deleted == False,
    ).order_by(TestPlanItem.sort_order).all()

    result = []
    for item in items:
        case = db.query(TestCase).filter(TestCase.id == item.ref_id).first()
        result.append(TestPlanCaseResponse(
            id=item.id,
            plan_id=item.plan_id,
            case_id=item.ref_id,
            sort_order=item.sort_order,
            status="active" if item.enabled else "disabled",
            run_id=None,
            case_title=case.title if case else item.item_name,
            case_priority=case.priority if case else None
        ))
    return result


@project_router.post("/plans/{plan_id}/cases", response_model=TestPlanResponse)
def update_plan_cases(project_id: int, plan_id: int, data: TestPlanCaseUpdate, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """更新计划关联的用例（统一基于 TestPlanItem）"""
    plan = db.query(TestPlan).filter(
        TestPlan.id == plan_id,
        TestPlan.project_id == project_id
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="测试计划不存在")

    db.query(TestPlanItem).filter(
        TestPlanItem.plan_id == plan_id,
        TestPlanItem.item_type == "ui_case",
    ).update({"is_deleted": True, "deleted_at": china_now_naive()})

    for idx, case_id in enumerate(data.case_ids):
        case = db.query(TestCase).filter(TestCase.id == case_id, TestCase.project_id == project_id).first()
        if case:
            item = TestPlanItem(
                plan_id=plan_id,
                item_type="ui_case",
                ref_id=case_id,
                item_name=case.title,
                sort_order=idx,
                enabled=True,
            )
            db.add(item)

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


# ==================== 计划节点管理（用例+场景混合编排） ====================

@project_router.get("/plans/{plan_id}/items", response_model=list[TestPlanItemResponse])
def list_plan_items(project_id: int, plan_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取计划节点列表"""
    plan = db.query(TestPlan).filter(
        TestPlan.id == plan_id, TestPlan.project_id == project_id
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="测试计划不存在")

    items = db.query(TestPlanItem).filter(
        TestPlanItem.plan_id == plan_id
    ).order_by(TestPlanItem.sort_order).all()
    return items


@project_router.post("/plans/{plan_id}/items", response_model=TestPlanItemResponse)
def add_plan_item(project_id: int, plan_id: int, data: TestPlanItemCreate, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """添加节点到测试计划"""
    plan = db.query(TestPlan).filter(
        TestPlan.id == plan_id, TestPlan.project_id == project_id
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="测试计划不存在")

    # 验证引用对象存在
    item_name = data.item_name
    if data.item_type == "case":
        case = db.query(ApiTestCase).filter(ApiTestCase.id == data.ref_id).first()
        if not case:
            raise HTTPException(status_code=404, detail="接口用例不存在")
        if not item_name:
            item_name = case.name
    elif data.item_type == "scenario":
        scenario = db.query(ApiScenario).filter(ApiScenario.id == data.ref_id).first()
        if not scenario:
            raise HTTPException(status_code=404, detail="场景编排不存在")
        if not item_name:
            item_name = scenario.name
    elif data.item_type == "script":
        script = db.query(AutomationScript).filter(AutomationScript.id == data.ref_id).first()
        if not script:
            raise HTTPException(status_code=404, detail="UI脚本不存在")
        if not item_name:
            item_name = script.name
    elif data.item_type == "suite":
        suite = db.query(AutomationSuite).filter(AutomationSuite.id == data.ref_id).first()
        if not suite:
            raise HTTPException(status_code=404, detail="编排套件不存在")
        if not item_name:
            item_name = suite.name
    else:
        raise HTTPException(status_code=400, detail="不支持的节点类型")

    # 计算排序
    max_order = db.query(TestPlanItem).filter(TestPlanItem.plan_id == plan_id).count()

    item = TestPlanItem(
        plan_id=plan_id,
        item_type=data.item_type,
        ref_id=data.ref_id,
        item_name=item_name,
        sort_order=data.sort_order if data.sort_order is not None else max_order,
        enabled=data.enabled,
        fail_strategy=data.fail_strategy,
        timeout=data.timeout,
        max_retries=data.max_retries,
        config=data.config or {},
    )
    db.add(item)
    db.flush()

    log_audit(
        db, action="create", resource_type="plan_item",
        resource_id=item.id, resource_name=item_name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"plan_id": plan_id, "item_type": data.item_type, "ref_id": data.ref_id},
    )
    db.commit()
    db.refresh(item)
    return item


@project_router.put("/plans/{plan_id}/items/{item_id}", response_model=TestPlanItemResponse)
def update_plan_item(project_id: int, plan_id: int, item_id: int, data: TestPlanItemUpdate, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """更新计划节点"""
    item = db.query(TestPlanItem).filter(
        TestPlanItem.id == item_id, TestPlanItem.plan_id == plan_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="节点不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(item, key, value)
    item.updated_at = china_now_naive()

    log_audit(
        db, action="update", resource_type="plan_item",
        resource_id=item.id, resource_name=item.item_name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"plan_id": plan_id, "updates": update_data},
    )
    db.commit()
    db.refresh(item)
    return item


@project_router.delete("/plans/{plan_id}/items/{item_id}")
def delete_plan_item(project_id: int, plan_id: int, item_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """删除计划节点"""
    item = db.query(TestPlanItem).filter(
        TestPlanItem.id == item_id, TestPlanItem.plan_id == plan_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="节点不存在")

    item_name = item.item_name
    item.soft_delete()

    # 重新排序
    remaining = db.query(TestPlanItem).filter(
        TestPlanItem.plan_id == plan_id,
        TestPlanItem.is_deleted == False
    ).order_by(TestPlanItem.sort_order).all()
    for idx, it in enumerate(remaining):
        it.sort_order = idx

    log_audit(
        db, action="delete", resource_type="plan_item",
        resource_id=item_id, resource_name=item_name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"plan_id": plan_id},
    )
    db.commit()
    return {"detail": "删除成功"}


@project_router.post("/plans/{plan_id}/items/reorder")
def reorder_plan_items(project_id: int, plan_id: int, data: TestPlanItemReorderRequest, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """节点排序"""
    plan = db.query(TestPlan).filter(
        TestPlan.id == plan_id, TestPlan.project_id == project_id
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="测试计划不存在")

    for idx, item_id in enumerate(data.item_ids):
        item = db.query(TestPlanItem).filter(
            TestPlanItem.id == item_id, TestPlanItem.plan_id == plan_id
        ).first()
        if item:
            item.sort_order = idx

    log_audit(
        db, action="update", resource_type="plan_item",
        resource_id=plan_id, resource_name=plan.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"action": "reorder", "item_ids": data.item_ids},
    )
    db.commit()
    return {"detail": "排序成功"}


# ==================== 可用节点库（接口用例+场景编排） ====================

@project_router.get("/plans/{plan_id}/available-items")
def get_available_items(
    project_id: int, plan_id: int,
    item_type: Optional[str] = Query(None, description="case/scenario"),
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取可添加到计划的节点库（接口用例+场景编排+UI脚本+编排套件）"""
    plan = db.query(TestPlan).filter(
        TestPlan.id == plan_id, TestPlan.project_id == project_id
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="测试计划不存在")

    # 获取已添加的节点ID
    existing_items = db.query(TestPlanItem).filter(
        TestPlanItem.plan_id == plan_id,
        TestPlanItem.is_deleted == False
    ).all()
    existing_case_ids = {it.ref_id for it in existing_items if it.item_type == "case"}
    existing_scenario_ids = {it.ref_id for it in existing_items if it.item_type == "scenario"}
    existing_script_ids = {it.ref_id for it in existing_items if it.item_type == "script"}
    existing_suite_ids = {it.ref_id for it in existing_items if it.item_type == "suite"}

    result = {"cases": [], "scenarios": [], "scripts": [], "suites": [], "total": 0}

    if not item_type or item_type == "case":
        query = db.query(ApiTestCase).filter(
            ApiTestCase.project_id == project_id,
            ApiTestCase.is_deleted == False
        )
        if keyword:
            query = query.filter(ApiTestCase.name.like(f"%{keyword}%"))
        cases = query.order_by(ApiTestCase.id.desc()).all()
        result["cases"] = [
            {"id": c.id, "name": c.name, "method": c.method, "path": c.path,
             "priority": c.priority, "added": c.id in existing_case_ids}
            for c in cases
        ]

    if not item_type or item_type == "scenario":
        query = db.query(ApiScenario).filter(
            ApiScenario.project_id == project_id,
            ApiScenario.is_deleted == False
        )
        if keyword:
            query = query.filter(ApiScenario.name.like(f"%{keyword}%"))
        scenarios = query.order_by(ApiScenario.id.desc()).all()
        result["scenarios"] = [
            {"id": s.id, "name": s.name, "description": s.description,
             "added": s.id in existing_scenario_ids}
            for s in scenarios
        ]

    if not item_type or item_type == "script":
        query = db.query(AutomationScript).filter(
            AutomationScript.project_id == project_id,
            AutomationScript.is_deleted == False,
        )
        if keyword:
            query = query.filter(AutomationScript.name.like(f"%{keyword}%"))
        scripts = query.order_by(AutomationScript.id.desc()).all()
        result["scripts"] = [
            {"id": s.id, "name": s.name, "target_url": s.target_url,
             "language": s.language, "version": s.version, "status": s.status,
             "added": s.id in existing_script_ids}
            for s in scripts
        ]
        logger.info(f"加载UI脚本: project_id={project_id}, count={len(scripts)}")

    if not item_type or item_type == "suite":
        query = db.query(AutomationSuite).filter(
            AutomationSuite.project_id == project_id,
            AutomationSuite.is_deleted == False,
        )
        if keyword:
            query = query.filter(AutomationSuite.name.like(f"%{keyword}%"))
        suites = query.order_by(AutomationSuite.id.desc()).all()
        result["suites"] = [
            {"id": s.id, "name": s.name, "description": s.description,
             "total_steps": s.total_steps, "status": s.status,
             "added": s.id in existing_suite_ids}
            for s in suites
        ]
        logger.info(f"加载编排套件: project_id={project_id}, count={len(suites)}")

    result["total"] = (len(result["cases"]) + len(result["scenarios"])
                       + len(result["scripts"]) + len(result["suites"]))
    return result


# ==================== 执行管理 ====================

@project_router.post("/plans/{plan_id}/run")
def run_plan(project_id: int, plan_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """触发测试计划执行（异步）"""
    plan = db.query(TestPlan).filter(
        TestPlan.id == plan_id, TestPlan.project_id == project_id
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="测试计划不存在")

    # 获取启用的节点
    items = db.query(TestPlanItem).filter(
        TestPlanItem.plan_id == plan_id,
        TestPlanItem.enabled == True,
        TestPlanItem.is_deleted == False
    ).order_by(TestPlanItem.sort_order).all()

    if not items:
        raise HTTPException(status_code=400, detail="测试计划中没有启用的节点")

    # 获取环境信息
    env_name = ""
    if plan.environment_id:
        env = db.query(TestEnvironment).filter(TestEnvironment.id == plan.environment_id).first()
        if env:
            env_name = env.name

    # 创建执行记录
    execution = TestPlanExecution(
        plan_id=plan_id,
        plan_name=plan.name,
        environment_id=plan.environment_id,
        environment_name=env_name,
        status="pending",
        triggered_by=current_user.id,
        total_items=len(items),
    )
    db.add(execution)
    db.flush()

    # 更新计划的最近执行ID
    plan.last_execution_id = execution.id
    plan.status = "running"
    plan.updated_at = china_now_naive()

    log_audit(
        db, action="execute", resource_type="plan",
        resource_id=plan.id, resource_name=plan.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"execution_id": execution.id, "total_items": len(items)},
    )
    db.commit()
    db.refresh(execution)

    # 提交异步任务
    try:
        from app.tasks.test_plan_tasks import execute_test_plan_task
        execute_test_plan_task.delay(execution.id)
    except Exception as e:
        logger.warning(f"Celery任务提交失败，降级为后台线程执行: {e}")
        # 降级：在后台线程执行核心逻辑（避免直接调用 bind=True 的 Celery 任务）
        import threading
        from app.tasks.test_plan_tasks import _run_test_plan_execution
        thread = threading.Thread(target=_run_test_plan_execution, args=(execution.id,), daemon=True)
        thread.start()

    return {"execution_id": execution.id, "status": "pending", "detail": "测试计划已启动"}


@project_router.get("/plans/{plan_id}/executions", response_model=TestPlanExecutionListResponse)
def list_plan_executions(
    project_id: int, plan_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取计划执行历史列表"""
    plan = db.query(TestPlan).filter(
        TestPlan.id == plan_id, TestPlan.project_id == project_id
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="测试计划不存在")

    query = db.query(TestPlanExecution).filter(
        TestPlanExecution.plan_id == plan_id,
        TestPlanExecution.is_deleted == False
    )
    total = query.count()
    executions = query.order_by(TestPlanExecution.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return TestPlanExecutionListResponse(
        total=total, page=page, page_size=page_size, items=executions
    )


@execution_router.get("/{execution_id}", response_model=TestPlanExecutionDetailResponse)
def get_execution_detail(execution_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取执行详情（含报告和结果明细）"""
    execution = db.query(TestPlanExecution).filter(
        TestPlanExecution.id == execution_id,
        TestPlanExecution.is_deleted == False
    ).first()
    if not execution:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    results = db.query(TestPlanExecutionResult).filter(
        TestPlanExecutionResult.execution_id == execution_id,
        TestPlanExecutionResult.is_deleted == False
    ).order_by(TestPlanExecutionResult.sort_order).all()

    return TestPlanExecutionDetailResponse(
        execution=execution,
        results=results,
    )


@execution_router.get("/{execution_id}/status", response_model=TestPlanExecutionStatusResponse)
def get_execution_status(execution_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """获取执行状态（轮询用）"""
    execution = db.query(TestPlanExecution).filter(
        TestPlanExecution.id == execution_id,
        TestPlanExecution.is_deleted == False
    ).first()
    if not execution:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    return TestPlanExecutionStatusResponse(
        id=execution.id,
        status=execution.status,
        total_items=execution.total_items,
        passed_count=execution.passed_count,
        failed_count=execution.failed_count,
        skipped_count=execution.skipped_count,
        pass_rate=execution.pass_rate,
        started_at=execution.started_at,
        finished_at=execution.finished_at,
    )


@execution_router.post("/{execution_id}/cancel")
def cancel_execution(execution_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """取消执行"""
    execution = db.query(TestPlanExecution).filter(
        TestPlanExecution.id == execution_id,
        TestPlanExecution.is_deleted == False
    ).first()
    if not execution:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    if execution.status not in ("pending", "running"):
        raise HTTPException(status_code=400, detail="只能取消待执行或执行中的任务")

    execution.status = "cancelled"
    execution.finished_at = china_now_naive()
    execution.error_message = "用户取消执行"

    # 更新计划状态
    plan = db.query(TestPlan).filter(TestPlan.id == execution.plan_id).first()
    if plan:
        plan.status = "draft"

    log_audit(
        db, action="cancel", resource_type="plan_execution",
        resource_id=execution.id, resource_name=execution.plan_name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"execution_id": execution_id},
    )
    db.commit()
    return {"detail": "已取消执行", "status": "cancelled"}


# ==================== 报告导出 ====================

@execution_router.get("/{execution_id}/report/html")
def export_html_report(execution_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """导出 HTML 报告"""
    execution = db.query(TestPlanExecution).filter(
        TestPlanExecution.id == execution_id,
        TestPlanExecution.is_deleted == False
    ).first()
    if not execution:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    results = db.query(TestPlanExecutionResult).filter(
        TestPlanExecutionResult.execution_id == execution_id,
        TestPlanExecutionResult.is_deleted == False
    ).order_by(TestPlanExecutionResult.sort_order).all()

    # 生成HTML
    status_colors = {"passed": "#52c41a", "failed": "#ff4d4f", "skipped": "#faad14", "error": "#ff4d4f"}
    status_texts = {"passed": "通过", "failed": "失败", "skipped": "跳过", "error": "错误"}
    type_labels = {"case": "接口用例", "scenario": "场景编排", "script": "UI脚本", "suite": "编排套件"}

    results_html = ""
    for r in results:
        color = status_colors.get(r.status, "#999")
        text = status_texts.get(r.status, r.status)
        type_label = type_labels.get(r.item_type, r.item_type)
        req = r.request_data or {}
        resp = r.response_data or {}
        category = req.get("category") or resp.get("category", "")

        # 根据节点类别渲染请求/响应信息
        if category in ("ui_script", "ui_suite"):
            if category == "ui_script":
                req_info = f"脚本: {req.get('script','')} | 目标: {req.get('target_url','')}"
            else:
                req_info = f"套件: {req.get('suite','')} | 步骤数: {req.get('total_steps',0)}"
            resp_info = (f"状态: {resp.get('status','')} | 通过: {resp.get('passed_steps',0)}"
                         f"/失败: {resp.get('failed_steps',0)} | 耗时: {resp.get('total_duration',0)}s")
        else:
            req_info = f"{req.get('method','')} {req.get('url','')}"
            resp_info = f"{resp.get('status_code','')} ({resp.get('duration','')}ms)"

        assertions_html = ""
        if r.assertions:
            for a in r.assertions:
                a_color = "#52c41a" if a.get("passed") else "#ff4d4f"
                assertions_html += f'<div style="color:{a_color}">{"✓" if a.get("passed") else "✗"} {a.get("assert_type","")}: {a.get("assert_target","")} {a.get("operator","")} {a.get("expected_value","")}</div>'

        results_html += f"""
        <div style="border:1px solid #e8e8e8;border-radius:8px;padding:16px;margin-bottom:12px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                <strong>{r.sort_order + 1}. {r.item_name}</strong>
                <span style="color:{color};font-weight:bold;">{text}</span>
            </div>
            <div style="font-size:12px;color:#666;margin-bottom:8px;">
                类型: {type_label} | 耗时: {r.duration_ms}ms | 重试: {r.retry_count}次
            </div>
            <div style="background:#fafafa;padding:8px;border-radius:4px;margin-bottom:8px;">
                <div><strong>请求:</strong> {req_info}</div>
                <div><strong>响应:</strong> {resp_info}</div>
            </div>
            {assertions_html}
            {f'<div style="color:#ff4d4f;margin-top:8px;">错误: {r.error_message}</div>' if r.error_message else ''}
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>测试报告 - {execution.plan_name}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 1000px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #f5f5f5; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .stats {{ display: flex; gap: 20px; margin: 16px 0; }}
        .stat-card {{ flex: 1; text-align: center; padding: 16px; border-radius: 8px; background: #fff; border: 1px solid #e8e8e8; }}
        .stat-value {{ font-size: 24px; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{execution.plan_name}</h1>
        <p>执行ID: {execution.id} | 环境: {execution.environment_name} | 状态: {execution.status}</p>
        <p>开始: {execution.started_at} | 结束: {execution.finished_at}</p>
    </div>
    <div class="stats">
        <div class="stat-card"><div class="stat-value">{execution.total_items}</div><div>总节点</div></div>
        <div class="stat-card"><div class="stat-value" style="color:#52c41a">{execution.passed_count}</div><div>通过</div></div>
        <div class="stat-card"><div class="stat-value" style="color:#ff4d4f">{execution.failed_count}</div><div>失败</div></div>
        <div class="stat-card"><div class="stat-value" style="color:#faad14">{execution.skipped_count}</div><div>跳过</div></div>
        <div class="stat-card"><div class="stat-value" style="color:#1890ff">{execution.pass_rate}%</div><div>通过率</div></div>
    </div>
    <h2>执行详情</h2>
    {results_html}
</body>
</html>"""

    return Response(content=html, media_type="text/html", headers={
        "Content-Disposition": f"attachment; filename=test_report_{execution_id}.html"
    })


@execution_router.get("/{execution_id}/report/junit")
def export_junit_report(execution_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """导出 JUnit XML 报告"""
    execution = db.query(TestPlanExecution).filter(
        TestPlanExecution.id == execution_id,
        TestPlanExecution.is_deleted == False
    ).first()
    if not execution:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    results = db.query(TestPlanExecutionResult).filter(
        TestPlanExecutionResult.execution_id == execution_id,
        TestPlanExecutionResult.is_deleted == False
    ).order_by(TestPlanExecutionResult.sort_order).all()

    import xml.etree.ElementTree as ET
    from xml.dom import minidom

    testsuite = ET.Element("testsuite", {
        "name": execution.plan_name,
        "tests": str(execution.total_items),
        "failures": str(execution.failed_count),
        "errors": str(sum(1 for r in results if r.status == "error")),
        "skipped": str(execution.skipped_count),
        "time": str(round(sum(r.duration_ms for r in results) / 1000, 3)),
        "timestamp": execution.started_at.isoformat() if execution.started_at else "",
    })

    for r in results:
        testcase = ET.SubElement(testsuite, "testcase", {
            "name": r.item_name,
            "classname": f"test_plan.{r.item_type}",
            "time": str(round(r.duration_ms / 1000, 3)),
        })
        if r.status == "failed" or r.status == "error":
            failure = ET.SubElement(testcase, "failure", {
                "message": r.error_message or "断言失败",
                "type": "AssertionError" if r.status == "failed" else "Error",
            })
            failure.text = r.error_message or json.dumps(r.assertions, ensure_ascii=False)
        elif r.status == "skipped":
            ET.SubElement(testcase, "skipped", {"message": "节点被跳过"})

    xml_str = minidom.parseString(ET.tostring(testsuite, encoding="unicode")).toprettyxml(indent="  ")

    return Response(content=xml_str, media_type="application/xml", headers={
        "Content-Disposition": f"attachment; filename=test_report_{execution_id}.xml"
    })
