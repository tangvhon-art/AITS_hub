"""
工作流执行编排（workflow 后端路径）

职责：
- 生成 uuid 并写入 AgentTask
- 按模块构造统一 input 契约（见需求文档 5.0）
- 调用 WorkflowConnector.invoke 异步受理
- 保存 external_task_id，任务保持 running（等待回调），Celery 任务结束（不阻塞）
- 调用/受理失败抛 WorkflowInvokeError，由调用方决定降级 local（v0.7 确认 #6）

回调到达后由 handle_workflow_callback_task 取 content 走 finalize_* 写库。
"""
import logging
import secrets
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from app.models.agent_task import AgentTask
from app.models.project import Project
from app.models.requirement import TestRequirement, RequirementFeature
from app.services.workflow_config_service import (
    get_module_config, get_webhook_config,
)
from app.services.workflow_connector import invoke as connector_invoke, WorkflowInvokeError
from app.services.workflow_call_logger import log_call
from app.core.timezone import china_now_naive
import json

logger = logging.getLogger(__name__)


def generate_uuid(task_id: int) -> str:
    """生成全局唯一回调定位 ID：wf_{task_id}_{random}"""
    return f"wf_{task_id}_{secrets.token_hex(8)}"


def _project_name(db: Session, project_id: Optional[int]) -> str:
    if not project_id:
        return ""
    p = db.query(Project).filter(Project.id == project_id).first()
    return p.name if p else ""


def _build_input(db: Session, task: AgentTask, module_id: str) -> Dict[str, Any]:
    """按模块构造统一 input 契约（AITS 业务信息载体）"""
    params = task.input_params or {}
    project_id = task.project_id
    project_name = _project_name(db, project_id)
    base = {
        "project_id": project_id,
        "project_name": project_name,
        "llm_config_id": task.llm_config_id,
    }

    if module_id == "requirement.generate":
        base.update({
            "task_type": "requirement_generate",
            "description": params.get("description", ""),
            "version_id": params.get("version_id"),
            "prompt_id": params.get("prompt_id"),
        })
        return base

    if module_id == "requirement.split_features":
        req_id = params.get("requirement_id")
        title, content = "", ""
        if req_id:
            r = db.query(TestRequirement).filter(TestRequirement.id == req_id).first()
            if r:
                title, content = r.title or "", r.content or ""
        base.update({
            "task_type": "feature_split",
            "requirement_id": req_id,
            "requirement_title": title or params.get("requirement_title", ""),
            "requirement_content": content or params.get("requirement_content", ""),
        })
        return base

    if module_id == "case.generate":
        req_id = params.get("requirement_id")
        title, content = "", ""
        feature_ids = params.get("feature_ids") or []
        if req_id:
            r = db.query(TestRequirement).filter(TestRequirement.id == req_id).first()
            if r:
                title, content = r.title or "", r.content or ""
        features = []
        if feature_ids and req_id:
            feats = db.query(RequirementFeature).filter(
                RequirementFeature.id.in_(feature_ids),
                RequirementFeature.requirement_id == req_id,
                RequirementFeature.is_deleted == False,  # noqa: E712
            ).all()
            for f in feats:
                try:
                    methods = json.loads(f.design_methods) if f.design_methods else []
                except (json.JSONDecodeError, TypeError):
                    methods = []
                features.append({
                    "id": f.id, "module_name": f.module_name, "name": f.name,
                    "description": f.description, "priority": f.priority,
                    "design_methods": methods, "preconditions": f.preconditions,
                })
        # 已有用例标题（避免重复）
        existing_titles = params.get("existing_case_titles") or []
        if req_id and not existing_titles:
            from app.models.test_case import TestCase
            existing_titles = [
                t[0] for t in db.query(TestCase.title).filter(
                    TestCase.project_id == project_id,
                    TestCase.req_id == req_id,
                    TestCase.is_deleted == False,  # noqa: E712
                ).limit(50).all()
            ]
        base.update({
            "task_type": "case_generate",
            "requirement_id": req_id,
            "requirement_title": title or params.get("requirement_title", ""),
            "requirement_content": content or params.get("content", ""),
            "features": features,
            "existing_case_titles": existing_titles,
            "count": params.get("count", 10),
            "prompt_id": params.get("prompt_id"),
        })
        return base

    if module_id == "case.review":
        base.update({
            "task_type": "case_review",
            "requirement_id": params.get("requirement_id"),
            "cases": params.get("cases", []),
            "requirements": params.get("requirements", []),
            "groups": params.get("groups", []),
            "prompt_id": params.get("prompt_id"),
        })
        return base

    # 兜底
    base["task_type"] = module_id
    base.update(params)
    return base


def run(db: Session, task: AgentTask, module_id: str) -> None:
    """发起 workflow 调用并挂起等待回调

    成功受理：写入 uuid + external_task_id，任务保持 running，返回（Celery 任务结束）。
    失败：抛 WorkflowInvokeError，由调用方降级 local。
    """
    cfg = get_module_config(db, module_id, task.project_id)
    if not cfg or not cfg.connector_id or not cfg.external_agent_id:
        raise WorkflowInvokeError(f"模块 {module_id} 未配置工作流连接/agent")

    from app.models.workflow import WorkflowPlatformConnector
    connector = db.query(WorkflowPlatformConnector).filter(
        WorkflowPlatformConnector.id == cfg.connector_id,
        WorkflowPlatformConnector.is_deleted == False,  # noqa: E712
    ).first()
    if not connector or connector.status != "active":
        raise WorkflowInvokeError(f"连接 {cfg.connector_id} 不可用")

    webhook = get_webhook_config(db)
    callback_url = webhook.webhook_url

    # 生成 uuid 并落库
    uuid = generate_uuid(task.id)
    task.uuid = uuid
    task.backend = "workflow"
    db.commit()

    input_payload = _build_input(db, task, module_id)

    # 记录 invoke 日志
    log_call(
        db, agent_task_id=task.id, module_id=module_id, uuid=uuid,
        connector_id=connector.id, phase="invoke", status="success",
        request_json={"input": input_payload, "callback_url": callback_url},
    )

    import time
    start = time.time()
    try:
        result = connector_invoke(connector, uuid, input_payload, callback_url)
    except WorkflowInvokeError as e:
        cost = int((time.time() - start) * 1000)
        log_call(
            db, agent_task_id=task.id, module_id=module_id, uuid=uuid,
            connector_id=connector.id, phase="invoke", status="failed",
            cost_ms=cost, error_msg=str(e),
        )
        raise

    cost = int((time.time() - start) * 1000)
    task.external_task_id = result["task_id"]
    task.status = "running"  # 等待回调
    db.commit()

    log_call(
        db, agent_task_id=task.id, module_id=module_id, uuid=uuid,
        connector_id=connector.id, phase="accept", status="success",
        response_json=result.get("raw"), external_task_id=result["task_id"],
        cost_ms=cost,
    )
    logger.info(
        f"[workflow] 外部受理成功: task_id={task.id}, uuid={uuid}, "
        f"external_task_id={result['task_id']}，等待回调"
    )
    # 受理成功：任务挂起，由 Webhook 回调接续
    return None
