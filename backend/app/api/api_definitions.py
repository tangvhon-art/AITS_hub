"""
接口定义管理 API
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.core.deps import get_current_user, get_project
from app.core.audit import log_audit
from app.models.user import User
from app.models.project import Project
from app.models.api_test import ApiDefinition, ApiModule
from app.schemas.api_test import (
    ApiDefinitionCreate, ApiDefinitionUpdate, ApiDefinitionResponse,
    PaginatedResponse,
)

router = APIRouter(prefix="/api/projects/{project_id}/api-definitions", tags=["接口测试-接口定义"])

@router.get("", response_model=PaginatedResponse)
def list_definitions(
    project_id: int,
    module_id: Optional[int] = Query(None, description="目录ID筛选"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    method: Optional[str] = Query(None, description="请求方法筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """接口列表（分页/筛选）"""
    get_project(project_id, db, current_user)
    query = db.query(ApiDefinition).filter(ApiDefinition.project_id == project_id)

    if module_id:
        query = query.filter(ApiDefinition.module_id == module_id)
    if method:
        query = query.filter(ApiDefinition.method == method.upper())
    if keyword:
        query = query.filter(
            (ApiDefinition.name.like(f"%{keyword}%")) |
            (ApiDefinition.path.like(f"%{keyword}%"))
        )

    total = query.count()
    items = query.order_by(ApiDefinition.id.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[ApiDefinitionResponse.model_validate(item) for item in items],
    )

@router.get("/{definition_id}", response_model=ApiDefinitionResponse)
def get_definition(
    project_id: int,
    definition_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """接口详情"""
    get_project(project_id, db, current_user)
    api = db.query(ApiDefinition).filter(
        ApiDefinition.id == definition_id, ApiDefinition.project_id == project_id
    ).first()
    if not api:
        raise HTTPException(status_code=404, detail="接口不存在")
    return api

@router.post("", response_model=ApiDefinitionResponse, status_code=status.HTTP_201_CREATED)
def create_definition(
    project_id: int,
    data: ApiDefinitionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建接口"""
    get_project(project_id, db, current_user)

    if data.module_id:
        module = db.query(ApiModule).filter(
            ApiModule.id == data.module_id, ApiModule.project_id == project_id
        ).first()
        if not module:
            raise HTTPException(status_code=400, detail="目录不存在")

    api = ApiDefinition(
        project_id=project_id,
        module_id=data.module_id,
        name=data.name,
        method=data.method,
        path=data.path,
        description=data.description,
        tags=data.tags,
        status=data.status,
        headers=data.headers,
        query_params=data.query_params,
        path_params=data.path_params,
        body_type=data.body_type,
        body_content=data.body_content,
        response_examples=data.response_examples,
        created_by=current_user.id,
    )
    db.add(api)
    db.flush()
    log_audit(
        db, action="create", resource_type="project",
        resource_id=api.id, resource_name=api.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "api_name": api.name, "type": "api_definition"},
    )
    db.commit()
    db.refresh(api)
    return api

@router.put("/{definition_id}", response_model=ApiDefinitionResponse)
def update_definition(
    project_id: int,
    definition_id: int,
    data: ApiDefinitionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新接口"""
    get_project(project_id, db, current_user)
    api = db.query(ApiDefinition).filter(
        ApiDefinition.id == definition_id, ApiDefinition.project_id == project_id
    ).first()
    if not api:
        raise HTTPException(status_code=404, detail="接口不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(api, key, value)

    log_audit(
        db, action="update", resource_type="project",
        resource_id=api.id, resource_name=api.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "api_name": api.name, "type": "api_definition"},
    )
    db.commit()
    db.refresh(api)
    return api

@router.delete("/{definition_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_definition(
    project_id: int,
    definition_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除接口（软删）"""
    get_project(project_id, db, current_user)
    api = db.query(ApiDefinition).filter(
        ApiDefinition.id == definition_id, ApiDefinition.project_id == project_id
    ).first()
    if not api:
        raise HTTPException(status_code=404, detail="接口不存在")

    api.is_deleted = True
    log_audit(
        db, action="delete", resource_type="project",
        resource_id=api.id, resource_name=api.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "api_name": api.name, "type": "api_definition"},
    )
    db.commit()


@router.post("/{definition_id}/ai-generate-doc")
def ai_generate_doc(
    project_id: int,
    definition_id: int,
    request: Request,
    llm_config_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 生成接口文档（异步）"""
    from app.core.rate_limiter import rate_limit
    rate_limit(request, key_prefix="ai_doc", limit=20, window=60)

    get_project(project_id, db, current_user)
    api = db.query(ApiDefinition).filter(
        ApiDefinition.id == definition_id, ApiDefinition.project_id == project_id
    ).first()
    if not api:
        raise HTTPException(status_code=404, detail="接口不存在")

    from app.models.agent_task import AgentTask

    task = AgentTask(
        project_id=project_id,
        agent_type="api_doc_generator",
        status="pending",
        input_params={"api_id": definition_id},
        llm_config_id=llm_config_id,
        created_by=current_user.id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    try:
        from app.tasks.api_doc_tasks import generate_api_doc_task
        generate_api_doc_task.delay(task.id)
    except Exception:
        import logging
        logging.getLogger(__name__).warning("Celery 不可用，使用后台线程回退")
        import threading

        def _run():
            from app.tasks.api_doc_tasks import generate_api_doc_task
            generate_api_doc_task(task.id)

        threading.Thread(target=_run, daemon=True).start()

    return {"task_id": task.id, "status": "pending"}


@router.get("/{definition_id}/ai-generate-doc/{task_id}")
def ai_generate_doc_status(
    project_id: int,
    definition_id: int,
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询 AI 文档生成状态"""
    get_project(project_id, db, current_user)
    from app.models.agent_task import AgentTask

    task = db.query(AgentTask).filter(
        AgentTask.id == task_id, AgentTask.project_id == project_id
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    result = {
        "status": task.status,
        "documentation": "",
        "error": task.error_message or "",
    }
    if task.status == "success" and task.output_result:
        result["documentation"] = task.output_result.get("documentation", "")

    return result
