"""
接口测试用例 API
用例CRUD + 断言CRUD + 执行 + AI生成
"""
import json
import logging
from datetime import datetime
from fastapi import APIRouter, Body, Depends, HTTPException, Request, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db, SessionLocal
from app.core.deps import get_current_user, get_project
from app.core.audit import log_audit
from app.core.timezone import china_now_naive
from app.models.user import User
from app.models.project import Project
from app.models.api_test import (
    ApiTestCase, ApiCaseAssertion, ApiExecution, ApiExecutionResult, ApiDefinition,
)
from app.models.agent_task import AgentTask
from app.schemas.api_test import (
    ApiTestCaseCreate, ApiTestCaseUpdate, ApiTestCaseResponse,
    ApiCaseAssertionCreate, ApiCaseAssertionUpdate, ApiCaseAssertionResponse,
    ApiCaseRunRequest, ApiCaseRunResponse,
    AiGenerateRequest, AiGenerateSaveRequest,
    PaginatedResponse,
)
from app.services.http_client import HttpClient
from app.services.variable_engine import VariableEngine
from app.services.assertion_engine import AssertionEngine
from app.services.script_engine import ScriptEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects/{project_id}/api-cases", tags=["接口测试-用例管理"])

@router.post("/search", response_model=PaginatedResponse)
def list_cases(
    project_id: int,
    module_id: Optional[int] = Body(None),
    api_id: Optional[int] = Body(None),
    keyword: Optional[str] = Body(None),
    priority: Optional[str] = Body(None),
    page: int = Body(1),
    page_size: int = Body(20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """用例列表"""
    get_project(project_id, db, current_user)
    query = db.query(ApiTestCase).filter(ApiTestCase.project_id == project_id)

    if module_id:
        query = query.filter(ApiTestCase.module_id == module_id)
    if api_id:
        query = query.filter(ApiTestCase.api_id == api_id)
    if priority:
        query = query.filter(ApiTestCase.priority == priority)
    if keyword:
        query = query.filter(ApiTestCase.name.like(f"%{keyword}%"))

    total = query.count()
    items = query.order_by(ApiTestCase.id.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return PaginatedResponse(
        total=total, page=page, page_size=page_size,
        items=[ApiTestCaseResponse.model_validate(item) for item in items],
    )

@router.get("/{case_id}", response_model=ApiTestCaseResponse)
def get_case(
    project_id: int,
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """用例详情"""
    get_project(project_id, db, current_user)
    case = db.query(ApiTestCase).filter(
        ApiTestCase.id == case_id, ApiTestCase.project_id == project_id
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")
    return case

@router.post("", response_model=ApiTestCaseResponse, status_code=status.HTTP_201_CREATED)
def create_case(
    project_id: int,
    data: ApiTestCaseCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建用例"""
    get_project(project_id, db, current_user)

    if data.api_id:
        api = db.query(ApiDefinition).filter(
            ApiDefinition.id == data.api_id, ApiDefinition.project_id == project_id
        ).first()
        if not api:
            raise HTTPException(status_code=400, detail="关联接口不存在")

    case = ApiTestCase(
        project_id=project_id,
        module_id=data.module_id,
        api_id=data.api_id,
        name=data.name,
        description=data.description,
        priority=data.priority,
        tags=data.tags,
        method=data.method,
        path=data.path,
        headers=data.headers,
        query_params=data.query_params,
        body_type=data.body_type,
        body_content=data.body_content,
        pre_script=data.pre_script,
        post_script=data.post_script,
        param_source=data.param_source,
        param_data=data.param_data,
        created_by=current_user.id,
    )
    db.add(case)
    db.flush()

    # 创建断言
    if data.assertions:
        for idx, assertion_data in enumerate(data.assertions):
            assertion = ApiCaseAssertion(
                case_id=case.id,
                assert_type=assertion_data.assert_type,
                assert_target=assertion_data.assert_target,
                operator=assertion_data.operator,
                expected_value=assertion_data.expected_value,
                sort_order=idx,
                enabled=assertion_data.enabled,
            )
            db.add(assertion)

    log_audit(
        db, action="create", resource_type="case",
        resource_id=case.id, resource_name=case.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "case_name": case.name},
    )
    db.commit()
    db.refresh(case)
    return case

@router.put("/{case_id}", response_model=ApiTestCaseResponse)
def update_case(
    project_id: int,
    case_id: int,
    data: ApiTestCaseUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新用例"""
    get_project(project_id, db, current_user)
    case = db.query(ApiTestCase).filter(
        ApiTestCase.id == case_id, ApiTestCase.project_id == project_id
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(case, key, value)

    log_audit(
        db, action="update", resource_type="case",
        resource_id=case.id, resource_name=case.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "case_name": case.name},
    )
    db.commit()
    db.refresh(case)
    return case

@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(
    project_id: int,
    case_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除用例（软删）"""
    get_project(project_id, db, current_user)
    case = db.query(ApiTestCase).filter(
        ApiTestCase.id == case_id, ApiTestCase.project_id == project_id
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")

    case.is_deleted = True
    # 软删关联断言
    db.query(ApiCaseAssertion).filter(
        ApiCaseAssertion.case_id == case_id
    ).update({ApiCaseAssertion.is_deleted: True}, synchronize_session=False)

    log_audit(
        db, action="delete", resource_type="case",
        resource_id=case.id, resource_name=case.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "case_name": case.name},
    )
    db.commit()

# ==================== 断言 CRUD ====================

@router.get("/{case_id}/assertions", response_model=List[ApiCaseAssertionResponse])
def list_assertions(
    project_id: int,
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """断言列表"""
    get_project(project_id, db, current_user)
    case = db.query(ApiTestCase).filter(
        ApiTestCase.id == case_id, ApiTestCase.project_id == project_id
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")

    assertions = db.query(ApiCaseAssertion).filter(
        ApiCaseAssertion.case_id == case_id
    ).order_by(ApiCaseAssertion.sort_order).all()
    return assertions

@router.post("/{case_id}/assertions", response_model=ApiCaseAssertionResponse, status_code=status.HTTP_201_CREATED)
def create_assertion(
    project_id: int,
    case_id: int,
    data: ApiCaseAssertionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """添加断言"""
    get_project(project_id, db, current_user)
    case = db.query(ApiTestCase).filter(
        ApiTestCase.id == case_id, ApiTestCase.project_id == project_id
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")

    # 计算排序
    max_order = db.query(ApiCaseAssertion).filter(
        ApiCaseAssertion.case_id == case_id
    ).count()

    assertion = ApiCaseAssertion(
        case_id=case_id,
        assert_type=data.assert_type,
        assert_target=data.assert_target,
        operator=data.operator,
        expected_value=data.expected_value,
        sort_order=data.sort_order if data.sort_order is not None else max_order,
        enabled=data.enabled,
    )
    db.add(assertion)
    db.commit()
    db.refresh(assertion)
    return assertion

@router.put("/assertions/{assertion_id}", response_model=ApiCaseAssertionResponse)
def update_assertion(
    project_id: int,
    assertion_id: int,
    data: ApiCaseAssertionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新断言"""
    get_project(project_id, db, current_user)
    assertion = db.query(ApiCaseAssertion).filter(
        ApiCaseAssertion.id == assertion_id
    ).first()
    if not assertion:
        raise HTTPException(status_code=404, detail="断言不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(assertion, key, value)

    db.commit()
    db.refresh(assertion)
    return assertion

@router.delete("/assertions/{assertion_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assertion(
    project_id: int,
    assertion_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除断言"""
    get_project(project_id, db, current_user)
    assertion = db.query(ApiCaseAssertion).filter(
        ApiCaseAssertion.id == assertion_id
    ).first()
    if not assertion:
        raise HTTPException(status_code=404, detail="断言不存在")

    assertion.is_deleted = True
    db.commit()

# ==================== 用例执行 ====================

@router.post("/{case_id}/run", response_model=ApiCaseRunResponse)
async def run_case(
    project_id: int,
    case_id: int,
    data: ApiCaseRunRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """执行单个用例"""
    get_project(project_id, db, current_user)
    case = db.query(ApiTestCase).filter(
        ApiTestCase.id == case_id, ApiTestCase.project_id == project_id
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")

    # 变量引擎
    var_engine = VariableEngine()
    if data.environment_vars:
        var_engine.load_from_dict("environment", data.environment_vars)
    base_url = data.base_url or var_engine.get("base_url") or ""

    # 如果关联了接口，使用接口的 method 和 path
    if case.api_id:
        api_def = db.query(ApiDefinition).filter(
            ApiDefinition.id == case.api_id, ApiDefinition.project_id == project_id
        ).first()
        if api_def:
            method = api_def.method or "GET"
            path = api_def.path or ""
        else:
            method = case.method or "GET"
            path = case.path or ""
    else:
        method = case.method or "GET"
        path = case.path or ""

    url = var_engine.replace(base_url + path)
    headers = var_engine.replace_headers(case.headers)
    params = var_engine.replace_params(case.query_params)
    body_content = var_engine.replace_body(case.body_type, case.body_content)

    # 前置脚本
    script_engine = ScriptEngine()
    console_log = ""
    if case.pre_script:
        script_result = script_engine.execute(
            case.pre_script,
            environment_vars=var_engine.environment_vars,
            global_vars=var_engine.global_vars,
            request={"method": method, "url": url},
        )
        for k, v in script_result.variables.items():
            var_engine.set("scenario", k, v)
        console_log += script_result.output
        url = var_engine.replace(base_url + path)
        headers = var_engine.replace_headers(case.headers)
        params = var_engine.replace_params(case.query_params)
        body_content = var_engine.replace_body(case.body_type, case.body_content)

    # 发送请求
    http_client = HttpClient()
    response = await http_client.asend(
        method=method, url=url, headers=headers, params=params,
        body_type=case.body_type, body_content=body_content,
    )

    # 后置脚本
    tests = []
    if case.post_script:
        script_result = script_engine.execute(
            case.post_script,
            environment_vars=var_engine.environment_vars,
            global_vars=var_engine.global_vars,
            request={"method": method, "url": url},
            response=response.to_dict(),
        )
        console_log += script_result.output
        tests = script_result.tests

    # 断言
    assertions = db.query(ApiCaseAssertion).filter(
        ApiCaseAssertion.case_id == case_id,
        ApiCaseAssertion.enabled == True,
    ).order_by(ApiCaseAssertion.sort_order).all()

    assertion_engine = AssertionEngine()
    assertion_dicts = [
        {"assert_type": a.assert_type, "assert_target": a.assert_target,
         "operator": a.operator, "expected_value": a.expected_value, "enabled": a.enabled}
        for a in assertions
    ]
    assertion_results = assertion_engine.run_all(assertion_dicts, response)
    all_passed = all(a.passed for a in assertion_results) and not response.error

    # 保存执行记录
    execution = ApiExecution(
        project_id=project_id,
        execution_type="case",
        ref_id=case.id,
        ref_name=case.name,
        environment_id=data.environment_id,
        status="passed" if all_passed else "failed",
        total_steps=1,
        passed_steps=1 if all_passed else 0,
        failed_steps=0 if all_passed else 1,
        skipped_steps=0,
        pass_rate=100.0 if all_passed else 0.0,
        total_duration=response.elapsed_ms / 1000,
        avg_duration=response.elapsed_ms / 1000,
        trigger_type="manual",
        executed_by=current_user.id,
        started_at=china_now_naive(),
        completed_at=china_now_naive(),
    )
    db.add(execution)
    db.flush()

    # 保存执行结果详情
    result = ApiExecutionResult(
        execution_id=execution.id,
        step_id=None,
        step_name=case.name,
        sort_order=0,
        status="passed" if all_passed else "failed",
        request_method=method,
        request_url=url,
        request_headers={h.get("key", ""): h.get("value", "") for h in headers if h.get("enabled", True)},
        request_body=json.dumps(body_content, ensure_ascii=False) if body_content else "",
        response_status=response.status_code,
        response_time=response.elapsed_ms,
        response_size=response.size,
        response_headers=response.headers,
        response_body=response.body,
        assertions=[a.to_dict() for a in assertion_results],
        console_log=console_log,
        error_message=response.error or "",
        retry_count=0,
        started_at=china_now_naive(),
        completed_at=china_now_naive(),
    )
    db.add(result)

    log_audit(
        db, action="execute", resource_type="case",
        resource_id=case.id, resource_name=case.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "case_name": case.name, "status": execution.status},
    )
    db.commit()

    # 执行失败时自动创建缺陷
    if not all_passed:
        from app.services.defect_helper import auto_create_defect
        failed_assertions = [a for a in assertion_results if not a.passed]
        error_detail = response.error or "; ".join(a.message for a in failed_assertions if a.message)
        auto_create_defect(
            db=db,
            project_id=project_id,
            title=f"[接口用例失败] {case.name}",
            description=(
                f"接口测试用例执行失败\n"
                f"用例名称: {case.name}\n"
                f"请求方法: {method}\n"
                f"请求URL: {url}\n"
                f"响应状态码: {response.status_code}\n"
                f"错误信息: {error_detail}"
            ),
            error_message=error_detail,
            severity="major",
            source="api_case",
            created_by=current_user.id,
        )

    return ApiCaseRunResponse(
        execution_id=execution.id,
        status=execution.status,
        response_status=response.status_code,
        response_time=response.elapsed_ms,
        response_body=response.body,
        response_headers=response.headers,
        assertions=[a.to_dict() for a in assertion_results],
        console_log=console_log,
        tests=tests,
        error=response.error,
    )

@router.post("/batch-run")
async def batch_run_cases(
    project_id: int,
    case_ids: List[int],
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量执行用例"""
    get_project(project_id, db, current_user)
    # 简化实现：逐个执行
    results = []
    for case_id in case_ids:
        case = db.query(ApiTestCase).filter(
            ApiTestCase.id == case_id, ApiTestCase.project_id == project_id
        ).first()
        if case:
            # 这里简化处理，实际应复用 run_case 逻辑
            results.append({"case_id": case_id, "name": case.name, "status": "pending"})
    return {"results": results, "total": len(results)}

# ==================== AI 生成用例 ====================

@router.post("/ai-generate")
def ai_generate_cases(
    project_id: int,
    data: AiGenerateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """触发AI生成用例（异步）"""
    get_project(project_id, db, current_user)

    if data.api_id:
        api = db.query(ApiDefinition).filter(
            ApiDefinition.id == data.api_id, ApiDefinition.project_id == project_id
        ).first()
        if not api:
            raise HTTPException(status_code=404, detail="接口不存在")

    # 创建 AgentTask
    agent_task = AgentTask(
        project_id=project_id,
        agent_type="api_case_generator",
        status="pending",
        input_params={
            "api_id": data.api_id,
            "strategy": data.strategy,
            "case_count": data.case_count,
            "coverage_scenarios": data.coverage_scenarios,
            "assertion_depth": data.assertion_depth,
            "prompt_id": data.prompt_id,
        },
        llm_config_id=data.llm_config_id,
        created_by=current_user.id,
    )
    db.add(agent_task)
    db.flush()

    log_audit(
        db, action="generate", resource_type="case",
        resource_id=agent_task.id, resource_name="AI生成用例",
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "api_id": data.api_id, "task_id": agent_task.id},
    )
    db.commit()

    # 异步执行
    try:
        from app.tasks.api_case_tasks import generate_api_cases_task
        generate_api_cases_task.delay(agent_task.id)
    except Exception:
        # 降级到 BackgroundTasks
        background_tasks.add_task(_run_generate_task, agent_task.id)

    return {"task_id": agent_task.id, "status": "pending"}

def _run_generate_task(task_id: int):
    """后台执行生成任务（降级用）"""
    db = SessionLocal()
    try:
        from app.tasks.api_case_tasks import generate_api_cases_task
        generate_api_cases_task(task_id)
    except Exception as e:
        logger.error(f"AI生成用例任务失败: {e}")
    finally:
        db.close()

@router.get("/ai-generate/{task_id}")
def get_ai_generate_status(
    project_id: int,
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询AI生成进度和结果"""
    get_project(project_id, db, current_user)
    task = db.query(AgentTask).filter(
        AgentTask.id == task_id, AgentTask.project_id == project_id
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    return {
        "task_id": task.id,
        "status": task.status,
        "output_result": task.output_result,
        "error_message": task.error_message,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }

@router.post("/ai-generate/{task_id}/save")
def save_ai_generated_cases(
    project_id: int,
    task_id: int,
    data: AiGenerateSaveRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """保存AI生成的用例"""
    get_project(project_id, db, current_user)
    task = db.query(AgentTask).filter(
        AgentTask.id == task_id, AgentTask.project_id == project_id
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status != "success":
        raise HTTPException(status_code=400, detail="任务未完成或失败")

    generated_cases = task.output_result.get("cases", []) if task.output_result else []
    selected_indices = data.selected_indices or list(range(len(generated_cases)))

    selected_cases = []
    for idx in selected_indices:
        if 0 <= idx < len(generated_cases):
            selected_cases.append(generated_cases[idx])

    from app.services.ai_creation_service import AICreationService
    created_cases = AICreationService.create_api_cases(
        db,
        project_id=project_id,
        cases=selected_cases,
        api_id=task.input_params.get("api_id") if task.input_params else None,
        module_id=data.module_id,
        created_by=current_user.id,
    )
    saved_count = len(created_cases)

    log_audit(
        db, action="create", resource_type="case",
        resource_id=task.id, resource_name="AI生成用例保存",
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "saved_count": saved_count, "task_id": task_id},
    )
    db.commit()
    return {"saved_count": saved_count}

@router.post("/ai-generate/batch")
def batch_ai_generate(
    project_id: int,
    api_ids: List[int],
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量AI生成用例"""
    get_project(project_id, db, current_user)
    task_ids = []
    for api_id in api_ids:
        agent_task = AgentTask(
            project_id=project_id,
            agent_type="api_case_generator",
            status="pending",
            input_params={"api_id": api_id, "strategy": "comprehensive", "case_count": 5},
            created_by=current_user.id,
        )
        db.add(agent_task)
        db.flush()
        task_ids.append(agent_task.id)

        try:
            from app.tasks.api_case_tasks import generate_api_cases_task
            generate_api_cases_task.delay(agent_task.id)
        except Exception:
            pass

    db.commit()
    return {"task_ids": task_ids, "total": len(task_ids)}
