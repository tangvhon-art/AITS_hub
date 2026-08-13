"""
版本管理 API
"""
from datetime import datetime
from app.core.timezone import china_now_naive
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_user
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


def _check_project_access(db: Session, user: User, project_id: int):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not user.is_admin and project.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权限访问该项目")
    return project


@router.get("", response_model=VersionListResponse)
def list_versions(
    project_id: int,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取版本列表"""
    _check_project_access(db, current_user, project_id)
    query = db.query(ProjectVersion).filter(ProjectVersion.project_id == project_id)
    if status:
        query = query.filter(ProjectVersion.status == status)
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建版本"""
    _check_project_access(db, current_user, project_id)
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
    _check_project_access(db, current_user, project_id)
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新版本"""
    _check_project_access(db, current_user, project_id)
    version = db.query(ProjectVersion).filter(
        ProjectVersion.id == version_id,
        ProjectVersion.project_id == project_id,
    ).first()
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(version, key, value)
    version.updated_at = china_now_naive()
    db.commit()
    db.refresh(version)
    return VersionResponse.model_validate(version)


@router.delete("/{version_id}", status_code=204)
def delete_version(
    project_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除版本"""
    _check_project_access(db, current_user, project_id)
    version = db.query(ProjectVersion).filter(
        ProjectVersion.id == version_id,
        ProjectVersion.project_id == project_id,
    ).first()
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")
    version.soft_delete()
    db.commit()
