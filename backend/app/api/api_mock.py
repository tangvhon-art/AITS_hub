"""
Mock 服务 API
Mock期望CRUD + Mock服务入口
"""
import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, Request, status, Query, Response
from sqlalchemy.orm import Session
from typing import List, Optional, Any
from app.database import get_db
from app.core.deps import get_current_user, get_project
from app.core.audit import log_audit
from app.models.user import User
from app.models.project import Project
from app.models.api_test import ApiMockExpectation
from app.schemas.api_test import (
    ApiMockExpectationCreate, ApiMockExpectationUpdate, ApiMockExpectationResponse,
    PaginatedResponse,
)

router = APIRouter(tags=["接口测试-Mock服务"])

@router.get("/api/projects/{project_id}/api-mock/expectations", response_model=PaginatedResponse)
def list_mock_expectations(
    project_id: int,
    keyword: Optional[str] = Query(None),
    method: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mock期望列表"""
    get_project(project_id, db, current_user)
    query = db.query(ApiMockExpectation).filter(ApiMockExpectation.project_id == project_id)

    if method:
        query = query.filter(ApiMockExpectation.method == method.upper())
    if keyword:
        query = query.filter(
            (ApiMockExpectation.name.like(f"%{keyword}%")) |
            (ApiMockExpectation.path.like(f"%{keyword}%"))
        )

    total = query.count()
    items = query.order_by(ApiMockExpectation.id.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return PaginatedResponse(
        total=total, page=page, page_size=page_size,
        items=[ApiMockExpectationResponse.model_validate(item) for item in items],
    )

@router.post("/api/projects/{project_id}/api-mock/expectations", response_model=ApiMockExpectationResponse, status_code=status.HTTP_201_CREATED)
def create_mock_expectation(
    project_id: int,
    data: ApiMockExpectationCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建Mock期望"""
    get_project(project_id, db, current_user)
    mock = ApiMockExpectation(
        project_id=project_id,
        api_id=data.api_id,
        name=data.name,
        method=data.method,
        path=data.path,
        match_rules=data.match_rules,
        response_status=data.response_status,
        response_headers=data.response_headers,
        response_body=data.response_body,
        delay_ms=data.delay_ms,
        enabled=data.enabled,
        created_by=current_user.id,
    )
    db.add(mock)
    db.flush()

    log_audit(
        db, action="create", resource_type="project",
        resource_id=mock.id, resource_name=mock.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "mock_name": mock.name, "type": "api_mock"},
    )
    db.commit()
    db.refresh(mock)
    return mock

@router.put("/api/projects/{project_id}/api-mock/expectations/{mock_id}", response_model=ApiMockExpectationResponse)
def update_mock_expectation(
    project_id: int,
    mock_id: int,
    data: ApiMockExpectationUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新Mock期望"""
    get_project(project_id, db, current_user)
    mock = db.query(ApiMockExpectation).filter(
        ApiMockExpectation.id == mock_id, ApiMockExpectation.project_id == project_id
    ).first()
    if not mock:
        raise HTTPException(status_code=404, detail="Mock期望不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(mock, key, value)

    log_audit(
        db, action="update", resource_type="project",
        resource_id=mock.id, resource_name=mock.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "mock_name": mock.name, "type": "api_mock"},
    )
    db.commit()
    db.refresh(mock)
    return mock

@router.delete("/api/projects/{project_id}/api-mock/expectations/{mock_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mock_expectation(
    project_id: int,
    mock_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除Mock期望"""
    get_project(project_id, db, current_user)
    mock = db.query(ApiMockExpectation).filter(
        ApiMockExpectation.id == mock_id, ApiMockExpectation.project_id == project_id
    ).first()
    if not mock:
        raise HTTPException(status_code=404, detail="Mock期望不存在")

    mock.is_deleted = True
    log_audit(
        db, action="delete", resource_type="project",
        resource_id=mock.id, resource_name=mock.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "mock_name": mock.name, "type": "api_mock"},
    )
    db.commit()

# ==================== Mock 服务入口 ====================

def _match_mock_request(
    mock: ApiMockExpectation,
    method: str,
    path: str,
    request: Request,
) -> bool:
    """匹配Mock请求"""
    if mock.method != method.upper():
        return False

    # 路径匹配（支持简单通配符）
    mock_path = mock.path.rstrip("/")
    request_path = "/" + path.rstrip("/")
    if mock_path != request_path:
        # 简单前缀匹配
        if not mock_path.endswith("*") or not request_path.startswith(mock_path.rstrip("*")):
            return False

    # 匹配规则
    if mock.match_rules:
        rules = mock.match_rules if isinstance(mock.match_rules, dict) else {}
        # 检查请求头匹配
        header_rules = rules.get("headers", {})
        for key, value in header_rules.items():
            if request.headers.get(key) != value:
                return False
        # 检查查询参数匹配
        query_rules = rules.get("query_params", {})
        for key, value in query_rules.items():
            if request.query_params.get(key) != value:
                return False

    return True

@router.api_route("/mock/{project_id}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def mock_service_entry(
    project_id: int,
    path: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Mock服务入口"""
    method = request.method

    # 查找启用的Mock期望
    mocks = db.query(ApiMockExpectation).filter(
        ApiMockExpectation.project_id == project_id,
        ApiMockExpectation.enabled == True,
    ).all()

    matched_mock = None
    for mock in mocks:
        if _match_mock_request(mock, method, path, request):
            matched_mock = mock
            break

    if not matched_mock:
        return Response(
            content=json.dumps({"error": "No matching mock expectation found", "path": "/" + path}),
            status_code=404,
            media_type="application/json",
        )

    # 延迟
    if matched_mock.delay_ms and matched_mock.delay_ms > 0:
        await asyncio.sleep(matched_mock.delay_ms / 1000)

    # 增加命中计数
    matched_mock.hit_count = (matched_mock.hit_count or 0) + 1
    db.commit()

    # 构建响应
    headers = {}
    if matched_mock.response_headers:
        if isinstance(matched_mock.response_headers, list):
            for h in matched_mock.response_headers:
                if isinstance(h, dict) and h.get("enabled", True):
                    headers[h.get("key", "")] = h.get("value", "")
        elif isinstance(matched_mock.response_headers, dict):
            headers = matched_mock.response_headers

    body = matched_mock.response_body or ""
    return Response(
        content=body,
        status_code=matched_mock.response_status or 200,
        headers=headers,
        media_type=headers.get("Content-Type", "application/json"),
    )
