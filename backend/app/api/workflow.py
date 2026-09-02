"""
外部工作流平台接入 — 配置管理 API

包含：平台连接 CRUD、固定 Webhook 全局配置、模块执行后端配置、input 字段映射、调用回调日志查询。
全部为管理员鉴权（系统级配置）。固定 Webhook 回调端点见 app/api/workflow_webhook.py。
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.core.deps import get_current_user, require_admin, get_project
from app.core.audit import log_audit
from app.models.user import User
from app.models.project import Project
from app.services import workflow_config_service as svc
from app.schemas.workflow import (
    WorkflowConnectorCreate, WorkflowConnectorUpdate, WorkflowConnectorResponse,
    WorkflowWebhookConfigUpdate, WorkflowWebhookConfigResponse,
    AgentBackendConfigCreate, AgentBackendConfigUpdate, AgentBackendConfigResponse,
    WorkflowInputMappingCreate, WorkflowInputMappingUpdate, WorkflowInputMappingResponse,
    WorkflowCallLogResponse,
)

router = APIRouter(
    prefix="/api/workflow",
    tags=["agent配置"],
    dependencies=[Depends(require_admin)],
)

ALLOWED_PLATFORM_TYPES = ("openai_compat", "coze", "dify", "n8n", "custom")
ALLOWED_BACKENDS = ("local", "workflow")



# ══════════════════════════════════════════════════════════
# 平台连接
# ══════════════════════════════════════════════════════════

@router.post("/connectors/list")
def list_connectors(db: Session = Depends(get_db)):
    """平台连接列表"""
    items = svc.list_connectors(db)
    return {"items": [svc.connector_to_response(i) for i in items], "total": len(items)}


@router.post("/connectors")
def create_connector(
    data: WorkflowConnectorCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """新建平台连接（凭证加密存储）"""
    if data.platform_type not in ALLOWED_PLATFORM_TYPES:
        raise HTTPException(400, f"平台类型必须为: {', '.join(ALLOWED_PLATFORM_TYPES)}")
    item = svc.create_connector(db, data.model_dump())
    log_audit(
        db, action="create", resource_type="workflow_connector",
        resource_id=item.id, resource_name=item.name, user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"platform_type": item.platform_type, "base_url": item.base_url},
    )
    db.commit()
    return svc.connector_to_response(item)


@router.put("/connectors/{connector_id}")
def update_connector(
    connector_id: int,
    data: WorkflowConnectorUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新平台连接"""
    if data.platform_type is not None and data.platform_type not in ALLOWED_PLATFORM_TYPES:
        raise HTTPException(400, f"平台类型必须为: {', '.join(ALLOWED_PLATFORM_TYPES)}")
    before_name = svc.get_connector(db, connector_id).name
    item = svc.update_connector(db, connector_id, data.model_dump(exclude_unset=True))
    log_audit(
        db, action="update", resource_type="workflow_connector",
        resource_id=item.id, resource_name=item.name, user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"before_name": before_name},
    )
    db.commit()
    return svc.connector_to_response(item)


@router.delete("/connectors/{connector_id}")
def delete_connector(
    connector_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除平台连接（软删除）"""
    item = svc.get_connector(db, connector_id)
    item_name = item.name
    item.soft_delete()
    log_audit(
        db, action="delete", resource_type="workflow_connector",
        resource_id=item.id, resource_name=item_name, user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return {"message": "已删除"}


@router.get("/connectors/{connector_id}")
def get_connector(connector_id: int, db: Session = Depends(get_db)):
    """平台连接详情"""
    return svc.connector_to_response(svc.get_connector(db, connector_id))


# ══════════════════════════════════════════════════════════
# 固定 Webhook 全局配置
# ══════════════════════════════════════════════════════════

@router.get("/webhook-config")
def get_webhook_config(db: Session = Depends(get_db)):
    """读取 Webhook 全局配置（单行）"""
    return svc.webhook_config_to_response(svc.get_webhook_config(db))


@router.put("/webhook-config")
def update_webhook_config(
    data: WorkflowWebhookConfigUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新 Webhook 全局配置（含 secret 生成/重置）"""
    item = svc.update_webhook_config(db, data.model_dump(exclude_unset=True))
    log_audit(
        db, action="update", resource_type="workflow_webhook",
        resource_id=item.id, resource_name="webhook_config", user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"enabled": item.enabled, "regenerate_secret": data.regenerate_secret},
    )
    db.commit()
    return svc.webhook_config_to_response(item)


# ══════════════════════════════════════════════════════════
# 模块执行后端配置
# ══════════════════════════════════════════════════════════

@router.post("/module-configs/list")
def list_module_configs(db: Session = Depends(get_db)):
    """模块执行后端配置列表"""
    items = svc.list_module_configs(db)
    return {"items": [svc.module_config_to_response(i) for i in items], "total": len(items)}


@router.post("/module-configs")
def upsert_module_config(
    data: AgentBackendConfigCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建/更新模块执行后端配置（按 module_id + project_id 唯一）"""
    if data.default_backend not in ALLOWED_BACKENDS:
        raise HTTPException(400, f"执行后端必须为: {', '.join(ALLOWED_BACKENDS)}")
    item = svc.upsert_module_config(db, data.model_dump())
    log_audit(
        db, action="update", resource_type="workflow_module_config",
        resource_id=item.id, resource_name=item.module_id, user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"default_backend": item.default_backend, "project_id": item.project_id},
    )
    db.commit()
    return svc.module_config_to_response(item)


@router.put("/module-configs/{config_id}")
def update_module_config(
    config_id: int,
    data: AgentBackendConfigUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新模块执行后端配置"""
    if data.default_backend is not None and data.default_backend not in ALLOWED_BACKENDS:
        raise HTTPException(400, f"执行后端必须为: {', '.join(ALLOWED_BACKENDS)}")
    item = svc.update_module_config(db, config_id, data.model_dump(exclude_unset=True))
    log_audit(
        db, action="update", resource_type="workflow_module_config",
        resource_id=item.id, resource_name=item.module_id, user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"default_backend": item.default_backend},
    )
    db.commit()
    return svc.module_config_to_response(item)


@router.delete("/module-configs/{config_id}")
def delete_module_config(
    config_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除模块执行后端配置"""
    item = db.query(svc.AgentBackendConfig).filter(svc.AgentBackendConfig.id == config_id).first()
    if not item:
        raise HTTPException(404, "模块执行后端配置不存在")
    module_id = item.module_id
    project_id = item.project_id
    svc.delete_module_config(db, config_id)
    log_audit(
        db, action="delete", resource_type="workflow_module_config",
        resource_id=config_id, resource_name=module_id, user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"module_id": module_id, "project_id": project_id},
    )
    db.commit()
    return {"message": "删除成功"}


# ══════════════════════════════════════════════════════════
# input 字段映射
# ══════════════════════════════════════════════════════════

@router.post("/mappings/list")
def list_input_mappings(module_id: str = None, db: Session = Depends(get_db)):
    """input 字段映射列表（可按 module_id 过滤）"""
    items = svc.list_input_mappings(db, module_id)
    return {"items": [svc.input_mapping_to_response(i) for i in items], "total": len(items)}


@router.post("/mappings")
def upsert_input_mapping(
    data: WorkflowInputMappingCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建/更新 input 字段映射（按 module_id + aits_field 唯一）"""
    item = svc.upsert_input_mapping(db, data.model_dump())
    log_audit(
        db, action="update", resource_type="workflow_input_mapping",
        resource_id=item.id, resource_name=f"{item.module_id}.{item.aits_field}", user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"external_field": item.external_field},
    )
    db.commit()
    return svc.input_mapping_to_response(item)


@router.put("/mappings/{mapping_id}")
def update_input_mapping(
    mapping_id: int,
    data: WorkflowInputMappingUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新 input 字段映射"""
    item = svc.update_input_mapping(db, mapping_id, data.model_dump(exclude_unset=True))
    log_audit(
        db, action="update", resource_type="workflow_input_mapping",
        resource_id=item.id, resource_name=f"{item.module_id}.{item.aits_field}", user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return svc.input_mapping_to_response(item)


@router.delete("/mappings/{mapping_id}")
def delete_input_mapping(
    mapping_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除 input 字段映射"""
    svc.delete_input_mapping(db, mapping_id)
    log_audit(
        db, action="delete", resource_type="workflow_input_mapping",
        resource_id=mapping_id, resource_name=str(mapping_id), user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return {"message": "已删除"}


# ══════════════════════════════════════════════════════════
# 调用回调日志
# ══════════════════════════════════════════════════════════

@router.post("/call-logs/list")
def list_call_logs(
    data: dict = None,
    db: Session = Depends(get_db),
):
    """调用回调日志查询（可按 agent_task_id/module_id/uuid/phase/status 筛选 backend=workflow 任务）"""
    data = data or {}
    result = svc.list_call_logs(
        db,
        page=data.get("page", 1),
        page_size=data.get("page_size", 20),
        agent_task_id=data.get("agent_task_id"),
        module_id=data.get("module_id"),
        uuid=data.get("uuid"),
        phase=data.get("phase"),
        status=data.get("status"),
    )
    return {
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
        "items": [
            {
                "id": i.id,
                "agent_task_id": i.agent_task_id,
                "module_id": i.module_id,
                "connector_id": i.connector_id,
                "uuid": i.uuid,
                "request_json": i.request_json,
                "response_json": i.response_json,
                "external_task_id": i.external_task_id,
                "phase": i.phase,
                "status": i.status,
                "cost_ms": i.cost_ms,
                "retry_times": i.retry_times,
                "fallback_used": i.fallback_used,
                "error_msg": i.error_msg,
                "created_at": i.created_at,
            }
            for i in result["items"]
        ],
    }


# ══════════════════════════════════════════════════════════
# 模块执行后端查询（仅需登录，供业务页面决定是否展示"执行方式"选项）
# ══════════════════════════════════════════════════════════

public_router = APIRouter(
    prefix="/api/workflow",
    tags=["agent配置"],
    dependencies=[Depends(get_current_user)],
)


@public_router.get("/effective")
def get_effective_backend(
    module_id: str,
    project_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """查询模块的执行后端有效配置（用于前端页面决定是否展示 workflow 选项）

    返回：
    - webhook_enabled: 全局开关是否启用
    - page_selectable: 模块是否允许页面切换执行后端
    - workflow_available: 是否具备 workflow 执行条件（全局开关+模块已配置连接+external_agent_id）
    - default_backend: 系统默认执行后端 local/workflow
    """
    from app.services.workflow_config_service import resolve_effective_backend
    webhook_enabled = svc.is_webhook_enabled(db)
    cfg = svc.get_module_config(db, module_id, project_id)
    page_selectable = bool(cfg and cfg.page_selectable)
    workflow_available = bool(
        webhook_enabled
        and cfg
        and cfg.default_backend == "workflow"
        and cfg.connector_id
        and cfg.external_agent_id
    )
    default_backend = resolve_effective_backend(db, module_id, project_id)
    return {
        "webhook_enabled": webhook_enabled,
        "page_selectable": page_selectable,
        "workflow_available": workflow_available,
        "default_backend": default_backend,
        "module_id": module_id,
        "project_id": project_id,
    }


# ══════════════════════════════════════════════════════════
# 项目级模块执行后端配置（项目成员可操作，项目管理员可配置）
# ══════════════════════════════════════════════════════════

project_router = APIRouter(
    prefix="/api/projects/{project_id}",
    tags=["agent配置-项目级"],
    dependencies=[Depends(get_current_user), Depends(get_project)],
)


@project_router.get("/agent-backend-configs")
def list_project_module_configs(
    project_id: int,
    db: Session = Depends(get_db),
):
    """获取项目级各模块执行后端配置（仅返回项目级行，不含系统级继承）

    返回每个模块的项目级配置；未配置项目级的模块不在列表中（前端显示"继承系统默认"）。
    """
    from app.models.workflow import AgentBackendConfig
    items = db.query(AgentBackendConfig).filter(
        AgentBackendConfig.project_id == project_id,
    ).order_by(AgentBackendConfig.module_id).all()
    return {
        "items": [svc.module_config_to_response(i) for i in items],
        "total": len(items),
        "project_id": project_id,
    }


@project_router.get("/agent-backend-configs/effective")
def get_project_effective_configs(
    project_id: int,
    db: Session = Depends(get_db),
):
    """获取项目生效配置（合并系统级+项目级，供项目配置页展示）

    返回四大核心模块的生效配置，每个模块包含：
    - effective: 生效配置（项目级优先，无则系统级）
    - project_config: 项目级配置（无则 null，表示继承系统默认）
    - system_config: 系统级配置
    - source: 配置来源 project/system
    """
    from app.services.workflow_config_service import MODULE_IDS
    webhook_enabled = svc.is_webhook_enabled(db)
    result = []
    for module_id in MODULE_IDS:
        proj_cfg = svc.get_module_config(db, module_id, project_id)
        sys_cfg = svc.get_module_config(db, module_id, None)
        # 判断生效配置来源
        has_project = db.query(__import__('app.models.workflow', fromlist=['AgentBackendConfig']).AgentBackendConfig).filter(
            __import__('app.models.workflow', fromlist=['AgentBackendConfig']).AgentBackendConfig.module_id == module_id,
            __import__('app.models.workflow', fromlist=['AgentBackendConfig']).AgentBackendConfig.project_id == project_id,
        ).first() is not None
        source = "project" if has_project else "system"
        effective_cfg = proj_cfg if has_project else sys_cfg
        result.append({
            "module_id": module_id,
            "source": source,
            "webhook_enabled": webhook_enabled,
            "effective": svc.module_config_to_response(effective_cfg) if effective_cfg else None,
            "project_config": svc.module_config_to_response(proj_cfg) if has_project and proj_cfg else None,
            "system_config": svc.module_config_to_response(sys_cfg) if sys_cfg else None,
            "workflow_ready": bool(
                webhook_enabled
                and effective_cfg
                and effective_cfg.default_backend == "workflow"
                and effective_cfg.connector_id
                and effective_cfg.external_agent_id
            ),
        })
    return {"items": result, "total": len(result), "project_id": project_id}


@project_router.put("/agent-backend-configs/{module_id}")
def upsert_project_module_config(
    project_id: int,
    module_id: str,
    data: AgentBackendConfigUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新项目级某模块执行后端配置（不存在则创建）

    用于项目级覆盖系统默认。设置后该模块在本项目内使用项目级配置。
    """
    if data.default_backend is not None and data.default_backend not in ALLOWED_BACKENDS:
        raise HTTPException(400, f"执行后端必须为: {', '.join(ALLOWED_BACKENDS)}")
    # 校验 module_id 合法性
    from app.services.workflow_config_service import MODULE_IDS
    if module_id not in MODULE_IDS:
        raise HTTPException(400, f"模块ID必须为: {', '.join(MODULE_IDS)}")
    # 构造 upsert 数据
    upsert_data = {"module_id": module_id, "project_id": project_id}
    for key in ("default_backend", "connector_id", "external_agent_id", "page_selectable"):
        val = getattr(data, key, None)
        if val is not None:
            upsert_data[key] = val
    item = svc.upsert_module_config(db, upsert_data)
    log_audit(
        db, action="update", resource_type="project_workflow_module_config",
        resource_id=item.id, resource_name=f"{module_id}@project_{project_id}", user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "module_id": module_id, "default_backend": item.default_backend},
    )
    db.commit()
    return svc.module_config_to_response(item)


@project_router.delete("/agent-backend-configs/{module_id}")
def delete_project_module_config(
    project_id: int,
    module_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除项目级某模块配置（恢复继承系统级默认）

    删除后该模块在本项目内恢复使用系统级默认配置。
    """
    from app.models.workflow import AgentBackendConfig
    item = db.query(AgentBackendConfig).filter(
        AgentBackendConfig.module_id == module_id,
        AgentBackendConfig.project_id == project_id,
    ).first()
    if not item:
        raise HTTPException(404, "项目级模块配置不存在")
    db.delete(item)
    log_audit(
        db, action="delete", resource_type="project_workflow_module_config",
        resource_id=item.id, resource_name=f"{module_id}@project_{project_id}", user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "module_id": module_id},
    )
    db.commit()
    return {"message": "已删除，恢复继承系统级默认"}
