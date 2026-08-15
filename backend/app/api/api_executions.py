"""
执行记录 API
执行记录查询 + 结果详情 + 报告
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.core.deps import get_current_user, get_project
from app.models.user import User
from app.models.project import Project
from app.models.api_test import ApiExecution, ApiExecutionResult
from app.models.report import TestReport
from app.schemas.api_test import (
    ApiExecutionResponse, ApiExecutionResultResponse, PaginatedResponse,
)

router = APIRouter(prefix="/api/projects/{project_id}/api-executions", tags=["接口测试-执行记录"])

@router.get("", response_model=PaginatedResponse)
def list_executions(
    project_id: int,
    execution_type: Optional[str] = Query(None, description="执行类型: case/scenario/debug"),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """执行记录列表"""
    get_project(project_id, db, current_user)
    query = db.query(ApiExecution).filter(ApiExecution.project_id == project_id)

    if execution_type:
        query = query.filter(ApiExecution.execution_type == execution_type)
    if status:
        query = query.filter(ApiExecution.status == status)

    total = query.count()
    items = query.order_by(ApiExecution.id.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return PaginatedResponse(
        total=total, page=page, page_size=page_size,
        items=[ApiExecutionResponse.model_validate(item) for item in items],
    )

@router.get("/{execution_id}", response_model=ApiExecutionResponse)
def get_execution(
    project_id: int,
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """执行记录详情"""
    get_project(project_id, db, current_user)
    execution = db.query(ApiExecution).filter(
        ApiExecution.id == execution_id, ApiExecution.project_id == project_id
    ).first()
    if not execution:
        raise HTTPException(status_code=404, detail="执行记录不存在")
    return execution

@router.get("/{execution_id}/results", response_model=List[ApiExecutionResultResponse])
def get_execution_results(
    project_id: int,
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """执行结果详情"""
    get_project(project_id, db, current_user)
    execution = db.query(ApiExecution).filter(
        ApiExecution.id == execution_id, ApiExecution.project_id == project_id
    ).first()
    if not execution:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    results = db.query(ApiExecutionResult).filter(
        ApiExecutionResult.execution_id == execution_id
    ).order_by(ApiExecutionResult.sort_order).all()
    return results

@router.get("/{execution_id}/report")
def get_execution_report(
    project_id: int,
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取执行报告"""
    get_project(project_id, db, current_user)
    execution = db.query(ApiExecution).filter(
        ApiExecution.id == execution_id, ApiExecution.project_id == project_id
    ).first()
    if not execution:
        raise HTTPException(status_code=404, detail="执行记录不存在")

    if not execution.report_id:
        raise HTTPException(status_code=404, detail="该执行记录没有关联报告")

    report = db.query(TestReport).filter(TestReport.id == execution.report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    return {
        "report_id": report.id,
        "title": report.title,
        "report_type": report.report_type,
        "status": report.status,
        "total_cases": report.total_cases,
        "passed_cases": report.passed_cases,
        "failed_cases": report.failed_cases,
        "pass_rate": report.pass_rate,
        "total_runs": report.total_runs,
        "avg_duration": report.avg_duration,
        "summary": report.summary,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }
