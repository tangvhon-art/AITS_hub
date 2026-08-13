"""
Agent 任务监控 API + Supervisor 流水线 API
"""
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.agent_task import AgentTask
from app.models.project import Project
from app.agents.supervisor import SupervisorEngine
from app.agents.case_reviewer import CaseReviewerAgent
from app.agents.bdd_generator import BDDGeneratorAgent
from app.schemas.agent_task import (
    AgentTaskResponse,
    AgentTaskListResponse,
    SupervisorRunRequest,
    ReviewRequest,
    BDDGenerateRequest,
)

# 全局任务监控路由
router = APIRouter(prefix="/api/agent-tasks", tags=["Agent任务"])

# 项目级操作路由
project_router = APIRouter(prefix="/api/projects/{project_id}", tags=["Agent任务"])


def _check_project_access(db: Session, user: User, project_id: int):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not user.is_admin and project.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权限访问该项目")
    return project


# ========== Agent 任务监控 ==========

@router.get("", response_model=AgentTaskListResponse)
def list_agent_tasks(
    project_id: Optional[int] = None,
    agent_type: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取 Agent 任务列表"""
    query = db.query(AgentTask)

    if project_id:
        _check_project_access(db, current_user, project_id)
        query = query.filter(AgentTask.project_id == project_id)
    elif not current_user.is_admin:
        # 普通用户只能看自己创建的任务
        query = query.filter(AgentTask.created_by == current_user.id)

    if agent_type:
        query = query.filter(AgentTask.agent_type == agent_type)
    if status:
        query = query.filter(AgentTask.status == status)

    total = query.count()
    tasks = query.order_by(AgentTask.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return AgentTaskListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[AgentTaskResponse.model_validate(t) for t in tasks],
    )


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
        _check_project_access(db, current_user, task.project_id)
    elif not current_user.is_admin and task.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问")

    return AgentTaskResponse.model_validate(task)


# ========== Supervisor 流水线 ==========

@project_router.post("/supervisor/run")
def run_supervisor_pipeline(
    project_id: int,
    req: SupervisorRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """运行 Supervisor 完整流水线"""
    _check_project_access(db, current_user, project_id)

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
        task.completed_at = datetime.now()
        db.commit()

        return {"task_id": task.id, "status": "success", "result": result}

    except Exception as e:
        task.status = "failed"
        task.error_message = str(e)
        task.completed_at = datetime.now()
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
    """评审测试用例"""
    _check_project_access(db, current_user, project_id)

    # 创建任务记录
    task = AgentTask(
        project_id=project_id,
        agent_type="case_reviewer",
        status="running",
        input_params={"case_count": len(req.cases)},
        created_by=current_user.id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    try:
        reviewer = CaseReviewerAgent(db, llm_config_id=req.llm_config_id, task_id=task.id)
        result = reviewer.review(req.cases, requirement=req.requirement)

        task.status = "success"
        task.output_result = result
        task.token_usage = result.get("token_usage", {})
        task.llm_config_id = result.get("llm_config_id")
        task.completed_at = datetime.now()
        db.commit()

        return {"task_id": task.id, "result": result}

    except Exception as e:
        task.status = "failed"
        task.error_message = str(e)
        task.completed_at = datetime.now()
        db.commit()
        raise HTTPException(status_code=500, detail=f"评审失败: {str(e)}")


# ========== BDD 用例生成 ==========

@project_router.post("/cases/bdd-generate")
def generate_bdd_cases(
    project_id: int,
    req: BDDGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """生成 BDD Gherkin 用例"""
    _check_project_access(db, current_user, project_id)

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
        task.completed_at = datetime.now()
        db.commit()

        return {"task_id": task.id, "result": result}

    except Exception as e:
        task.status = "failed"
        task.error_message = str(e)
        task.completed_at = datetime.now()
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
    _check_project_access(db, current_user, project_id)

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
