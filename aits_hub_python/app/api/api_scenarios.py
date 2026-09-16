"""
测试场景 API
场景CRUD + 步骤CRUD + 排序 + 执行 + 变量提取
"""
import json
import logging
from fastapi import APIRouter, Body, Depends, HTTPException, Request, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.core.deps import get_current_user, get_project
from app.core.audit import log_audit
from app.core.timezone import china_now_naive
from app.models.user import User
from app.models.project import Project
from app.models.api_test import (
    ApiScenario, ApiScenarioStep, ApiScenarioVariable,
    ApiExecution, ApiExecutionResult,
)
from app.models.report import TestReport
from app.schemas.api_test import (
    ApiScenarioCreate, ApiScenarioUpdate, ApiScenarioResponse,
    ApiScenarioStepCreate, ApiScenarioStepUpdate, ApiScenarioStepResponse,
    ApiScenarioVariableResponse,
    ApiScenarioVariableCreate,
    ApiScenarioVariableUpdate,
    ApiScenarioRunRequest,
    PaginatedResponse,
)
from app.services.scenario_executor import ScenarioExecutor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects/{project_id}/api-scenarios", tags=["接口测试-场景编排"])

@router.post("/search", response_model=PaginatedResponse)
def list_scenarios(
    project_id: int,
    keyword: Optional[str] = Body(None),
    page: int = Body(1),
    page_size: int = Body(20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """场景列表"""
    get_project(project_id, db, current_user)
    query = db.query(ApiScenario).filter(ApiScenario.project_id == project_id)
    if keyword:
        query = query.filter(ApiScenario.name.like(f"%{keyword}%"))

    total = query.count()
    items = query.order_by(ApiScenario.id.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    return PaginatedResponse(
        total=total, page=page, page_size=page_size,
        items=[ApiScenarioResponse.model_validate(item) for item in items],
    )

@router.get("/{scenario_id}", response_model=ApiScenarioResponse)
def get_scenario(
    project_id: int,
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """场景详情（含步骤）"""
    get_project(project_id, db, current_user)
    scenario = db.query(ApiScenario).filter(
        ApiScenario.id == scenario_id, ApiScenario.project_id == project_id
    ).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="场景不存在")
    return scenario

@router.post("", response_model=ApiScenarioResponse, status_code=status.HTTP_201_CREATED)
def create_scenario(
    project_id: int,
    data: ApiScenarioCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建场景"""
    get_project(project_id, db, current_user)
    scenario = ApiScenario(
        project_id=project_id,
        module_id=data.module_id,
        plan_id=data.plan_id,
        name=data.name,
        description=data.description,
        environment_id=data.environment_id,
        config=data.config,
        pre_script=data.pre_script,
        post_script=data.post_script,
        created_by=current_user.id,
    )
    db.add(scenario)
    db.flush()

    log_audit(
        db, action="create", resource_type="plan",
        resource_id=scenario.id, resource_name=scenario.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "scenario_name": scenario.name},
    )
    db.commit()
    db.refresh(scenario)
    return scenario

@router.put("/{scenario_id}", response_model=ApiScenarioResponse)
def update_scenario(
    project_id: int,
    scenario_id: int,
    data: ApiScenarioUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新场景"""
    get_project(project_id, db, current_user)
    scenario = db.query(ApiScenario).filter(
        ApiScenario.id == scenario_id, ApiScenario.project_id == project_id
    ).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="场景不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(scenario, key, value)

    log_audit(
        db, action="update", resource_type="plan",
        resource_id=scenario.id, resource_name=scenario.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "scenario_name": scenario.name},
    )
    db.commit()
    db.refresh(scenario)
    return scenario

@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario(
    project_id: int,
    scenario_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除场景（软删，同时删除步骤和变量）"""
    get_project(project_id, db, current_user)
    scenario = db.query(ApiScenario).filter(
        ApiScenario.id == scenario_id, ApiScenario.project_id == project_id
    ).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="场景不存在")

    # 软删步骤
    steps = db.query(ApiScenarioStep).filter(ApiScenarioStep.scenario_id == scenario_id).all()
    step_ids = [s.id for s in steps]
    if step_ids:
        db.query(ApiScenarioVariable).filter(
            ApiScenarioVariable.step_id.in_(step_ids)
        ).update({ApiScenarioVariable.is_deleted: True}, synchronize_session=False)
    db.query(ApiScenarioStep).filter(
        ApiScenarioStep.scenario_id == scenario_id
    ).update({ApiScenarioStep.is_deleted: True}, synchronize_session=False)

    scenario.is_deleted = True
    log_audit(
        db, action="delete", resource_type="plan",
        resource_id=scenario.id, resource_name=scenario.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "scenario_name": scenario.name},
    )
    db.commit()

# ==================== 步骤 CRUD ====================

@router.get("/{scenario_id}/steps", response_model=List[ApiScenarioStepResponse])
def list_steps(
    project_id: int,
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """步骤列表"""
    get_project(project_id, db, current_user)
    scenario = db.query(ApiScenario).filter(
        ApiScenario.id == scenario_id, ApiScenario.project_id == project_id
    ).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="场景不存在")

    steps = db.query(ApiScenarioStep).filter(
        ApiScenarioStep.scenario_id == scenario_id,
        ApiScenarioStep.is_deleted == False,
    ).order_by(ApiScenarioStep.sort_order).all()
    return steps

@router.post("/{scenario_id}/steps", response_model=ApiScenarioStepResponse, status_code=status.HTTP_201_CREATED)
def create_step(
    project_id: int,
    scenario_id: int,
    data: ApiScenarioStepCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """添加步骤"""
    get_project(project_id, db, current_user)
    scenario = db.query(ApiScenario).filter(
        ApiScenario.id == scenario_id, ApiScenario.project_id == project_id
    ).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="场景不存在")

    max_order = db.query(ApiScenarioStep).filter(
        ApiScenarioStep.scenario_id == scenario_id
    ).count()

    step = ApiScenarioStep(
        scenario_id=scenario_id,
        step_type=data.step_type,
        step_name=data.step_name,
        sort_order=data.sort_order if data.sort_order is not None else max_order,
        enabled=data.enabled,
        api_id=data.api_id,
        case_id=data.case_id,
        request_config=data.request_config,
        script_content=data.script_content,
        wait_seconds=data.wait_seconds,
        condition_expr=data.condition_expr,
        loop_config=data.loop_config,
        pre_script=data.pre_script,
        post_script=data.post_script,
        continue_on_failure=data.continue_on_failure,
        max_retries=data.max_retries,
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return step

@router.put("/steps/{step_id}", response_model=ApiScenarioStepResponse)
def update_step(
    project_id: int,
    step_id: int,
    data: ApiScenarioStepUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新步骤"""
    get_project(project_id, db, current_user)
    step = db.query(ApiScenarioStep).filter(ApiScenarioStep.id == step_id).first()
    if not step:
        raise HTTPException(status_code=404, detail="步骤不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(step, key, value)

    db.commit()
    db.refresh(step)
    return step

@router.delete("/steps/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_step(
    project_id: int,
    step_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除步骤"""
    get_project(project_id, db, current_user)
    step = db.query(ApiScenarioStep).filter(ApiScenarioStep.id == step_id).first()
    if not step:
        raise HTTPException(status_code=404, detail="步骤不存在")

    # 软删变量
    db.query(ApiScenarioVariable).filter(
        ApiScenarioVariable.step_id == step_id
    ).update({ApiScenarioVariable.is_deleted: True}, synchronize_session=False)

    step.is_deleted = True
    db.commit()

@router.post("/{scenario_id}/steps/reorder")
def reorder_steps(
    project_id: int,
    scenario_id: int,
    step_ids: List[int],
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """步骤排序"""
    get_project(project_id, db, current_user)
    for idx, step_id in enumerate(step_ids):
        step = db.query(ApiScenarioStep).filter(
            ApiScenarioStep.id == step_id, ApiScenarioStep.scenario_id == scenario_id
        ).first()
        if step:
            step.sort_order = idx
    db.commit()
    return {"success": True, "count": len(step_ids)}

# ==================== 变量提取 ====================

@router.get("/{scenario_id}/variables", response_model=List[ApiScenarioVariableResponse])
def list_scenario_variables(
    project_id: int,
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """变量提取配置列表"""
    get_project(project_id, db, current_user)
    scenario = db.query(ApiScenario).filter(
        ApiScenario.id == scenario_id, ApiScenario.project_id == project_id
    ).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="场景不存在")

    steps = db.query(ApiScenarioStep).filter(
        ApiScenarioStep.scenario_id == scenario_id
    ).all()
    step_ids = [s.id for s in steps]

    variables = db.query(ApiScenarioVariable).filter(
        ApiScenarioVariable.step_id.in_(step_ids)
    ).all() if step_ids else []
    return variables

@router.post("/{scenario_id}/steps/{step_id}/variables", response_model=ApiScenarioVariableResponse)
def create_scenario_variable(
    project_id: int,
    scenario_id: int,
    step_id: int,
    data: ApiScenarioVariableCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建变量提取配置"""
    get_project(project_id, db, current_user)
    step = db.query(ApiScenarioStep).filter(
        ApiScenarioStep.id == step_id,
        ApiScenarioStep.scenario_id == scenario_id,
    ).first()
    if not step:
        raise HTTPException(status_code=404, detail="步骤不存在")

    var = ApiScenarioVariable(
        step_id=step_id,
        var_name=data.var_name,
        extract_type=data.extract_type,
        extract_expr=data.extract_expr,
        default_value=data.default_value,
        scope=data.scope,
    )
    db.add(var)
    db.commit()
    db.refresh(var)
    return var

@router.put("/variables/{variable_id}", response_model=ApiScenarioVariableResponse)
def update_scenario_variable(
    project_id: int,
    variable_id: int,
    data: ApiScenarioVariableUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新变量提取配置"""
    get_project(project_id, db, current_user)
    var = db.query(ApiScenarioVariable).filter(
        ApiScenarioVariable.id == variable_id
    ).first()
    if not var:
        raise HTTPException(status_code=404, detail="变量不存在")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(var, field, value)
    db.commit()
    db.refresh(var)
    return var

@router.delete("/variables/{variable_id}")
def delete_scenario_variable(
    project_id: int,
    variable_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除变量提取配置"""
    get_project(project_id, db, current_user)
    var = db.query(ApiScenarioVariable).filter(
        ApiScenarioVariable.id == variable_id
    ).first()
    if not var:
        raise HTTPException(status_code=404, detail="变量不存在")
    var.is_deleted = True
    db.commit()
    return {"detail": "删除成功"}

@router.delete("/{scenario_id}/steps/{step_id}/variables")
def clear_step_variables(
    project_id: int,
    scenario_id: int,
    step_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """清空某步骤的所有变量提取配置（保存时先清空再重建，避免重复）"""
    get_project(project_id, db, current_user)
    step = db.query(ApiScenarioStep).filter(
        ApiScenarioStep.id == step_id,
        ApiScenarioStep.scenario_id == scenario_id,
    ).first()
    if not step:
        raise HTTPException(status_code=404, detail="步骤不存在")
    db.query(ApiScenarioVariable).filter(
        ApiScenarioVariable.step_id == step_id,
        ApiScenarioVariable.is_deleted == False,
    ).update({ApiScenarioVariable.is_deleted: True}, synchronize_session=False)
    db.commit()
    return {"detail": "已清空"}

# ==================== 场景执行 ====================

@router.post("/{scenario_id}/run")
async def run_scenario(
    project_id: int,
    scenario_id: int,
    data: ApiScenarioRunRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """执行场景"""
    get_project(project_id, db, current_user)
    scenario = db.query(ApiScenario).filter(
        ApiScenario.id == scenario_id, ApiScenario.project_id == project_id
    ).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="场景不存在")

    steps = db.query(ApiScenarioStep).filter(
        ApiScenarioStep.scenario_id == scenario_id
    ).order_by(ApiScenarioStep.sort_order).all()

    if not steps:
        raise HTTPException(status_code=400, detail="场景没有步骤")

    # 获取环境
    environment = None
    env_id = data.environment_id or scenario.environment_id
    if env_id:
        from app.models.test_plan import TestEnvironment
        environment = db.query(TestEnvironment).filter(TestEnvironment.id == env_id).first()

    # 创建执行记录
    execution = ApiExecution(
        project_id=project_id,
        execution_type="scenario",
        ref_id=scenario.id,
        ref_name=scenario.name,
        environment_id=env_id,
        status="running",
        total_steps=len(steps),
        passed_steps=0,
        failed_steps=0,
        skipped_steps=0,
        pass_rate=0.0,
        total_duration=0,
        avg_duration=0,
        trigger_type="manual",
        executed_by=current_user.id,
        started_at=china_now_naive(),
    )
    db.add(execution)
    db.flush()

    # 执行场景
    executor = ScenarioExecutor(db)
    scenario_dict = {
        "id": scenario.id,
        "name": scenario.name,
        "pre_script": scenario.pre_script,
        "post_script": scenario.post_script,
        "project_id": project_id,
        "execution_id": execution.id,
        "environment_name": environment.name if environment else "默认环境",
        "triggered_by": current_user.id,
    }
    steps_dict = [
        {
            "id": s.id,
            "step_type": s.step_type,
            "step_name": s.step_name,
            "sort_order": s.sort_order,
            "enabled": s.enabled,
            "api_id": s.api_id,
            "case_id": s.case_id,
            "request_config": s.request_config,
            "script_content": s.script_content,
            "wait_seconds": s.wait_seconds,
            "condition_expr": s.condition_expr,
            "loop_config": s.loop_config,
            "pre_script": s.pre_script,
            "post_script": s.post_script,
            "continue_on_failure": s.continue_on_failure,
            "max_retries": s.max_retries,
        }
        for s in steps
    ]

    env_dict = None
    if environment:
        env_dict = {
            "id": environment.id,
            "name": environment.name,
            "base_url": environment.base_url,
            "config": environment.config,
        }

    result = await executor.execute_scenario(
        scenario_dict, steps_dict, environment=env_dict, extra_vars=data.extra_vars
    )

    # 更新执行记录
    execution.status = result["status"]
    execution.passed_steps = result["passed_steps"]
    execution.failed_steps = result["failed_steps"]
    execution.skipped_steps = result["skipped_steps"]
    execution.pass_rate = result["pass_rate"]
    execution.total_duration = result["total_duration"]
    execution.avg_duration = result["avg_duration"]
    execution.completed_at = china_now_naive()

    # 保存执行结果详情
    for step_result in result["results"]:
        exec_result = ApiExecutionResult(
            execution_id=execution.id,
            step_id=step_result.get("step_id"),
            step_name=step_result.get("step_name", ""),
            sort_order=step_result.get("sort_order", 0),
            status=step_result.get("status", "pending"),
            request_method=step_result.get("request_method", ""),
            request_url=step_result.get("request_url", ""),
            request_headers=step_result.get("request_headers", {}),
            request_body=step_result.get("request_body", ""),
            response_status=step_result.get("response_status"),
            response_time=step_result.get("response_time", 0),
            response_size=step_result.get("response_size", 0),
            response_headers=step_result.get("response_headers", {}),
            response_body=step_result.get("response_body", ""),
            assertions=step_result.get("assertions", []),
            console_log=step_result.get("console_log", ""),
            error_message=step_result.get("error_message", ""),
            retry_count=step_result.get("retry_count", 0),
            started_at=china_now_naive(),
            completed_at=china_now_naive(),
        )
        db.add(exec_result)

    # 创建测试报告
    report = TestReport(
        project_id=project_id,
        title=f"接口测试报告 - {scenario.name}",
        report_type="api",
        status="completed",
        summary={
            "scenario_id": scenario.id,
            "execution_id": execution.id,
        },
        total_cases=result["total_steps"],
        passed_cases=result["passed_steps"],
        failed_cases=result["failed_steps"],
        pass_rate=result["pass_rate"],
        total_runs=1,
        avg_duration=result["avg_duration"],
        created_by=current_user.id,
    )
    db.add(report)
    db.flush()
    execution.report_id = report.id

    log_audit(
        db, action="execute", resource_type="plan",
        resource_id=scenario.id, resource_name=scenario.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "scenario_name": scenario.name, "status": execution.status},
    )
    db.commit()

    # 执行失败时自动创建缺陷
    if execution.status in ("failed", "partial") and execution.failed_steps > 0:
        from app.services.defect_helper import auto_create_defect
        failed_results = [r for r in result["results"] if r.get("status") == "failed"]
        error_msgs = [r.get("error_message", "") for r in failed_results if r.get("error_message")]
        auto_create_defect(
            db=db,
            project_id=project_id,
            title=f"[接口场景失败] {scenario.name}",
            description=(
                f"接口测试场景执行失败\n"
                f"场景名称: {scenario.name}\n"
                f"总步骤: {execution.total_steps}\n"
                f"通过: {execution.passed_steps}\n"
                f"失败: {execution.failed_steps}\n"
                f"错误信息: {'; '.join(error_msgs[:3])}"
            ),
            error_message="; ".join(error_msgs[:3]) if error_msgs else "场景执行失败",
            severity="critical" if execution.failed_steps > execution.passed_steps else "major",
            source="api_scenario",
            created_by=current_user.id,
        )

    return {
        "execution_id": execution.id,
        "report_id": report.id,
        "status": execution.status,
        "total_steps": execution.total_steps,
        "passed_steps": execution.passed_steps,
        "failed_steps": execution.failed_steps,
        "skipped_steps": execution.skipped_steps,
        "pass_rate": execution.pass_rate,
        "total_duration": execution.total_duration,
        "results": result["results"],
    }
