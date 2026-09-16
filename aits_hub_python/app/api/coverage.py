import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_user, get_project
from app.core.audit import log_audit
from app.models.user import User
from app.models.test_coverage import CoverageConfig
from app.schemas.test_coverage import (
    CoverageConfigUpdate, CoverageConfigResponse, CoverageSnapshotResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/projects/{project_id}/coverage",
    tags=["覆盖率分析"],
)


@router.get("")
def get_coverage(
    project_id: int,
    version_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project(project_id, db, current_user)
    from app.services.coverage_analyzer import CoverageAnalyzer
    analyzer = CoverageAnalyzer(db)
    result = analyzer.get_latest(project_id)
    if not result:
        result = analyzer.calculate_and_save(project_id, version_id)
    return result


@router.get("/matrix")
def get_coverage_matrix(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project(project_id, db, current_user)
    from app.models.test_coverage import CoverageSnapshot
    snapshot = db.query(CoverageSnapshot).filter(
        CoverageSnapshot.project_id == project_id,
    ).order_by(CoverageSnapshot.calculated_at.desc()).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail="暂无覆盖率数据，请先计算")
    return {
        "matrix": snapshot.coverage_matrix,
        "uncovered_apis": snapshot.uncovered_apis,
        "total_apis": snapshot.total_apis,
        "covered_apis": snapshot.covered_apis,
    }


@router.get("/trend")
def get_coverage_trend(
    project_id: int,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project(project_id, db, current_user)
    from app.services.coverage_analyzer import CoverageAnalyzer
    analyzer = CoverageAnalyzer(db)
    return analyzer.get_trend(project_id, days)


@router.post("/recalculate")
def recalculate(
    project_id: int,
    request: Request,
    version_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project(project_id, db, current_user)
    from app.services.coverage_analyzer import CoverageAnalyzer
    analyzer = CoverageAnalyzer(db)
    result = analyzer.calculate_and_save(project_id, version_id)

    log_audit(
        db, action="recalculate", resource_type="coverage",
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "result": result},
    )
    db.commit()
    return result


@router.get("/uncovered")
def get_uncovered(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project(project_id, db, current_user)
    from app.models.test_coverage import CoverageSnapshot
    snapshot = db.query(CoverageSnapshot).filter(
        CoverageSnapshot.project_id == project_id,
    ).order_by(CoverageSnapshot.calculated_at.desc()).first()
    if not snapshot:
        return {"uncovered_apis": [], "total": 0}
    return {"uncovered_apis": snapshot.uncovered_apis, "total": len(snapshot.uncovered_apis)}


@router.get("/config", response_model=CoverageConfigResponse)
def get_config(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project(project_id, db, current_user)
    config = db.query(CoverageConfig).filter(
        CoverageConfig.project_id == project_id,
        CoverageConfig.is_deleted == False,
    ).first()
    if not config:
        config = CoverageConfig(project_id=project_id)
        db.add(config)
        db.commit()
        db.refresh(config)
    return CoverageConfigResponse.model_validate(config)


@router.put("/config", response_model=CoverageConfigResponse)
def update_config(
    project_id: int,
    data: CoverageConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project(project_id, db, current_user)
    config = db.query(CoverageConfig).filter(
        CoverageConfig.project_id == project_id,
        CoverageConfig.is_deleted == False,
    ).first()
    if not config:
        config = CoverageConfig(project_id=project_id)
        db.add(config)

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(config, key, value)
    db.commit()
    db.refresh(config)
    return CoverageConfigResponse.model_validate(config)
