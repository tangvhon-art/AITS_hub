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
