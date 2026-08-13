"""
报告管理 API
"""
import json
from datetime import datetime
from app.core.timezone import china_now_naive
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.report import TestReport
from app.models.project import Project
from app.agents.report_generator import ReportGeneratorAgent
from app.schemas.report import (
    ReportCreate,
    ReportUpdate,
    ReportGenerateRequest,
    ReportResponse,
    ReportListResponse,
)

router = APIRouter(prefix="/api/projects/{project_id}/reports", tags=["报告管理"])


def _check_project_access(db: Session, user: User, project_id: int):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not user.is_admin and project.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权限访问该项目")
    return project


@router.get("", response_model=ReportListResponse)
def list_reports(
    project_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取报告列表"""
    _check_project_access(db, current_user, project_id)

    query = db.query(TestReport).filter(TestReport.project_id == project_id)
    total = query.count()
    reports = query.order_by(TestReport.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return ReportListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[ReportResponse.model_validate(r) for r in reports],
    )


@router.get("/{report_id}", response_model=ReportResponse)
def get_report(
    project_id: int,
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取报告详情"""
    _check_project_access(db, current_user, project_id)
    report = db.query(TestReport).filter(TestReport.id == report_id, TestReport.project_id == project_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    return ReportResponse.model_validate(report)


@router.post("/generate", response_model=ReportResponse)
def generate_report(
    project_id: int,
    req: ReportGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 生成测试报告"""
    _check_project_access(db, current_user, project_id)

    # 创建报告记录
    report = TestReport(
        project_id=project_id,
        title=req.title or f"测试报告 - {china_now_naive().strftime('%Y-%m-%d %H:%M')}",
        report_type=req.report_type,
        status="generating",
        created_by=current_user.id,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    try:
        # 调用报告生成 Agent
        agent = ReportGeneratorAgent(db, llm_config_id=req.llm_config_id)
        result = agent.generate(
            project_id=project_id,
            report_type=req.report_type,
            title=report.title,
        )

        # 更新报告
        report.content = result.get("content", "")
        report.summary = result.get("summary", {})
        report.total_cases = result.get("total_cases", 0)
        report.passed_cases = result.get("passed_cases", 0)
        report.failed_cases = result.get("failed_cases", 0)
        report.pass_rate = result.get("pass_rate", 0.0)
        report.total_defects = result.get("total_defects", 0)
        report.open_defects = result.get("open_defects", 0)
        report.total_runs = result.get("total_runs", 0)
        report.avg_duration = result.get("avg_duration", 0.0)
        report.status = "completed"
        report.updated_at = china_now_naive()

        db.commit()
        db.refresh(report)

    except Exception as e:
        report.status = "failed"
        report.content = f"报告生成失败: {str(e)}"
        db.commit()
        raise HTTPException(status_code=500, detail=f"报告生成失败: {str(e)}")

    return ReportResponse.model_validate(report)


@router.put("/{report_id}", response_model=ReportResponse)
def update_report(
    project_id: int,
    report_id: int,
    report_data: ReportUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新报告"""
    _check_project_access(db, current_user, project_id)
    report = db.query(TestReport).filter(TestReport.id == report_id, TestReport.project_id == project_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    update_data = report_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(report, key, value)
    report.updated_at = china_now_naive()
    db.commit()
    db.refresh(report)
    return ReportResponse.model_validate(report)


@router.delete("/{report_id}")
def delete_report(
    project_id: int,
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除报告"""
    _check_project_access(db, current_user, project_id)
    report = db.query(TestReport).filter(TestReport.id == report_id, TestReport.project_id == project_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    db.delete(report)
    db.commit()
    return {"message": "报告已删除"}
