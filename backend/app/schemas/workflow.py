"""
外部工作流接入 Pydantic Schema

覆盖：平台连接、固定 Webhook 全局配置、模块执行后端、input 字段映射、调用回调日志。
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


# ── 平台连接 ──────────────────────────────────────────────

class WorkflowConnectorBase(BaseModel):
    name: str = Field(..., max_length=100, description="连接名称")
    platform_type: str = Field(..., max_length=30, description="openai_compat/coze/dify/n8n/custom")
    base_url: str = Field(..., max_length=500, description="平台服务地址（AITS调用方向）")
    auth_type: str = Field("bearer", description="鉴权方式：bearer/apikey/custom")
    auth_token: Optional[str] = Field(None, description="凭证明文（写入时加密存储，列表返回掩码）")
    auth_header: str = Field("Authorization", description="鉴权 Header 名")
    accept_timeout: int = Field(30, description="等待受理超时(秒)")
    status: str = Field("active", description="active/inactive")
    run_path: str = Field("/v1/workflows/run", description="调用外部 agent 的请求路径")


class WorkflowConnectorCreate(WorkflowConnectorBase):
    pass


class WorkflowConnectorUpdate(BaseModel):
    name: Optional[str] = None
    platform_type: Optional[str] = None
    base_url: Optional[str] = None
    auth_type: Optional[str] = None
    auth_token: Optional[str] = None
    auth_header: Optional[str] = None
    accept_timeout: Optional[int] = None
    status: Optional[str] = None
    run_path: Optional[str] = None


class WorkflowConnectorResponse(BaseModel):
    id: int
    name: str
    platform_type: str
    base_url: str
    auth_type: str
    auth_token_masked: Optional[str] = None
    auth_header: str
    accept_timeout: int
    status: str
    run_path: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── 固定 Webhook 全局配置 ─────────────────────────────────

class WorkflowWebhookConfigUpdate(BaseModel):
    webhook_url: Optional[str] = None
    enabled: Optional[bool] = None
    secret: Optional[str] = None  # 传明文则加密存储；不传则保持原值
    regenerate_secret: bool = Field(False, description="是否重新生成签名密钥")
    callback_timeout: Optional[int] = None


class WorkflowWebhookConfigResponse(BaseModel):
    id: int
    webhook_url: str
    enabled: bool
    secret_masked: Optional[str] = None
    secret_plain: Optional[str] = Field(None, description="签名密钥明文（仅管理员接口返回）")
    callback_timeout: int
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── 模块执行后端配置 ──────────────────────────────────────

class AgentBackendConfigBase(BaseModel):
    module_id: str = Field(..., max_length=64, description="模块ID，如 requirement.generate")
    project_id: Optional[int] = Field(None, description="项目ID（NULL=全局，预留项目级）")
    default_backend: str = Field("local", description="local/workflow")
    connector_id: Optional[int] = None
    external_agent_id: Optional[str] = Field(None, max_length=128)
    page_selectable: bool = True


class AgentBackendConfigCreate(AgentBackendConfigBase):
    pass


class AgentBackendConfigUpdate(BaseModel):
    default_backend: Optional[str] = None
    connector_id: Optional[int] = None
    external_agent_id: Optional[str] = None
    page_selectable: Optional[bool] = None


class AgentBackendConfigResponse(BaseModel):
    id: int
    module_id: str
    project_id: Optional[int] = None
    default_backend: str
    connector_id: Optional[int] = None
    external_agent_id: Optional[str] = None
    page_selectable: bool
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── input 字段映射 ────────────────────────────────────────

class WorkflowInputMappingBase(BaseModel):
    module_id: str = Field(..., max_length=64)
    aits_field: str = Field(..., max_length=64)
    external_field: str = Field(..., max_length=64)
    required: bool = False
    default_value: Optional[str] = None


class WorkflowInputMappingCreate(WorkflowInputMappingBase):
    pass


class WorkflowInputMappingUpdate(BaseModel):
    external_field: Optional[str] = None
    required: Optional[bool] = None
    default_value: Optional[str] = None


class WorkflowInputMappingResponse(BaseModel):
    id: int
    module_id: str
    aits_field: str
    external_field: str
    required: bool
    default_value: Optional[str] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── 调用回调日志 ──────────────────────────────────────────

class WorkflowCallLogResponse(BaseModel):
    id: int
    agent_task_id: int
    module_id: str
    connector_id: Optional[int] = None
    uuid: Optional[str] = None
    request_json: Optional[Dict[str, Any]] = None
    response_json: Optional[Dict[str, Any]] = None
    external_task_id: Optional[str] = None
    phase: str
    status: str
    cost_ms: Optional[int] = None
    retry_times: int = 0
    fallback_used: bool = False
    error_msg: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class WorkflowCallLogListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[WorkflowCallLogResponse]
