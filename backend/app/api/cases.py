import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.core.deps import get_current_user, get_project
from app.core.audit import log_audit
from app.core.timezone import china_now_naive
from app.models.user import User
from app.models.project import Project
from app.models.test_case import TestCase
from app.models.requirement import TestRequirement, RequirementFeature
from app.models.agent_task import AgentTask
from app.schemas.test_case import TestCaseCreate, TestCaseUpdate, TestCaseResponse, TestCaseBatchCreate
from app.schemas.requirement import (
    CaseGenerateRequest,
    FeatureSplitRequest,
    RequirementFeatureCreate, RequirementFeatureUpdate, RequirementFeatureResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects/{project_id}/cases", tags=["用例管理"])

@router.post("/search", response_model=List[TestCaseResponse])
def list_cases(
    project_id: int,
    module: Optional[str] = Body(None),
    priority: Optional[str] = Body(None),
    status: Optional[str] = Body(None),
    title: Optional[str] = Body(None),
    case_type: Optional[str] = Body(None),
    req_id: Optional[int] = Body(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取用例列表，支持按模块/优先级/状态/标题/类型/需求筛选"""
    get_project(project_id, db, current_user)
    query = db.query(TestCase).filter(TestCase.project_id == project_id)
    if module:
        query = query.filter(TestCase.module == module)
    if priority:
        query = query.filter(TestCase.priority == priority)
    if status:
        query = query.filter(TestCase.status == status)
    if title:
        query = query.filter(TestCase.title.ilike(f"%{title}%"))
    if case_type:
        query = query.filter(TestCase.case_type == case_type)
    if req_id is not None:
        query = query.filter(TestCase.req_id == req_id)
    return query.order_by(TestCase.created_at.desc()).all()

@router.post("", response_model=TestCaseResponse, status_code=status.HTTP_201_CREATED)
def create_case(
    project_id: int,
    case_data: TestCaseCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建单条用例"""
    get_project(project_id, db, current_user)
    case = TestCase(
        project_id=project_id,
        req_id=case_data.req_id,
        title=case_data.title,
        module=case_data.module,
        priority=case_data.priority,
        case_type=case_data.case_type,
        preconditions=case_data.preconditions,
        steps=json.dumps(case_data.steps, ensure_ascii=False) if isinstance(case_data.steps, list) else case_data.steps,
        expected_result=case_data.expected_result,
        bdd_content=case_data.bdd_content,
        created_by=current_user.id,
    )
    db.add(case)
    db.flush()
    log_audit(
        db, action="create", resource_type="case",
        resource_id=case.id, resource_name=case.title,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "title": case.title, "priority": case.priority},
    )
    db.commit()
    db.refresh(case)
    return case

@router.post("/batch", response_model=List[TestCaseResponse], status_code=status.HTTP_201_CREATED)
def batch_create_cases(
    project_id: int,
    batch_data: TestCaseBatchCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量创建用例（AI 生成后保存）"""
    get_project(project_id, db, current_user)
    cases = []
    for case_data in batch_data.cases:
        case = TestCase(
            project_id=project_id,
            req_id=case_data.req_id,
            title=case_data.title,
            module=case_data.module,
            priority=case_data.priority,
            case_type=case_data.case_type,
            preconditions=case_data.preconditions,
            steps=json.dumps(case_data.steps, ensure_ascii=False) if isinstance(case_data.steps, list) else case_data.steps,
            expected_result=case_data.expected_result,
            bdd_content=case_data.bdd_content,
            created_by=current_user.id,
        )
        db.add(case)
        cases.append(case)
    db.flush()
    log_audit(
        db, action="create", resource_type="case",
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "batch_count": len(cases), "action": "batch_create"},
    )
    db.commit()
    for case in cases:
        db.refresh(case)
    return cases

@router.post("/batch-update-status")
def batch_update_status(
    project_id: int,
    data: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """批量修改用例状态"""
    get_project(project_id, db, current_user)
    case_ids = data.get("case_ids", [])
    new_status = data.get("status", "")
    if not case_ids or not new_status:
        raise HTTPException(status_code=400, detail="case_ids 和 status 不能为空")
    if new_status not in ("draft", "active", "archived"):
        raise HTTPException(status_code=400, detail="status 必须是 draft/active/archived")

    updated = db.query(TestCase).filter(
        TestCase.id.in_(case_ids),
        TestCase.project_id == project_id,
        TestCase.is_deleted == False,
    ).update({TestCase.status: new_status}, synchronize_session=False)
    db.commit()
    log_audit(
        db, action="batch_update_status", resource_type="case",
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "case_ids": case_ids, "status": new_status, "updated": updated},
    )
    return {"updated": updated}

@router.get("/{case_id}", response_model=TestCaseResponse)
def get_case(
    project_id: int,
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取用例详情"""
    get_project(project_id, db, current_user)
    case = db.query(TestCase).filter(
        TestCase.id == case_id,
        TestCase.project_id == project_id,
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")
    return case

@router.put("/{case_id}", response_model=TestCaseResponse)
def update_case(
    project_id: int,
    case_id: int,
    case_data: TestCaseUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新用例"""
    get_project(project_id, db, current_user)
    case = db.query(TestCase).filter(
        TestCase.id == case_id,
        TestCase.project_id == project_id,
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")

    old_data = {"title": case.title, "priority": case.priority, "status": case.status}
    update_data = case_data.model_dump(exclude_unset=True)
    if "steps" in update_data and isinstance(update_data["steps"], list):
        update_data["steps"] = json.dumps(update_data["steps"], ensure_ascii=False)
    for key, value in update_data.items():
        setattr(case, key, value)
    log_audit(
        db, action="update", resource_type="case",
        resource_id=case.id, resource_name=case.title,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"before": old_data, "after": {k: v for k, v in update_data.items() if k != "steps"}},
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
    """删除用例"""
    get_project(project_id, db, current_user)
    case = db.query(TestCase).filter(
        TestCase.id == case_id,
        TestCase.project_id == project_id,
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")
    case_name = case.title
    case.soft_delete()
    log_audit(
        db, action="delete", resource_type="case",
        resource_id=case_id, resource_name=case_name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()

@router.post("/generate")
def generate_cases(
    project_id: int,
    gen_request: CaseGenerateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    AI 生成测试用例（异步执行）
    提交后立即返回任务ID，生成结果可在Agent任务中查看
    """
    from app.core.rate_limiter import rate_limit
    rate_limit(request, key_prefix="ai_case", limit=20, window=60)

    get_project(project_id, db, current_user)

    # 获取需求内容
    requirement_content = gen_request.content
    req_id = gen_request.requirement_id
    req_title = None
    if req_id:
        requirement = db.query(TestRequirement).filter(
            TestRequirement.id == req_id,
            TestRequirement.project_id == project_id,
        ).first()
        if requirement:
            requirement_content = requirement.content or requirement.title
            req_title = requirement.title

    if not requirement_content or not requirement_content.strip():
        raise HTTPException(status_code=400, detail="需求内容不能为空")

    # 创建 Agent 任务记录
    task = AgentTask(
        project_id=project_id,
        agent_type="case_generator",
        status="pending",
        input_params={
            "content": gen_request.content,
            "content_length": len(requirement_content),
            "count": gen_request.count,
            "requirement_id": req_id,
            "requirement_title": req_title,
            "prompt_id": gen_request.prompt_id,
            "feature_ids": gen_request.feature_ids or [],
            "page_backend": gen_request.backend,
        },
        llm_config_id=gen_request.llm_config_id,
        created_by=current_user.id,
    )
    db.add(task)
    db.flush()
    log_audit(
        db, action="generate", resource_type="case",
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "count": gen_request.count, "requirement_id": req_id, "task_id": task.id},
    )
    db.commit()
    db.refresh(task)

    # 异步执行（Celery 优先，失败降级后台线程）
    from app.core.tasks import dispatch_task
    from app.tasks.case_tasks import generate_cases_task
    dispatch_task(generate_cases_task, task.id)

    return {
        "task_id": task.id,
        "status": "pending",
        "message": "用例生成任务已提交，可在Agent任务中查看进度",
    }


@router.get("/generate/{task_id}")
def generate_cases_status(
    project_id: int,
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询用例生成任务状态"""
    get_project(project_id, db, current_user)

    task = db.query(AgentTask).filter(
        AgentTask.id == task_id,
        AgentTask.project_id == project_id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    result = {
        "status": task.status,
        "case_count": 0,
        "cases_saved": 0,
        "error": task.error_message or "",
    }
    if task.status == "success" and task.output_result:
        result["case_count"] = task.output_result.get("case_count", 0)
        result["cases_saved"] = task.output_result.get("cases_saved", 0)

    return result


# ── 需求功能点 ──────────────────────────────────────────────

@router.get("/requirements/{req_id}/features")
def list_features(
    project_id: int,
    req_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取需求的功能点列表（按模块分组）"""
    get_project(project_id, db, current_user)
    req = db.query(TestRequirement).filter(
        TestRequirement.id == req_id,
        TestRequirement.project_id == project_id,
        TestRequirement.is_deleted == False,
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="需求不存在")

    features = db.query(RequirementFeature).filter(
        RequirementFeature.requirement_id == req_id,
        RequirementFeature.is_deleted == False,
    ).order_by(RequirementFeature.sort_order, RequirementFeature.id).all()

    # 按模块分组
    modules_map = {}
    for f in features:
        mod = modules_map.setdefault(f.module_name, {
            "module_name": f.module_name,
            "module_desc": f.module_desc,
            "features": [],
        })
        mod["features"].append({
            "id": f.id,
            "name": f.name,
            "description": f.description,
            "priority": f.priority,
            "design_methods": _safe_json(f.design_methods),
            "preconditions": f.preconditions,
            "module_name": f.module_name,
            "sort_order": f.sort_order,
        })

    return {
        "split_status": req.feature_split_status,
        "modules": list(modules_map.values()),
        "total": len(features),
    }


@router.post("/requirements/{req_id}/split-features")
def trigger_split_features(
    project_id: int,
    req_id: int,
    request: Request,
    data: FeatureSplitRequest = Body(default_factory=FeatureSplitRequest),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """手动触发功能点拆分（异步，支持页面选择执行后端）"""
    get_project(project_id, db, current_user)
    req = db.query(TestRequirement).filter(
        TestRequirement.id == req_id,
        TestRequirement.project_id == project_id,
        TestRequirement.is_deleted == False,
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="需求不存在")

    if not req.content or not req.content.strip():
        raise HTTPException(status_code=400, detail="需求内容为空，无法拆分功能点")

    req.feature_split_status = "splitting"
    db.commit()

    log_audit(
        db, action="split_features", resource_type="requirement",
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"requirement_id": req_id, "page_backend": data.backend},
    )

    # 异步拆分（Celery 优先，失败降级后台线程）；page_backend 透传给任务
    from app.core.tasks import dispatch_task
    from app.tasks.case_tasks import split_features_task
    dispatch_task(split_features_task, req_id, data.backend, data.llm_config_id)

    return {"message": "功能点拆分任务已提交", "status": "splitting"}


@router.put("/requirement-features/{feature_id}")
def update_feature(
    project_id: int,
    feature_id: int,
    data: RequirementFeatureUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """编辑功能点"""
    get_project(project_id, db, current_user)
    feat = db.query(RequirementFeature).filter(
        RequirementFeature.id == feature_id,
        RequirementFeature.project_id == project_id,
        RequirementFeature.is_deleted == False,
    ).first()
    if not feat:
        raise HTTPException(status_code=404, detail="功能点不存在")

    update_data = data.model_dump(exclude_unset=True)
    if "design_methods" in update_data and update_data["design_methods"] is not None:
        update_data["design_methods"] = json.dumps(update_data["design_methods"], ensure_ascii=False)
    for key, value in update_data.items():
        setattr(feat, key, value)

    log_audit(
        db, action="update", resource_type="requirement_feature",
        user=current_user, resource_id=feature_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return {"message": "更新成功"}


@router.delete("/requirement-features/{feature_id}")
def delete_feature(
    project_id: int,
    feature_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除功能点"""
    get_project(project_id, db, current_user)
    feat = db.query(RequirementFeature).filter(
        RequirementFeature.id == feature_id,
        RequirementFeature.project_id == project_id,
        RequirementFeature.is_deleted == False,
    ).first()
    if not feat:
        raise HTTPException(status_code=404, detail="功能点不存在")

    feat.is_deleted = True
    feat.deleted_at = china_now_naive()
    log_audit(
        db, action="delete", resource_type="requirement_feature",
        user=current_user, resource_id=feature_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return {"message": "删除成功"}


def _safe_json(value):
    """安全解析 JSON 字段"""
    import json as _json
    if not value:
        return []
    try:
        return _json.loads(value)
    except (_json.JSONDecodeError, TypeError):
        return []
