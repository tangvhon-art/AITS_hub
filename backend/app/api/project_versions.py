"""
版本管理 API（项目级资源）

标准 CRUD（search / create / get / update / delete + 分页 + 审计 + 统一响应）
由 BaseRouter 组装；支持状态筛选、名称关键词、起止日期范围筛选。
"""
from fastapi import APIRouter

from app.core.base_router import ResourceRouter
from app.models.project_version import ProjectVersion
from app.schemas.project_version import VersionCreate, VersionUpdate, VersionResponse

# ── 标准资源路由（统一响应 {code, message, data} + 分页 + 审计）──
resource = ResourceRouter(
    prefix="/api/projects/{project_id}/versions",
    tags=["版本管理"],
    resource_name="版本",
    model=ProjectVersion,
    create_schema=VersionCreate,
    update_schema=VersionUpdate,
    response_schema=VersionResponse,
    search_fields=["status", "start_date__gte", "start_date__lte", "end_date__gte", "end_date__lte"],
    keyword_fields=["name"],
    order_by=["created_at_desc"],
)
router = resource.build()
