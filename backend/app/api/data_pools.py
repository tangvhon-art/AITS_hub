"""
测试数据池 API（项目级资源）

标准 CRUD（search / create / get / update / delete + 分页 + 审计 + 统一响应）
由 BaseRouter 组装；generate / preview（造数）为业务端点保留自定义实现。
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.base_router import ResourceRouter
from app.core.crud import CRUDBase
from app.core.deps import get_current_user, get_project
from app.models.user import User
from app.models.test_data_pool import TestDataPool
from app.schemas.test_data_pool import TestDataPoolCreate, TestDataPoolUpdate

logger = logging.getLogger(__name__)

# ── 标准资源路由（统一响应 {code, message, data} + 分页 + 审计）──
resource = ResourceRouter(
    prefix="/api/projects/{project_id}/data-pools",
    tags=["测试数据池"],
    resource_name="数据池",
    model=TestDataPool,
    create_schema=TestDataPoolCreate,
    update_schema=TestDataPoolUpdate,
    search_fields=["data_type"],
    keyword_fields=["name", "description"],
    order_by=["id_desc"],
    # schema_config -> schema 字段映射需要 by_alias 的 CRUDBase 实例
    crud=CRUDBase(TestDataPool, "数据池", by_alias=True),
)
router = resource.build()


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
