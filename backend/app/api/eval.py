"""AI 模型五维综合测评 API

统一前缀：/api/eval（系统级，不归属项目）。
遵循现有 JWT 鉴权、项目隔离、审计规范。
"""
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_user, get_project
from app.models.user import User
from app.models.eval import (
    EvalTarget, EvalDataset, EvalCase, EvalTask, EvalRun, EvalResult,
    EvalReport, EvalIssue, EvalBaseline,
)
from app.models.llm_config import LLMConfig
from app.schemas.eval import (
    EvalTargetCreate, EvalTargetUpdate, EvalTargetResponse,
    EvalDatasetCreate, EvalDatasetUpdate, EvalDatasetResponse,
    EvalCaseCreate, EvalCaseUpdate, EvalCaseResponse,
    EvalTaskCreate, EvalTaskResponse,
    EvalRunResponse, EvalResultResponse, ManualScoreIn,
    EvalReportResponse, EvalIssueCreate, EvalIssueStatusUpdate, EvalIssueResponse,
    EvalBaselineCreate, EvalBaselineResponse, PaginatedEvalResponse,
    RedteamRunIn, EvalCompareIn, EvalReportGenerateIn,
)
from app.services import eval_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/eval", tags=["AI测评"])
sse_router = APIRouter(prefix="/api/eval", tags=["AI测评-SSE"])
global_router = APIRouter(prefix="/api/eval", tags=["AI测评-全局"])

ALLOWED_TARGET_TYPES = ("llm", "agent", "external_agent", "business")
ALLOWED_EVAL_TYPES = ("ai_judge", "agent", "business", "redteam", "manual")


def _audit(db, current_user: User, request: Request, action: str, resource_type: str,
           resource_id: int, resource_name: str, detail: Optional[dict] = None):
    try:
        from app.api.audit_logs import log_audit
        log_audit(
            db, action=action, resource_type=resource_type, resource_id=resource_id,
            resource_name=resource_name, user=current_user,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"), detail=detail,
        )
    except Exception as e:
        logger.debug(f"审计写入失败: {e}")


# ═══════════════════════════ 测评对象 ═══════════════════════════
@router.get("/targets", response_model=List[EvalTargetResponse])
def list_targets(target_type: Optional[str] = None, db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    q = db.query(EvalTarget).filter(EvalTarget.status == "active")
    if target_type:
        q = q.filter(EvalTarget.target_type == target_type)
    return q.order_by(EvalTarget.id.desc()).all()


@router.post("/targets", response_model=EvalTargetResponse)
def create_target(data: EvalTargetCreate, request: Request,
                  db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if data.target_type not in ALLOWED_TARGET_TYPES:
        raise HTTPException(400, f"被测对象类型必须为: {', '.join(ALLOWED_TARGET_TYPES)}")
    if data.target_type == "external_agent" and not (data.service_url and data.call_path):
        raise HTTPException(400, "外部工作流需填写服务地址 service_url 与调用路径 call_path")
    item = EvalTarget(created_by=current_user.id, **data.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    _audit(db, current_user, request, "create", "eval_target", item.id, item.name)
    return item


@router.put("/targets/{target_id}", response_model=EvalTargetResponse)
def update_target(target_id: int, data: EvalTargetUpdate, request: Request,
                  db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.query(EvalTarget).filter(EvalTarget.id == target_id).first()
    if not item:
        raise HTTPException(404, "被测对象不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(item, k, v)
    db.commit(); db.refresh(item)
    _audit(db, current_user, request, "update", "eval_target", item.id, item.name)
    return item


@router.delete("/targets/{target_id}")
def delete_target(target_id: int, request: Request,
                  db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.query(EvalTarget).filter(EvalTarget.id == target_id).first()
    if not item:
        raise HTTPException(404, "被测对象不存在")
    item_id, item_name = item.id, item.name  # 提交前缓存，避免软删后会话过期实例再加载报 ObjectDeletedError
    item.soft_delete()
    db.commit()
    _audit(db, current_user, request, "delete", "eval_target", item_id, item_name)
    return {"message": "已停用被测对象"}


# ═══════════════════════════ 测评数据集 ═══════════════════════════
@router.get("/datasets", response_model=List[EvalDatasetResponse])
def list_datasets(eval_type: Optional[str] = None, db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    q = db.query(EvalDataset)
    if eval_type:
        q = q.filter(EvalDataset.eval_type == eval_type)
    return q.order_by(EvalDataset.id.desc()).all()


@router.post("/datasets", response_model=EvalDatasetResponse)
def create_dataset(data: EvalDatasetCreate, request: Request,
                   db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if data.eval_type not in ALLOWED_EVAL_TYPES:
        raise HTTPException(400, f"数据集类型必须为: {', '.join(ALLOWED_EVAL_TYPES)}")
    item = EvalDataset(created_by=current_user.id, **data.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return item


@router.put("/datasets/{dataset_id}", response_model=EvalDatasetResponse)
def update_dataset(dataset_id: int, data: EvalDatasetUpdate, request: Request,
                   db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.query(EvalDataset).filter(EvalDataset.id == dataset_id).first()
    if not item:
        raise HTTPException(404, "数据集不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(item, k, v)
    db.commit(); db.refresh(item)
    return item


@router.delete("/datasets/{dataset_id}")
def delete_dataset(dataset_id: int, request: Request,
                   db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.query(EvalDataset).filter(EvalDataset.id == dataset_id).first()
    if not item:
        raise HTTPException(404, "数据集不存在")
    item.soft_delete()
    db.commit()
    return {"message": "已归档数据集"}


# ═══════════════════════════ 测评用例 ═══════════════════════════
@router.get("/datasets/{dataset_id}/cases")
def list_cases(dataset_id: int, keyword: Optional[str] = None,
               page: int = Query(1), page_size: int = Query(20),
               db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    q = db.query(EvalCase).filter(EvalCase.dataset_id == dataset_id, EvalCase.status == "active")
    if keyword:
        q = q.filter(EvalCase.title.contains(keyword) | EvalCase.prompt.contains(keyword))
    total = q.count()
    items = q.order_by(EvalCase.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PaginatedEvalResponse(total=total, page=page, page_size=page_size,
                                 items=[EvalCaseResponse.model_validate(c).model_dump() for c in items])


@router.post("/datasets/{dataset_id}/cases", response_model=EvalCaseResponse)
def create_case(dataset_id: int, data: EvalCaseCreate, request: Request,
                db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ds = db.query(EvalDataset).filter(EvalDataset.id == dataset_id).first()
    if not ds:
        raise HTTPException(404, "数据集不存在")
    item = EvalCase(dataset_id=dataset_id, eval_type=data.eval_type or ds.eval_type,
                    created_by=current_user.id, **data.model_dump(exclude={"dataset_id", "eval_type"}))
    db.add(item); db.commit(); db.refresh(item)
    ds.case_count = db.query(EvalCase).filter(EvalCase.dataset_id == dataset_id, EvalCase.status == "active").count()
    db.commit()
    return item


@router.put("/cases/{case_id}", response_model=EvalCaseResponse)
def update_case(case_id: int, data: EvalCaseUpdate, request: Request,
                db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.query(EvalCase).filter(EvalCase.id == case_id).first()
    if not item:
        raise HTTPException(404, "用例不存在")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(item, k, v)
    db.commit(); db.refresh(item)
    return item


@router.delete("/cases/{case_id}")
def delete_case(case_id: int, request: Request,
                db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.query(EvalCase).filter(EvalCase.id == case_id).first()
    if not item:
        raise HTTPException(404, "用例不存在")
    item.soft_delete()
    db.commit()
    return {"message": "已删除用例"}


@router.post("/datasets/import")
def import_cases(dataset_id: int = Body(...), cases: List[EvalCaseCreate] = Body(...),
                 db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """批量导入用例（Excel/JSON 前端解析后调用）"""
    ds = db.query(EvalDataset).filter(EvalDataset.id == dataset_id).first()
    if not ds:
        raise HTTPException(404, "数据集不存在")
    n = 0
    for c in cases:
        item = EvalCase(dataset_id=dataset_id, eval_type=c.eval_type or ds.eval_type,
                        created_by=current_user.id, **c.model_dump(exclude={"dataset_id", "eval_type"}))
        db.add(item); n += 1
    db.commit()
    ds.case_count = db.query(EvalCase).filter(EvalCase.dataset_id == dataset_id, EvalCase.status == "active").count()
    db.commit()
    return {"message": f"已导入 {n} 条用例", "count": n}


# ═══════════════════════════ 测评任务 ═══════════════════════════
@router.get("/tasks", response_model=List[EvalTaskResponse])
def list_tasks(status: Optional[str] = None, keyword: Optional[str] = None,
               db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    q = db.query(EvalTask)
    if status:
        q = q.filter(EvalTask.status == status)
    if keyword:
        q = q.filter(EvalTask.name.contains(keyword))
    return q.order_by(EvalTask.id.desc()).all()


@router.post("/tasks", response_model=EvalTaskResponse)
def create_task(data: EvalTaskCreate, request: Request,
                db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    target = db.query(EvalTarget).filter(EvalTarget.id == data.target_id).first()
    if not target:
        raise HTTPException(404, "被测对象不存在")
    item = EvalTask(created_by=current_user.id, status="ready", **data.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    _audit(db, current_user, request, "create", "eval_task", item.id, item.name)
    return item


@router.get("/tasks/{task_id}", response_model=EvalTaskResponse)
def get_task(task_id: int, db: Session = Depends(get_db),
             current_user: User = Depends(get_current_user)):
    item = db.query(EvalTask).filter(EvalTask.id == task_id).first()
    if not item:
        raise HTTPException(404, "测评任务不存在")
    return item


@router.get("/tasks/{task_id}/runs", response_model=List[EvalRunResponse])
def get_task_runs(task_id: int, db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    return db.query(EvalRun).filter(EvalRun.eval_task_id == task_id).order_by(EvalRun.id).all()


@router.post("/tasks/{task_id}/run")
def run_task(task_id: int, request: Request,
             db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """启动测评（提交 eval 队列 Celery，返回异步 agent_task_id）"""
    task = db.query(EvalTask).filter(EvalTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "测评任务不存在")
    if task.status in ("running", "completed"):
        raise HTTPException(400, f"任务当前状态 {task.status}，不允许重复启动")
    if not task.dataset_ids:
        raise HTTPException(400, "任务未配置数据集")
    task.status = "ready"
    db.commit()
    from app.core.tasks import dispatch_task
    from app.tasks.eval_tasks import run_eval_task as run_eval_task_fn
    use_celery, cid = dispatch_task(run_eval_task_fn, task_id)
    _audit(db, current_user, request, "run", "eval_task", task.id, task.name,
           detail={"celery": use_celery})
    return {"message": "测评已提交", "agent_task_id": cid, "use_celery": use_celery}


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: int, request: Request,
                db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = db.query(EvalTask).filter(EvalTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "测评任务不存在")
    if task.status == "running":
        task.status = "canceled"
        task.completed_at = __import__("app.core.timezone", fromlist=["china_now_naive"]).china_now_naive()
        db.query(EvalRun).filter(EvalRun.eval_task_id == task_id, EvalRun.status == "running").update(
            {"status": "failed"})
        db.commit()
    return {"message": "任务已取消"}


@router.get("/tasks/{task_id}/results")
def list_results(task_id: int, mode: Optional[str] = None,
                 status: Optional[str] = None, risk_level: Optional[str] = None, low_score: Optional[bool] = None,
                 page: int = Query(1), page_size: int = Query(20),
                 db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    q = db.query(EvalResult).filter(EvalResult.eval_task_id == task_id)
    if mode:
        q = q.join(EvalRun).filter(EvalRun.mode == mode)
    if status:
        q = q.filter(EvalResult.status == status)
    if risk_level:
        q = q.filter(EvalResult.risk_level == risk_level)
    if low_score:
        q = q.filter(EvalResult.score.isnot(None), EvalResult.score < 3.5)
    total = q.count()
    items = q.order_by(EvalResult.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PaginatedEvalResponse(total=total, page=page, page_size=page_size,
                                 items=[EvalResultResponse.model_validate(r).model_dump() for r in items])


@router.get("/results/{result_id}", response_model=EvalResultResponse)
def get_result(result_id: int, db: Session = Depends(get_db),
               current_user: User = Depends(get_current_user)):
    item = db.query(EvalResult).filter(EvalResult.id == result_id).first()
    if not item:
        raise HTTPException(404, "测评结果不存在")
    return item


@router.post("/results/{result_id}/manual-score", response_model=EvalResultResponse)
def manual_score(result_id: int, data: ManualScoreIn, request: Request,
                 db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.query(EvalResult).filter(EvalResult.id == result_id).first()
    if not item:
        raise HTTPException(404, "测评结果不存在")
    item.manual_score = data.manual_score
    item.manual_comment = data.manual_comment
    item.review_status = data.review_status
    db.commit(); db.refresh(item)
    _audit(db, current_user, request, "manual_score", "eval_result", item.id, "manual")
    return item


@router.get("/manual-queue")
def manual_queue(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """人工打分待复核样本队列（flagged/低分/高危）"""
    items = (db.query(EvalResult).join(EvalTask, EvalResult.eval_task_id == EvalTask.id)
             .filter(EvalResult.review_status == "pending")
             .filter(EvalResult.status.in_(["flagged", "failed", "blocked"]))
             .order_by(EvalResult.id.desc()).limit(100).all())
    return [EvalResultResponse.model_validate(r).model_dump() for r in items]


@router.post("/tasks/{task_id}/compare")
def compare_task(task_id: int, data: EvalCompareIn = Body(...),
                 db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """版本对比：与 compare_task_id 或同目标最近任务对比"""
    compare_task_id = data.compare_task_id
    task = db.query(EvalTask).filter(EvalTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "测评任务不存在")
    base = None
    if compare_task_id:
        base = db.query(EvalTask).filter(EvalTask.id == compare_task_id).first()
    else:
        base = (db.query(EvalTask).filter(
                                          EvalTask.target_id == task.target_id,
                                          EvalTask.id != task.id, EvalTask.status == "completed")
                .order_by(EvalTask.id.desc()).first())
    cur_summary = task.summary or {}
    base_summary = base.summary if base else None
    diff = {}
    for k in ("ai_judge", "business", "agent", "redteam"):
        c = cur_summary.get(k, {})
        b = (base_summary or {}).get(k, {})
        score_diff = None
        if isinstance(c, dict) and isinstance(b, dict) and c.get("score") is not None and b.get("score") is not None:
            score_diff = round(c["score"] - b["score"], 2)
        diff[k] = {"current": c, "base": b, "score_diff": score_diff}
    return {"current_task": task.id, "base_task": base.id if base else None,
            "current_summary": cur_summary, "base_summary": base_summary, "diff": diff}


# ═══════════════════════════ 报告 / 问题 / 基线 ═══════════════════════════
@router.post("/tasks/{task_id}/report")
def gen_report(task_id: int, data: EvalReportGenerateIn = Body(...), request: Request = None,
               db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.core.tasks import dispatch_task
    from app.tasks.eval_tasks import generate_eval_report as gen_fn
    use_celery, cid = dispatch_task(gen_fn, task_id, data.report_type)
    return {"message": "报告生成中", "agent_task_id": cid}


@router.get("/reports", response_model=List[EvalReportResponse])
def list_reports(task_id: Optional[int] = None, report_type: Optional[str] = None,
                 db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    q = db.query(EvalReport)
    if task_id:
        q = q.filter(EvalReport.eval_task_id == task_id)
    if report_type:
        q = q.filter(EvalReport.report_type == report_type)
    return q.order_by(EvalReport.id.desc()).all()


@router.get("/reports/{report_id}", response_model=EvalReportResponse)
def get_report(report_id: int, db: Session = Depends(get_db),
               current_user: User = Depends(get_current_user)):
    item = db.query(EvalReport).filter(EvalReport.id == report_id).first()
    if not item:
        raise HTTPException(404, "报告不存在")
    return item


@router.post("/issues")
def create_issue(data: EvalIssueCreate,
                 db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = EvalIssue(eval_task_id=data.eval_task_id or 0, **data.model_dump(exclude={"eval_task_id"}))
    db.add(item); db.commit(); db.refresh(item)
    return EvalIssueResponse.model_validate(item)


@router.get("/issues")
def list_issues(task_id: Optional[int] = None, issue_level: Optional[str] = None,
                status: Optional[str] = None, db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user)):
    q = db.query(EvalIssue)
    if task_id:
        q = q.filter(EvalIssue.eval_task_id == task_id)
    if issue_level:
        q = q.filter(EvalIssue.issue_level == issue_level)
    if status:
        q = q.filter(EvalIssue.status == status)
    return [EvalIssueResponse.model_validate(i).model_dump() for i in q.order_by(EvalIssue.id.desc()).all()]


@router.put("/issues/{issue_id}/status")
def update_issue_status(issue_id: int, data: EvalIssueStatusUpdate, request: Request,
                        db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.query(EvalIssue).filter(EvalIssue.id == issue_id).first()
    if not item:
        raise HTTPException(404, "问题不存在")
    item.status = data.status
    if data.retest_result is not None:
        item.retest_result = data.retest_result
    if data.owner_id is not None:
        item.owner_id = data.owner_id
    if data.fix_suggestion is not None:
        item.fix_suggestion = data.fix_suggestion
    if data.status in ("closed", "archived"):
        item.closed_at = __import__("app.core.timezone", fromlist=["china_now_naive"]).china_now_naive()
    db.commit(); db.refresh(item)
    return EvalIssueResponse.model_validate(item)


@router.get("/baselines")
def list_baselines(target_id: Optional[int] = None, db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    q = db.query(EvalBaseline)
    if target_id:
        q = q.filter(EvalBaseline.target_id == target_id)
    return [EvalBaselineResponse.model_validate(b).model_dump() for b in q.order_by(EvalBaseline.id.desc()).all()]


@router.post("/baselines")
def create_baseline(data: EvalBaselineCreate, request: Request,
                    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    metrics = None
    if data.eval_task_id:
        task = db.query(EvalTask).filter(EvalTask.id == data.eval_task_id).first()
        if task:
            metrics = task.summary
    item = EvalBaseline(created_by=current_user.id, metrics=metrics, **data.model_dump(exclude={"eval_task_id"}))
    if data.eval_task_id:
        item.eval_task_id = data.eval_task_id
    db.add(item); db.commit(); db.refresh(item)
    return EvalBaselineResponse.model_validate(item)


@router.delete("/baselines/{baseline_id}")
def delete_baseline(baseline_id: int, request: Request,
                    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.query(EvalBaseline).filter(EvalBaseline.id == baseline_id).first()
    if not item:
        raise HTTPException(404, "基线不存在")
    item.soft_delete()
    db.commit()
    return {"message": "已删除基线"}


# ═══════════════════════════ 红队专项 ═══════════════════════════
@router.post("/redteam/run")
def redteam_run(data: RedteamRunIn, request: Request,
                db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """红队专项执行：直接对数据集创建临时任务并启动"""
    ds = db.query(EvalDataset).filter(EvalDataset.id == data.dataset_id).first()
    if not ds:
        raise HTTPException(404, "数据集不存在")
    target_id = data.target_id
    if not target_id:
        target = db.query(EvalTarget).filter(
                                             EvalTarget.target_type.in_(["llm", "agent"])).first()
        if not target:
            raise HTTPException(400, "请先登记被测对象或指定 target_id")
        target_id = target.id
    task = EvalTask(name=f"红队专项 · {ds.name}", target_id=target_id,
                    modes={"redteam": {"datasets": [ds.id]}}, dataset_ids={"redteam": [ds.id]},
                    settings={"concurrency": data.concurrency}, backend="local",
                    created_by=current_user.id, status="ready")
    db.add(task); db.commit(); db.refresh(task)
    from app.core.tasks import dispatch_task
    from app.tasks.eval_tasks import run_eval_task as fn
    use_celery, cid = dispatch_task(fn, task.id)
    return {"message": "红队专项已启动", "task_id": task.id, "agent_task_id": cid}


@router.get("/redteam/logs")
def redteam_logs(risk_level: Optional[str] = None, page: int = Query(1),
                 page_size: int = Query(20), db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    """红队攻击日志（复用 eval_results 中 redteam 模式结果）"""
    q = (db.query(EvalResult).join(EvalTask, EvalResult.eval_task_id == EvalTask.id)
         .join(EvalRun, EvalResult.eval_run_id == EvalRun.id)
         .filter(EvalRun.mode == "redteam"))
    if risk_level:
        q = q.filter(EvalResult.risk_level == risk_level)
    total = q.count()
    items = q.order_by(EvalResult.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PaginatedEvalResponse(total=total, page=page, page_size=page_size,
                                 items=[EvalResultResponse.model_validate(r).model_dump() for r in items])


# ═══════════════════════════ 看板 ═══════════════════════════
@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """测评总览看板聚合数据（五维雷达/趋势/指标）"""
    tasks = db.query(EvalTask).order_by(EvalTask.id.desc()).limit(20).all()
    completed = [t for t in tasks if t.status == "completed"]
    # 最近一次完整任务作为雷达
    latest = completed[0] if completed else None
    radar = {"ai_judge": 0, "agent": 0, "business": 0, "redteam": 0, "manual": 0}
    if latest and latest.summary:
        for k, v in latest.summary.items():
            if k == "ai_judge":
                radar[k] = (v or {}).get("score") or 0
            elif k == "redteam":
                radar[k] = (v or {}).get("block_rate") or 0
            elif k in ("agent", "business"):
                radar[k] = ((v or {}).get("completion_rate") or (v or {}).get("success_rate") or 0)
    # 趋势
    trend = [{"id": t.id, "name": t.name, "status": t.status, "conclusion": t.conclusion,
              "created_at": str(t.created_at)} for t in tasks]
    status_count = {}
    for t in tasks:
        status_count[t.status] = status_count.get(t.status, 0) + 1
    p0_count = db.query(EvalResult).join(EvalTask).filter(
        EvalResult.risk_level == "P0").count()
    return {
        "radar": radar,
        "trend": trend,
        "status_count": status_count,
        "p0_count": p0_count,
        "total_tasks": len(tasks),
        "completed_tasks": len(completed),
    }


# ═══════════════════════════ SSE 实时进度（全局） ═══════════════════════════
@sse_router.get("/tasks/{task_id}/progress")
def sse_progress(task_id: int, token: str = Query(""), db: Session = Depends(get_db),
                 current_user: Optional[User] = Depends(get_current_user)):
    """SSE 实时进度流（整体 + 各模式）。鉴权：query token 或 JWT。"""
    task = db.query(EvalTask).filter(EvalTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "测评任务不存在")

    def gen():
        import time
        last_overall = -1
        while True:
            db2 = SessionLocal_factory()
            try:
                t = db2.query(EvalTask).filter(EvalTask.id == task_id).first()
                if not t:
                    break
                runs = db2.query(EvalRun).filter(EvalRun.eval_task_id == task_id).all()
                run_state = {r.mode: {"status": r.status, "progress": r.progress,
                                      "pass_rate": r.pass_rate, "score_avg": r.score_avg} for r in runs}
                payload = {"overall": t.progress, "status": t.status, "conclusion": t.conclusion,
                           "runs": run_state}
                yield f"event: progress\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                if t.status in ("completed", "failed", "canceled"):
                    yield f"event: done\ndata: {json.dumps({'status': t.status, 'conclusion': t.conclusion}, ensure_ascii=False)}\n\n"
                    break
            finally:
                db2.close()
            time.sleep(1.5)

    return StreamingResponse(gen(), media_type="text/event-stream")


def SessionLocal_factory():
    from app.database import SessionLocal
    return SessionLocal()


