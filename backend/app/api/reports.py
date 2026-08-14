"""
报告管理 API
"""
import json
import logging
from datetime import datetime
from app.core.timezone import china_now_naive
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_user
from app.core.audit import log_audit
from app.models.user import User
from app.models.report import TestReport
from app.models.project import Project
from app.models.project_version import ProjectVersion
from app.models.agent_task import AgentTask
from app.agents.report_generator import ReportGeneratorAgent
from app.schemas.report import (
    ReportCreate,
    ReportUpdate,
    ReportGenerateRequest,
    ReportResponse,
    ReportListResponse,
)

logger = logging.getLogger(__name__)

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
    version_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取报告列表"""
    _check_project_access(db, current_user, project_id)

    query = db.query(TestReport).filter(TestReport.project_id == project_id)
    if version_id is not None:
        query = query.filter(TestReport.version_id == version_id)
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
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 生成测试报告（异步）"""
    _check_project_access(db, current_user, project_id)

    # 校验版本存在
    version = db.query(ProjectVersion).filter(
        ProjectVersion.id == req.version_id,
        ProjectVersion.project_id == project_id,
    ).first()
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在，请先选择版本再生成报告")

    report_title = req.title or f"{version.name} - 测试报告 - {china_now_naive().strftime('%Y-%m-%d %H:%M')}"

    # 创建报告记录
    report = TestReport(
        project_id=project_id,
        version_id=req.version_id,
        title=report_title,
        report_type=req.report_type,
        status="generating",
        created_by=current_user.id,
    )
    db.add(report)
    db.flush()

    # 创建 Agent 任务记录
    agent_task = AgentTask(
        project_id=project_id,
        agent_type="report_generator",
        status="running",
        input_params={
            "report_type": req.report_type,
            "version_id": req.version_id,
            "version_name": version.name,
            "title": report_title,
        },
        llm_config_id=req.llm_config_id,
        created_by=current_user.id,
    )
    db.add(agent_task)
    db.flush()

    log_audit(
        db, action="generate", resource_type="report",
        resource_id=report.id, resource_name=report.title,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "report_type": req.report_type, "version_id": req.version_id},
    )
    db.commit()
    db.refresh(report)
    db.refresh(agent_task)

    # 异步生成：优先 Celery，降级 BackgroundTasks
    use_celery = False
    celery_task_id = None
    try:
        from app.tasks.report_tasks import generate_test_report_task
        task_result = generate_test_report_task.delay(
            report.id, project_id, req.report_type, req.version_id,
            report_title, req.llm_config_id, agent_task.id
        )
        celery_task_id = task_result.id
        use_celery = True
        logger.info(f"报告 #{report.id} 已提交 Celery 任务: task_id={celery_task_id}")
    except Exception as celery_e:
        logger.warning(f"Celery 任务提交失败，降级到 BackgroundTasks: {celery_e}")

        def _generate_in_background(rid: int, pid: int, rtype: str, vid: int, title: str, llm_id, at_id: int):
            from app.tasks.report_tasks import generate_test_report_task
            generate_test_report_task(rid, pid, rtype, vid, title, llm_id, at_id)

        background_tasks.add_task(
            _generate_in_background,
            report.id, project_id, req.report_type, req.version_id,
            report_title, req.llm_config_id, agent_task.id
        )

    # 在 AgentTask 中记录 celery_task_id
    try:
        agent_task.input_params["celery_task_id"] = celery_task_id
        agent_task.input_params["executor"] = "celery" if use_celery else "background"
        db.commit()
    except Exception:
        pass

    return ReportResponse.model_validate(report)


@router.put("/{report_id}", response_model=ReportResponse)
def update_report(
    project_id: int,
    report_id: int,
    report_data: ReportUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新报告"""
    _check_project_access(db, current_user, project_id)
    report = db.query(TestReport).filter(TestReport.id == report_id, TestReport.project_id == project_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    old_data = {"title": report.title, "status": report.status}
    update_data = report_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(report, key, value)
    report.updated_at = china_now_naive()
    log_audit(
        db, action="update", resource_type="report",
        resource_id=report.id, resource_name=report.title,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"before": old_data, "after": update_data},
    )
    db.commit()
    db.refresh(report)
    return ReportResponse.model_validate(report)


@router.delete("/{report_id}")
def delete_report(
    project_id: int,
    report_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除报告"""
    _check_project_access(db, current_user, project_id)
    report = db.query(TestReport).filter(TestReport.id == report_id, TestReport.project_id == project_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    report_name = report.title
    report.soft_delete()
    log_audit(
        db, action="delete", resource_type="report",
        resource_id=report_id, resource_name=report_name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return {"message": "报告已删除"}
