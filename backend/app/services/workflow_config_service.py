"""
外部工作流接入配置管理服务

职责：
- 平台连接 CRUD（凭证加密存储，列表返回掩码）
- 固定 Webhook 全局配置（单行，签名密钥生成/重置）
- 模块执行后端配置（CRUD + 查询生效配置：项目级优先于全局）
- input 字段映射 CRUD
- 调用回调日志查询
"""
import logging
import secrets
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.workflow import (
    WorkflowPlatformConnector,
    WorkflowWebhookConfig,
    AgentBackendConfig,
    WorkflowInputMapping,
    WorkflowCallLog,
)
from app.agents.llm_factory import encrypt_api_key, decrypt_api_key

logger = logging.getLogger(__name__)

# 五大核心模块清单（module_id → 对应 agent_type）
# 新模块请优先在 workflow_registry 中注册，此处保留向后兼容
MODULE_IDS = [
    "requirement.generate",
    "requirement.split_features",
    "case.generate",
    "case.review",
    "report.generate",
]

# module_id → AgentTask.agent_type 映射（uuid 路由按 agent_type 定位模块）
MODULE_TO_AGENT_TYPE = {
    "requirement.generate": "requirement_generator",
    "requirement.split_features": "feature_splitter",
    "case.generate": "case_generator",
    "case.review": "case_reviewer",
    "report.generate": "report_generator",
}

# 反向：agent_type → module_id
AGENT_TYPE_TO_MODULE = {v: k for k, v in MODULE_TO_AGENT_TYPE.items()}


# ── 通用掩码 ──────────────────────────────────────────────

def _mask(value: Optional[str], visible: int = 4) -> str:
    """对敏感凭证做掩码：仅显示前 visible 位 + ***（用于平台连接 auth_token）"""
    if not value:
        return ""
    if len(value) <= visible:
        return "*" * len(value)
    return value[:visible] + "***" + value[-2:]


def _mask_full(value: Optional[str]) -> str:
    """全掩码：返回与明文相同长度的圆点，保持视觉长度一致（用于签名密钥）"""
    if not value:
        return ""
    return "•" * len(value)


# ══════════════════════════════════════════════════════════
# 平台连接
# ══════════════════════════════════════════════════════════

def list_connectors(db: Session) -> List[WorkflowPlatformConnector]:
    return db.query(WorkflowPlatformConnector).filter(
        WorkflowPlatformConnector.is_deleted == False  # noqa: E712
    ).order_by(WorkflowPlatformConnector.id.desc()).all()


def get_connector(db: Session, connector_id: int) -> WorkflowPlatformConnector:
    item = db.query(WorkflowPlatformConnector).filter(
        WorkflowPlatformConnector.id == connector_id,
        WorkflowPlatformConnector.is_deleted == False,  # noqa: E712
    ).first()
    if not item:
        raise HTTPException(404, "外部平台连接不存在")
    return item


def get_connector_decrypted(connector: WorkflowPlatformConnector) -> WorkflowPlatformConnector:
    """返回 auth_token 已解密的连接对象（仅供连接器调用时使用，不对外暴露）"""
    if connector.auth_token:
        connector.auth_token = decrypt_api_key(connector.auth_token)
    return connector


def create_connector(db: Session, data: Dict[str, Any]) -> WorkflowPlatformConnector:
    item = WorkflowPlatformConnector(
        name=data["name"],
        platform_type=data["platform_type"],
        base_url=data["base_url"].rstrip("/"),
        auth_type=data.get("auth_type", "bearer"),
        auth_token=encrypt_api_key(data["auth_token"]) if data.get("auth_token") else None,
        auth_header=data.get("auth_header", "Authorization"),
        accept_timeout=data.get("accept_timeout", 30),
        status=data.get("status", "active"),
        run_path=data.get("run_path", "/v1/workflows/run"),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_connector(db: Session, connector_id: int, data: Dict[str, Any]) -> WorkflowPlatformConnector:
    item = get_connector(db, connector_id)
    for key in ("name", "platform_type", "auth_type", "auth_header",
                "accept_timeout", "status", "run_path"):
        if key in data and data[key] is not None:
            setattr(item, key, data[key])
    if "base_url" in data and data["base_url"] is not None:
        item.base_url = data["base_url"].rstrip("/")
    # auth_token 仅在显式提供时更新（空字符串视为清空）
    if "auth_token" in data and data["auth_token"] is not None:
        item.auth_token = encrypt_api_key(data["auth_token"])
    db.commit()
    db.refresh(item)
    return item


def delete_connector(db: Session, connector_id: int) -> None:
    item = get_connector(db, connector_id)
    item.soft_delete()
    db.commit()


def connector_to_response(item: WorkflowPlatformConnector) -> Dict[str, Any]:
    """连接对象转响应字典（auth_token 掩码）"""
    return {
        "id": item.id,
        "name": item.name,
        "platform_type": item.platform_type,
        "base_url": item.base_url,
        "auth_type": item.auth_type,
        "auth_token_masked": _mask(decrypt_api_key(item.auth_token)) if item.auth_token else "",
        "auth_header": item.auth_header,
        "accept_timeout": item.accept_timeout,
        "status": item.status,
        "run_path": item.run_path,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


# ══════════════════════════════════════════════════════════
# 固定 Webhook 全局配置（单行）
# ══════════════════════════════════════════════════════════

_DEFAULT_WEBHOOK_URL = "http://localhost:8000/api/workflow/webhook"


def get_webhook_config(db: Session) -> WorkflowWebhookConfig:
    """获取全局 Webhook 配置（单行）；不存在则创建默认行"""
    item = db.query(WorkflowWebhookConfig).first()
    if not item:
        item = WorkflowWebhookConfig(
            webhook_url=_DEFAULT_WEBHOOK_URL,
            enabled=False,
            secret=None,
            callback_timeout=1800,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
    return item


def update_webhook_config(db: Session, data: Dict[str, Any]) -> WorkflowWebhookConfig:
    item = get_webhook_config(db)
    if "webhook_url" in data and data["webhook_url"] is not None:
        item.webhook_url = data["webhook_url"]
    if "enabled" in data and data["enabled"] is not None:
        item.enabled = data["enabled"]
    if "callback_timeout" in data and data["callback_timeout"] is not None:
        item.callback_timeout = data["callback_timeout"]
    # 显式传入明文 secret
    if "secret" in data and data["secret"]:
        item.secret = encrypt_api_key(data["secret"])
    # 重新生成密钥
    if data.get("regenerate_secret"):
        item.secret = encrypt_api_key(secrets.token_urlsafe(32))
    db.commit()
    db.refresh(item)
    return item


def webhook_config_to_response(item: WorkflowWebhookConfig) -> Dict[str, Any]:
    secret_plain = decrypt_api_key(item.secret) if item.secret else None
    return {
        "id": item.id,
        "webhook_url": item.webhook_url,
        "enabled": item.enabled,
        "secret_masked": _mask_full(secret_plain) if secret_plain else "",
        "secret_plain": secret_plain,
        "callback_timeout": item.callback_timeout,
        "updated_at": item.updated_at,
    }


def is_webhook_enabled(db: Session) -> bool:
    return bool(get_webhook_config(db).enabled)


def get_webhook_secret(db: Session) -> Optional[str]:
    secret = get_webhook_config(db).secret
    return decrypt_api_key(secret) if secret else None


def get_callback_timeout(db: Session) -> int:
    return get_webhook_config(db).callback_timeout


# ══════════════════════════════════════════════════════════
# 模块执行后端配置
# ══════════════════════════════════════════════════════════

def list_module_configs(db: Session) -> List[AgentBackendConfig]:
    return db.query(AgentBackendConfig).order_by(AgentBackendConfig.module_id).all()


def get_module_config(db: Session, module_id: str, project_id: Optional[int] = None) -> Optional[AgentBackendConfig]:
    """查询生效配置：项目级优先于全局（project_id 非空时优先匹配项目级，否则取全局 NULL 行）"""
    if project_id is not None:
        proj_cfg = db.query(AgentBackendConfig).filter(
            AgentBackendConfig.module_id == module_id,
            AgentBackendConfig.project_id == project_id,
        ).first()
        if proj_cfg:
            return proj_cfg
    return db.query(AgentBackendConfig).filter(
        AgentBackendConfig.module_id == module_id,
        AgentBackendConfig.project_id.is_(None),
    ).first()


def upsert_module_config(db: Session, data: Dict[str, Any]) -> AgentBackendConfig:
    """创建或更新模块配置（按 module_id + project_id 唯一）"""
    module_id = data["module_id"]
    project_id = data.get("project_id")
    item = get_module_config(db, module_id, project_id)
    if not item:
        # 项目级查不到时，若 project_id 非空则新建项目级行；否则新建全局行
        item = AgentBackendConfig(
            module_id=module_id,
            project_id=project_id,
            default_backend=data.get("default_backend", "local"),
            connector_id=data.get("connector_id"),
            external_agent_id=data.get("external_agent_id"),
            page_selectable=data.get("page_selectable", True),
        )
        db.add(item)
    else:
        for key in ("default_backend", "connector_id", "external_agent_id", "page_selectable"):
            if key in data and data[key] is not None:
                setattr(item, key, data[key])
    db.commit()
    db.refresh(item)
    return item


def update_module_config(db: Session, config_id: int, data: Dict[str, Any]) -> AgentBackendConfig:
    item = db.query(AgentBackendConfig).filter(AgentBackendConfig.id == config_id).first()
    if not item:
        raise HTTPException(404, "模块执行后端配置不存在")
    for key in ("default_backend", "connector_id", "external_agent_id", "page_selectable"):
        if key in data and data[key] is not None:
            setattr(item, key, data[key])
    db.commit()
    db.refresh(item)
    return item


def delete_module_config(db: Session, config_id: int) -> None:
    """删除模块执行后端配置"""
    item = db.query(AgentBackendConfig).filter(AgentBackendConfig.id == config_id).first()
    if not item:
        raise HTTPException(404, "模块执行后端配置不存在")
    db.delete(item)
    db.commit()


def module_config_to_response(item: AgentBackendConfig) -> Dict[str, Any]:
    return {
        "id": item.id,
        "module_id": item.module_id,
        "project_id": item.project_id,
        "default_backend": item.default_backend,
        "connector_id": item.connector_id,
        "external_agent_id": item.external_agent_id,
        "page_selectable": item.page_selectable,
        "updated_at": item.updated_at,
    }


def resolve_effective_backend(
    db: Session,
    module_id: str,
    project_id: Optional[int],
    page_choice: Optional[str] = None,
) -> str:
    """解析最终执行后端：页面选择优先 → 模块配置 → local

    v0.7 确认 #5：配置了工作流则默认执行工作流；页面选择优先级高于系统默认。
    全局开关/Webhook 未启用时强制 local。
    """
    # 全局开关：Webhook 未启用则一律 local
    if not is_webhook_enabled(db):
        return "local"
    cfg = get_module_config(db, module_id, project_id)
    if not cfg:
        return "local"
    # 模块未配置连接/agent 标识 → 退回 local
    if cfg.default_backend == "workflow" and not (
        cfg.connector_id and cfg.external_agent_id
    ):
        return "local"
    # 页面选择优先（且模块允许页面切换）
    if page_choice and cfg.page_selectable:
        return page_choice
    return cfg.default_backend


def module_workflow_ready(db: Session, module_id: str, project_id: Optional[int] = None) -> bool:
    """模块是否已具备 workflow 执行条件（配置了连接 + external_agent_id）"""
    cfg = get_module_config(db, module_id, project_id)
    if not cfg:
        return False
    return bool(cfg.connector_id and cfg.external_agent_id)


# ══════════════════════════════════════════════════════════
# input 字段映射
# ══════════════════════════════════════════════════════════

def list_input_mappings(db: Session, module_id: Optional[str] = None) -> List[WorkflowInputMapping]:
    q = db.query(WorkflowInputMapping)
    if module_id:
        q = q.filter(WorkflowInputMapping.module_id == module_id)
    return q.order_by(WorkflowInputMapping.module_id, WorkflowInputMapping.id).all()


def upsert_input_mapping(db: Session, data: Dict[str, Any]) -> WorkflowInputMapping:
    """按 (module_id, aits_field) 唯一创建或更新"""
    item = db.query(WorkflowInputMapping).filter(
        WorkflowInputMapping.module_id == data["module_id"],
        WorkflowInputMapping.aits_field == data["aits_field"],
    ).first()
    if not item:
        item = WorkflowInputMapping(
            module_id=data["module_id"],
            aits_field=data["aits_field"],
            external_field=data.get("external_field") or data["aits_field"],
            required=data.get("required", False),
            default_value=data.get("default_value"),
        )
        db.add(item)
    else:
        for key in ("external_field", "required", "default_value"):
            if key in data and data[key] is not None:
                setattr(item, key, data[key])
    db.commit()
    db.refresh(item)
    return item


def update_input_mapping(db: Session, mapping_id: int, data: Dict[str, Any]) -> WorkflowInputMapping:
    item = db.query(WorkflowInputMapping).filter(WorkflowInputMapping.id == mapping_id).first()
    if not item:
        raise HTTPException(404, "input 字段映射不存在")
    for key in ("external_field", "required", "default_value"):
        if key in data and data[key] is not None:
            setattr(item, key, data[key])
    db.commit()
    db.refresh(item)
    return item


def delete_input_mapping(db: Session, mapping_id: int) -> None:
    item = db.query(WorkflowInputMapping).filter(WorkflowInputMapping.id == mapping_id).first()
    if not item:
        raise HTTPException(404, "input 字段映射不存在")
    db.delete(item)
    db.commit()


def input_mapping_to_response(item: WorkflowInputMapping) -> Dict[str, Any]:
    return {
        "id": item.id,
        "module_id": item.module_id,
        "aits_field": item.aits_field,
        "external_field": item.external_field,
        "required": item.required,
        "default_value": item.default_value,
        "updated_at": item.updated_at,
    }


# ══════════════════════════════════════════════════════════
# 调用回调日志
# ══════════════════════════════════════════════════════════

def list_call_logs(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    agent_task_id: Optional[int] = None,
    module_id: Optional[str] = None,
    uuid: Optional[str] = None,
    phase: Optional[str] = None,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    q = db.query(WorkflowCallLog)
    if agent_task_id:
        q = q.filter(WorkflowCallLog.agent_task_id == agent_task_id)
    if module_id:
        q = q.filter(WorkflowCallLog.module_id == module_id)
    if uuid:
        q = q.filter(WorkflowCallLog.uuid == uuid)
    if phase:
        q = q.filter(WorkflowCallLog.phase == phase)
    if status:
        q = q.filter(WorkflowCallLog.status == status)
    total = q.count()
    items = (
        q.order_by(WorkflowCallLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"total": total, "page": page, "page_size": page_size, "items": items}
