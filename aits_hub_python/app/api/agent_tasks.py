"""
Agent 任务监控 API + Supervisor 流水线 API
"""
import json
import logging
import time
from datetime import datetime
from app.core.timezone import china_now_naive
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Worker 在线探测缓存（inspect 广播拥塞防护）
_workers_probe_cache = None
_workers_probe_at = 0.0

from app.database import get_db
from app.core.deps import get_current_user, get_project
from app.models.user import User
from app.models.agent_task import AgentTask
from app.models.project import Project
from app.agents.supervisor import SupervisorEngine
from app.agents.bdd_generator import BDDGeneratorAgent
from app.schemas.agent_task import (
    AgentTaskResponse,
    AgentTaskListResponse,
    SupervisorRunRequest,
    ReviewRequest,
    ReviewOptimizeRequest,
    BDDGenerateRequest,
)

# 全局任务监控路由
router = APIRouter(prefix="/api/agent-tasks", tags=["Agent任务"])

# 项目级操作路由
project_router = APIRouter(prefix="/api/projects/{project_id}", tags=["Agent任务"])

@router.post("/search", response_model=AgentTaskListResponse)
def list_agent_tasks(
    project_id: Optional[int] = Body(None),
    agent_type: Optional[str] = Body(None),
    status: Optional[str] = Body(None),
    backend: Optional[str] = Body(None),
    page: int = Body(1),
    page_size: int = Body(20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 Agent 任务列表（支持按 backend 筛选）"""
    query = db.query(AgentTask)

    if project_id:
        get_project(project_id, db, current_user)
        query = query.filter(AgentTask.project_id == project_id)
    elif not current_user.is_admin:
        # 普通用户只能看自己创建的任务
        query = query.filter(AgentTask.created_by == current_user.id)

    if agent_type:
        query = query.filter(AgentTask.agent_type == agent_type)
    if status:
        query = query.filter(AgentTask.status == status)
    if backend:
        query = query.filter(AgentTask.backend == backend)

    total = query.count()
    tasks = query.order_by(AgentTask.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return AgentTaskListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[AgentTaskResponse.model_validate(t) for t in tasks],
    )

@router.get("/monitor")
def agent_task_monitor(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    任务监控汇总：Agent 任务状态统计 + Redis 队列积压 + 最近任务列表 + 各队列(Worker)负载统计。
    （任务状态以 DB agent_tasks 为准，不依赖 Celery 事件流/Flower，保证“执行中”等状态准确可读）
    """
    from sqlalchemy import func
    # 状态分布
    rows = db.query(AgentTask.status, func.count()).group_by(AgentTask.status).all()
    status_counts = {s: c for s, c in rows}
    # 队列积压（Redis LLEN）
    queues = {}
    try:
        import redis as redis_lib
        from app.config import settings
        rc = redis_lib.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        for q in ("default", "ai", "execution", "eval"):
            try:
                queues[q] = rc.llen(q)
            except Exception:
                queues[q] = 0
    except Exception:
        queues = {"default": 0, "ai": 0, "execution": 0, "eval": 0}
    # 最近任务（含执行中/排队中的最新一批，供监控列表展示）
    recent = db.query(AgentTask).order_by(AgentTask.created_at.desc()).limit(50).all()
    # ---- 按队列(Worker)聚合负载统计 ----
    # agent_type -> 队列映射（与 celery_app.py 任务队列划分对齐）
    AGENT_TYPE_QUEUE = {
        # ai 队列（AI 生成类）
        "case_generator": "ai", "case_reviewer": "ai", "case_optimizer": "ai",
        "requirement_generator": "ai", "api_case_generator": "ai", "api_doc_generator": "ai",
        "knowledge_processor": "ai", "report_generator": "ai", "script_generator": "ai",
        "script_fixer": "ai", "defect_analyzer": "ai", "bdd_generator": "ai",
        # execution 队列（执行类）
        "ui_execution": "execution", "performance_test": "execution",
        "script_execution": "execution", "test_plan_execution": "execution",
        # default 队列（后台轻量）
        "supervisor": "default", "notification": "default",
    }
    # 按 agent_type/status 聚合 AgentTask
    at_rows = db.query(AgentTask.agent_type, AgentTask.status, func.count()).group_by(AgentTask.agent_type, AgentTask.status).all()
    queue_active = {q: 0 for q in queues}
    queue_processed = {q: 0 for q in queues}
    for atype, st, cnt in at_rows:
        q = AGENT_TYPE_QUEUE.get(atype, "default")
        queue_processed[q] += cnt
        if st == "running":
            queue_active[q] += cnt
    # eval 队列：AI 测评任务记录在 eval_tasks 表
    try:
        from app.models.eval import EvalTask
        et_rows = db.query(EvalTask.status, func.count()).group_by(EvalTask.status).all()
        eval_total = sum(c for _, c in et_rows)
        eval_running = sum(c for st, c in et_rows if st == "running")
        queue_processed["eval"] += eval_total
        queue_active["eval"] += eval_running
    except Exception:
        pass
    queue_stats = {
        q: {"queued": queues[q], "active": queue_active[q], "processed": queue_processed[q]}
        for q in queues
    }
    # ---- Worker 在线探测（用 control inspect，不依赖失效的 Celery 事件流）----
    # inspect 是控制广播，并发/高频调用会拥塞导致请求挂起，故加 TTL 缓存串行化
    global _workers_probe_cache, _workers_probe_at
    now = time.time()
    if _workers_probe_cache is not None and now - _workers_probe_at < 8:
        workers = _workers_probe_cache
    else:
        workers = {}
        try:
            from app.celery_app import celery_app
            insp = celery_app.control.inspect(timeout=2)
            pings = insp.ping() or {}
            stats = insp.stats() or {}
            active_queues = insp.active_queues() or {}
            for name in pings:
                st = stats.get(name) or {}
                aq = active_queues.get(name) or []
                workers[name] = {
                    "queue": [q.get("name") for q in aq if q.get("name")],
                    "pid": st.get("pid"),
                    "concurrency": (st.get("pool") or {}).get("max-concurrency"),
                }
        except Exception as e:
            logger.warning(f"Worker 在线探测失败: {e}")
            workers = {}
        _workers_probe_cache = workers
        _workers_probe_at = now
    return {
        "running": status_counts.get("running", 0),
        "pending": status_counts.get("pending", 0),
        "success": status_counts.get("success", 0),
        "failed": status_counts.get("failed", 0),
        "canceled": status_counts.get("canceled", 0),
        "queues": queues,
        "queue_stats": queue_stats,
        "workers": workers,
        "recent": [AgentTaskResponse.model_validate(t) for t in recent],
    }

@router.get("/{task_id}", response_model=AgentTaskResponse)
def get_agent_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 Agent 任务详情"""
    task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.project_id:
        get_project(task.project_id, db, current_user)
    elif not current_user.is_admin and task.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问")

    return AgentTaskResponse.model_validate(task)


@router.post("/{task_id}/cancel")
def cancel_agent_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """手动取消 Agent 任务（pending/running → canceled）"""
    task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.project_id:
        get_project(task.project_id, db, current_user)
    elif not current_user.is_admin and task.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问")

    if task.status in ("success", "failed", "canceled"):
        raise HTTPException(status_code=400, detail=f"任务已结束（当前状态: {task.status}），无需取消")

    task.status = "canceled"
    task.completed_at = china_now_naive()
    base = task.error_message or ""
    suffix = "用户手动取消"
    task.error_message = (f"{base} | {suffix}") if base else suffix
    db.commit()
    return {"message": "任务已取消", "task_id": task.id}

# ========== Supervisor 流水线 ==========

@project_router.post("/supervisor/run")
def run_supervisor_pipeline(
    project_id: int,
    req: SupervisorRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """运行 Supervisor 完整流水线"""
    get_project(project_id, db, current_user)

    # 创建任务记录
    task = AgentTask(
        project_id=project_id,
        agent_type="supervisor",
        status="running",
        input_params={
            "requirement_content": req.requirement_content,
            "requirement_title": req.requirement_title,
            "generate_count": req.generate_count,
        },
        created_by=current_user.id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    try:
        engine = SupervisorEngine(db)
        result = engine.run_full_pipeline(
            project_id=project_id,
            requirement_content=req.requirement_content,
            requirement_title=req.requirement_title,
            generate_count=req.generate_count,
            target_url=req.target_url,
            llm_config_id=req.llm_config_id,
            created_by=current_user.id,
            auto_execute=req.auto_execute,
            notification_config=req.notification_config,
        )

        task.status = "success"
        task.output_result = result
        task.completed_at = china_now_naive()
        db.commit()

        return {"task_id": task.id, "status": "success", "result": result}

    except Exception as e:
        task.status = "failed"
        task.error_message = str(e)
        task.completed_at = china_now_naive()
        db.commit()
        raise HTTPException(status_code=500, detail=f"流水线执行失败: {str(e)}")

# ========== 用例评审 ==========

@project_router.post("/cases/review")
def review_cases(
    project_id: int,
    req: ReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """评审测试用例（异步），支持多选需求和模块"""
    get_project(project_id, db, current_user)

    from app.models.test_case import TestCase
    from app.models.requirement import TestRequirement

    # 合并单选和多选参数
    requirement_ids = list(req.requirement_ids or [])
    if req.requirement_id and req.requirement_id not in requirement_ids:
        requirement_ids.append(req.requirement_id)
    modules = list(req.modules or [])
    if req.module and req.module not in modules:
        modules.append(req.module)

    # 如果前端未传 cases，则根据需求和模块从数据库查询
    cases = req.cases or []
    if not cases:
        query = db.query(TestCase).filter(
            TestCase.project_id == project_id,
            TestCase.is_deleted == False,
        )
        if requirement_ids:
            query = query.filter(TestCase.req_id.in_(requirement_ids))
        if modules:
            query = query.filter(TestCase.module.in_(modules))
        cases_db = query.order_by(TestCase.module, TestCase.id).all()

        # 一次性查询所有相关功能点，构建 feature_id -> {module_name, name} 映射
        from app.models.requirement import RequirementFeature
        feature_ids = {c.feature_id for c in cases_db if c.feature_id}
        feature_map = {}
        if feature_ids:
            feats = db.query(RequirementFeature).filter(
                RequirementFeature.id.in_(feature_ids),
                RequirementFeature.is_deleted == False,
            ).all()
            feature_map = {f.id: {"module_name": f.module_name, "name": f.name} for f in feats}

        cases = []
        for c in cases_db:
            try:
                steps = json.loads(c.steps) if c.steps else []
            except (json.JSONDecodeError, TypeError):
                steps = []
            feat = feature_map.get(c.feature_id) if c.feature_id else None
            cases.append({
                "id": c.id,
                "title": c.title,
                "module": c.module or "",
                "case_type": c.case_type or "functional",
                "priority": c.priority or "",
                "preconditions": c.preconditions or "",
                "steps": steps,
                "expected_result": c.expected_result or "",
                "req_id": c.req_id,
                "feature_id": c.feature_id,
                "feature_name": feat["name"] if feat else "",
                "feature_module": feat["module_name"] if feat else "",
            })

    # 查询选中的需求详情
    requirements_data = []
    if requirement_ids:
        reqs = db.query(TestRequirement).filter(
            TestRequirement.id.in_(requirement_ids),
            TestRequirement.project_id == project_id,
            TestRequirement.is_deleted == False,
        ).all()
        for r in reqs:
            requirements_data.append({
                "id": r.id,
                "title": r.title,
                "content": r.content or "",
            })

    # 按需求+模块分组统计
    groups = {}
    for c in cases:
        key = f"{c.get('req_id', '无需求')}||{c.get('module', '未分类')}"
        if key not in groups:
            req_title = next((r["title"] for r in requirements_data if r["id"] == c.get("req_id")), "无需求")
            groups[key] = {
                "requirement_id": c.get("req_id"),
                "requirement_title": req_title,
                "module": c.get("module", "未分类"),
                "case_count": 0,
            }
        groups[key]["case_count"] += 1

    if not cases:
        raise HTTPException(status_code=400, detail="未找到符合条件的测试用例，请选择需求或模块")

    # 创建任务记录
    task = AgentTask(
        project_id=project_id,
        agent_type="case_reviewer",
        status="pending",
        input_params={
            "cases": cases,
            "case_count": len(cases),
            "requirements": requirements_data,
            "requirement_ids": requirement_ids,
            "modules": modules,
            "groups": list(groups.values()),
            "prompt_id": req.prompt_id,
            # 单需求/单模块时写入单数字段，供评审优化任务直接关联补充用例
            "requirement_id": requirement_ids[0] if len(requirement_ids or []) == 1 else None,
            "module": modules[0] if len(modules or []) == 1 else None,
            "page_backend": req.backend,
        },
        created_by=current_user.id,
        llm_config_id=req.llm_config_id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # 异步派发
    from app.core.tasks import dispatch_task
    from app.tasks.review_tasks import review_cases_task
    dispatch_task(review_cases_task, task.id)

    return {"task_id": task.id, "status": "pending", "message": "评审任务已提交", "case_count": len(cases)}


@project_router.post("/case-reviews/search")
def list_case_reviews(
    project_id: int,
    page: int = Body(1),
    page_size: int = Body(20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取用例评审历史列表"""
    get_project(project_id, db, current_user)

    query = db.query(AgentTask).filter(
        AgentTask.project_id == project_id,
        AgentTask.agent_type == "case_reviewer",
    ).order_by(AgentTask.created_at.desc())

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": t.id,
                "status": t.status,
                "input_params": t.input_params or {},
                "output_result": t.output_result or {},
                "llm_config_id": t.llm_config_id,
                "token_usage": t.token_usage or {},
                "error_message": t.error_message,
                "created_by": t.created_by,
                "created_at": t.created_at,
                "completed_at": t.completed_at,
            }
            for t in items
        ],
    }


@project_router.get("/case-reviews/{task_id}")
def get_case_review_detail(
    project_id: int,
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取用例评审详情"""
    get_project(project_id, db, current_user)

    task = db.query(AgentTask).filter(
        AgentTask.id == task_id,
        AgentTask.project_id == project_id,
        AgentTask.agent_type == "case_reviewer",
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="评审记录不存在")

    return {
        "id": task.id,
        "status": task.status,
        "input_params": task.input_params or {},
        "output_result": task.output_result or {},
        "llm_config_id": task.llm_config_id,
        "token_usage": task.token_usage or {},
        "error_message": task.error_message,
        "created_by": task.created_by,
        "created_at": task.created_at,
        "completed_at": task.completed_at,
    }


@project_router.post("/case-reviews/{task_id}/optimize")
def optimize_cases_from_review(
    project_id: int,
    task_id: int,
    req: ReviewOptimizeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """基于评审报告的问题列表和改进建议，优化/补充测试用例（异步）"""
    get_project(project_id, db, current_user)

    # 校验评审任务存在且已完成
    review_task = db.query(AgentTask).filter(
        AgentTask.id == task_id,
        AgentTask.project_id == project_id,
        AgentTask.agent_type == "case_reviewer",
    ).first()
    if not review_task:
        raise HTTPException(status_code=404, detail="评审记录不存在")
    if review_task.status != "success":
        raise HTTPException(status_code=400, detail="评审尚未完成，无法优化用例")

    # 创建优化任务
    opt_task = AgentTask(
        project_id=project_id,
        agent_type="case_optimizer",
        status="pending",
        input_params={
            "review_task_id": task_id,
            "optimize_mode": req.optimize_mode,
            "prompt_id": req.prompt_id,
            "system_prompt": req.system_prompt,
        },
        created_by=current_user.id,
        llm_config_id=req.llm_config_id,
    )
    db.add(opt_task)
    db.commit()
    db.refresh(opt_task)

    # 异步派发
    try:
        from app.tasks.review_tasks import optimize_cases_from_review_task
        optimize_cases_from_review_task.delay(task_id, opt_task.id)
    except Exception:
        logger.warning("Celery 不可用，使用后台线程回退")
        import threading
        from app.tasks.review_tasks import optimize_cases_from_review_task

        def _run():
            optimize_cases_from_review_task(task_id, opt_task.id)
        threading.Thread(target=_run, daemon=True).start()

    return {
        "task_id": opt_task.id,
        "review_task_id": task_id,
        "status": "pending",
        "message": "优化任务已提交，正在异步处理中",
    }


# ========== BDD 用例生成 ==========

@project_router.post("/cases/bdd-generate")
def generate_bdd_cases(
    project_id: int,
    req: BDDGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """生成 BDD Gherkin 用例"""
    get_project(project_id, db, current_user)

    task = AgentTask(
        project_id=project_id,
        agent_type="bdd_generator",
        status="running",
        input_params={"feature_name": req.feature_name},
        created_by=current_user.id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    try:
        generator = BDDGeneratorAgent(db, llm_config_id=req.llm_config_id, task_id=task.id)
        result = generator.generate(
            requirement=req.requirement,
            test_cases=req.cases,
            feature_name=req.feature_name,
        )

        task.status = "success"
        task.output_result = {"bdd_content": result.get("bdd_content"), "scenario_count": result.get("scenario_count")}
        task.token_usage = result.get("token_usage", {})
        task.llm_config_id = result.get("llm_config_id")
        task.completed_at = china_now_naive()
        db.commit()

        return {"task_id": task.id, "result": result}

    except Exception as e:
        task.status = "failed"
        task.error_message = str(e)
        task.completed_at = china_now_naive()
        db.commit()
        raise HTTPException(status_code=500, detail=f"BDD 生成失败: {str(e)}")

# ========== Token 消耗统计 ==========

@project_router.get("/token-usage")
def get_token_usage(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 Token 消耗统计"""
    get_project(project_id, db, current_user)

    tasks = db.query(AgentTask).filter(
        AgentTask.project_id == project_id,
        AgentTask.token_usage.isnot(None),
    ).all()

    total_prompt = 0
    total_completion = 0
    total_tokens = 0
    by_agent_type: Dict[str, Dict[str, int]] = {}

    for task in tasks:
        usage = task.token_usage or {}
        prompt = usage.get("prompt_tokens", 0) or 0
        completion = usage.get("completion_tokens", 0) or 0
        total = usage.get("total_tokens", 0) or (prompt + completion)

        total_prompt += prompt
        total_completion += completion
        total_tokens += total

        if task.agent_type not in by_agent_type:
            by_agent_type[task.agent_type] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "task_count": 0}
        by_agent_type[task.agent_type]["prompt_tokens"] += prompt
        by_agent_type[task.agent_type]["completion_tokens"] += completion
        by_agent_type[task.agent_type]["total_tokens"] += total
        by_agent_type[task.agent_type]["task_count"] += 1

    # 估算成本（按 DeepSeek 价格：输入 $0.001/1K tokens，输出 $0.002/1K tokens）
    estimated_cost = (total_prompt / 1000 * 0.001) + (total_completion / 1000 * 0.002)

    return {
        "project_id": project_id,
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_completion,
        "total_tokens": total_tokens,
        "estimated_cost_usd": round(estimated_cost, 4),
        "by_agent_type": by_agent_type,
        "total_tasks": len(tasks),
    }
