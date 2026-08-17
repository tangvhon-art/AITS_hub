"""
版本管理 API
"""
from datetime import datetime
from app.core.timezone import china_now_naive
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Body
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_user, get_project
from app.core.audit import log_audit
from app.models.user import User
from app.models.project import Project
from app.models.project_version import ProjectVersion
from app.schemas.project_version import (
    VersionCreate,
    VersionUpdate,
    VersionResponse,
    VersionListResponse,
)

router = APIRouter(prefix="/api/projects/{project_id}/versions", tags=["版本管理"])

@router.post("/search", response_model=VersionListResponse)
def list_versions(
    project_id: int,
    status: Optional[str] = Body(None),
    name: Optional[str] = Body(None),
    start_date: Optional[str] = Body(None),
    end_date: Optional[str] = Body(None),
    page: int = Body(1),
    page_size: int = Body(50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取版本列表"""
    get_project(project_id, db, current_user)
    query = db.query(ProjectVersion).filter(ProjectVersion.project_id == project_id)
    if status:
        query = query.filter(ProjectVersion.status == status)
    if name:
        query = query.filter(ProjectVersion.name.ilike(f"%{name}%"))
    if start_date:
        try:
            sd = datetime.fromisoformat(start_date)
            query = query.filter(ProjectVersion.start_date >= sd)
        except ValueError:
            pass
    if end_date:
        try:
            ed = datetime.fromisoformat(end_date)
            query = query.filter(ProjectVersion.end_date <= ed)
        except ValueError:
            pass
    total = query.count()
    versions = query.order_by(ProjectVersion.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return VersionListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[VersionResponse.model_validate(v) for v in versions],
    )

@router.post("", response_model=VersionResponse, status_code=201)
def create_version(
    project_id: int,
    data: VersionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建版本"""
    get_project(project_id, db, current_user)
    version = ProjectVersion(
        project_id=project_id,
        name=data.name,
        description=data.description or "",
        status=data.status or "draft",
        start_date=data.start_date,
        end_date=data.end_date,
        released_at=data.released_at,
        created_by=current_user.id,
    )
    db.add(version)
    db.flush()
    log_audit(
        db, action="create", resource_type="version",
        resource_id=version.id, resource_name=version.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "name": version.name, "status": version.status},
    )
    db.commit()
    db.refresh(version)
    return VersionResponse.model_validate(version)

@router.get("/{version_id}", response_model=VersionResponse)
def get_version(
    project_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取版本详情"""
    get_project(project_id, db, current_user)
    version = db.query(ProjectVersion).filter(
        ProjectVersion.id == version_id,
        ProjectVersion.project_id == project_id,
    ).first()
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")
    return VersionResponse.model_validate(version)

@router.put("/{version_id}", response_model=VersionResponse)
def update_version(
    project_id: int,
    version_id: int,
    data: VersionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新版本"""
    get_project(project_id, db, current_user)
    version = db.query(ProjectVersion).filter(
        ProjectVersion.id == version_id,
        ProjectVersion.project_id == project_id,
    ).first()
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")
    old_data = {
        "name": version.name,
        "description": version.description,
        "status": version.status,
        "start_date": version.start_date,
        "end_date": version.end_date,
        "released_at": version.released_at,
    }
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(version, key, value)
    version.updated_at = china_now_naive()
    log_audit(
        db, action="update", resource_type="version",
        resource_id=version.id, resource_name=version.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"before": old_data, "after": update_data},
    )
    db.commit()
    db.refresh(version)
    return VersionResponse.model_validate(version)

@router.delete("/{version_id}", status_code=204)
def delete_version(
    project_id: int,
    version_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除版本"""
    get_project(project_id, db, current_user)
    version = db.query(ProjectVersion).filter(
        ProjectVersion.id == version_id,
        ProjectVersion.project_id == project_id,
    ).first()
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")
    version_name = version.name
    version.soft_delete()
    log_audit(
        db, action="delete", resource_type="version",
        resource_id=version_id, resource_name=version_name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
