import logging
from typing import Optional
from fastapi import APIRouter, Body, Depends, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_user, get_project
from app.core.crud import CRUDBase
from app.models.user import User
from app.models.test_data_pool import TestDataPool
from app.schemas.test_data_pool import (
    TestDataPoolCreate, TestDataPoolUpdate, TestDataPoolResponse,
    PaginatedResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/projects/{project_id}/data-pools",
    tags=["测试数据池"],
)

# CRUDBase 实例：by_alias=True 处理 schema_config -> schema 字段映射
pool_crud = CRUDBase(TestDataPool, "数据池", by_alias=True)


@router.post("", response_model=TestDataPoolResponse, response_model_by_alias=True)
def create_pool(
    project_id: int,
    data: TestDataPoolCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project(project_id, db, current_user)
    pool = pool_crud.create(db, data, project_id=project_id, created_by=current_user.id)
    return TestDataPoolResponse.model_validate(pool)


@router.post("/search", response_model=PaginatedResponse)
def list_pools(
    project_id: int,
    keyword: Optional[str] = Body(None),
    data_type: Optional[str] = Body(None),
    page: int = Body(1),
    page_size: int = Body(20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project(project_id, db, current_user)
    # keyword 模糊搜索在 CRUDBase.list 之外处理，因为它是 like 而非 eq
    query = db.query(TestDataPool).filter(TestDataPool.project_id == project_id)
    if keyword:
        query = query.filter(TestDataPool.name.contains(keyword))
    if data_type:
        query = query.filter(TestDataPool.data_type == data_type)
    total = query.count()
    items = query.order_by(TestDataPool.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PaginatedResponse(
        total=total, page=page, page_size=page_size,
        items=[TestDataPoolResponse.model_validate(p).model_dump(by_alias=True) for p in items],
    )


@router.get("/{pool_id}", response_model=TestDataPoolResponse, response_model_by_alias=True)
def get_pool(
    project_id: int,
    pool_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project(project_id, db, current_user)
    pool = pool_crud.get(db, pool_id, project_id)
    return TestDataPoolResponse.model_validate(pool)


@router.put("/{pool_id}", response_model=TestDataPoolResponse, response_model_by_alias=True)
def update_pool(
    project_id: int,
    pool_id: int,
    data: TestDataPoolUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project(project_id, db, current_user)
    pool = pool_crud.update(db, pool_id, data, project_id)
    return TestDataPoolResponse.model_validate(pool)


@router.delete("/{pool_id}")
def delete_pool(
    project_id: int,
    pool_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project(project_id, db, current_user)
    pool_crud.soft_delete(db, pool_id, project_id)
    return {"detail": "删除成功"}


@router.post("/{pool_id}/generate")
def generate_data(
    project_id: int,
    pool_id: int,
    count: int = Query(10, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project(project_id, db, current_user)
    from app.services.data_factory import DataFactory
    factory = DataFactory()
    data = factory.generate_from_pool(db, pool_id, count)
    return {"data": data, "count": len(data)}


@router.get("/{pool_id}/preview")
def preview_data(
    project_id: int,
    pool_id: int,
    count: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project(project_id, db, current_user)
    from app.services.data_factory import DataFactory
    factory = DataFactory()
    data = factory.generate_from_pool(db, pool_id, count)
    return {"data": data, "count": len(data)}
