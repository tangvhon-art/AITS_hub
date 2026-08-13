"""
缺陷管理 API
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.defect import Defect
from app.models.project import Project
from app.schemas.defect import (
    DefectCreate,
    DefectUpdate,
    DefectResponse,
    DefectListResponse,
)

router = APIRouter(prefix="/api/projects/{project_id}/defects", tags=["缺陷管理"])


def _check_project_access(db: Session, user: User, project_id: int):
    """检查项目访问权限"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not user.is_admin and project.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权限访问该项目")
    return project


@router.get("", response_model=DefectListResponse)
def list_defects(
    project_id: int,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取缺陷列表"""
    _check_project_access(db, current_user, project_id)

    query = db.query(Defect).filter(Defect.project_id == project_id)
    if status:
        query = query.filter(Defect.status == status)
    if severity:
        query = query.filter(Defect.severity == severity)

    total = query.count()
    defects = query.order_by(Defect.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return DefectListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[DefectResponse.model_validate(d) for d in defects],
    )


@router.get("/{defect_id}", response_model=DefectResponse)
def get_defect(
    project_id: int,
    defect_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取缺陷详情"""
    _check_project_access(db, current_user, project_id)
    defect = db.query(Defect).filter(Defect.id == defect_id, Defect.project_id == project_id).first()
    if not defect:
        raise HTTPException(status_code=404, detail="缺陷不存在")
    return DefectResponse.model_validate(defect)


@router.post("", response_model=DefectResponse)
def create_defect(
    project_id: int,
    defect_data: DefectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建缺陷"""
    _check_project_access(db, current_user, project_id)

    defect = Defect(
        project_id=project_id,
        run_id=defect_data.run_id,
        case_id=defect_data.case_id,
        title=defect_data.title,
        description=defect_data.description,
        severity=defect_data.severity,
        priority=defect_data.priority,
        status=defect_data.status or "open",
        root_cause=defect_data.root_cause,
        root_cause_category=defect_data.root_cause_category,
        reproduce_steps=defect_data.reproduce_steps,
        expected_result=defect_data.expected_result,
        actual_result=defect_data.actual_result,
        screenshot_url=defect_data.screenshot_url,
        error_log=defect_data.error_log,
        assignee_id=defect_data.assignee_id,
        created_by=current_user.id,
    )
    db.add(defect)
    db.commit()
    db.refresh(defect)
    return DefectResponse.model_validate(defect)


@router.put("/{defect_id}", response_model=DefectResponse)
def update_defect(
    project_id: int,
    defect_id: int,
    defect_data: DefectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新缺陷"""
    _check_project_access(db, current_user, project_id)
    defect = db.query(Defect).filter(Defect.id == defect_id, Defect.project_id == project_id).first()
    if not defect:
        raise HTTPException(status_code=404, detail="缺陷不存在")

    update_data = defect_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(defect, key, value)
    defect.updated_at = datetime.now()

    db.commit()
    db.refresh(defect)
    return DefectResponse.model_validate(defect)


@router.delete("/{defect_id}")
def delete_defect(
    project_id: int,
    defect_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除缺陷"""
    _check_project_access(db, current_user, project_id)
    defect = db.query(Defect).filter(Defect.id == defect_id, Defect.project_id == project_id).first()
    if not defect:
        raise HTTPException(status_code=404, detail="缺陷不存在")
    db.delete(defect)
    db.commit()
    return {"message": "缺陷已删除"}


@router.post("/{defect_id}/status", response_model=DefectResponse)
def update_defect_status(
    project_id: int,
    defect_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新缺陷状态"""
    valid_statuses = ["open", "confirmed", "resolved", "closed", "reopened"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"无效状态，可选: {valid_statuses}")

    _check_project_access(db, current_user, project_id)
    defect = db.query(Defect).filter(Defect.id == defect_id, Defect.project_id == project_id).first()
    if not defect:
        raise HTTPException(status_code=404, detail="缺陷不存在")

    defect.status = status
    defect.updated_at = datetime.now()
    db.commit()
    db.refresh(defect)
    return DefectResponse.model_validate(defect)
