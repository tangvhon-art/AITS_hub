"""
外部工作流平台接入相关模型

包含：
- WorkflowPlatformConnector  外部平台连接（可配置多个）
- WorkflowWebhookConfig      固定 Webhook 全局配置（单行）
- AgentBackendConfig          AI 模块执行后端配置（local/workflow）
- WorkflowCallLog            外部调用与回调日志
- WorkflowInputMapping       统一 input 字段映射（v0.7 确认 #8 可配置补充）

业务表（test_requirements / requirement_features / test_cases / 评审记录）不变，
写库仍复用现有 ContentExtractor / AICreationService / 各模块 _parse_xxx。
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON

from app.database import Base, SoftDeleteMixin, TimestampMixin
from app.core.timezone import china_now_naive


class WorkflowPlatformConnector(SoftDeleteMixin, TimestampMixin, Base):
    """外部工作流平台连接表"""
    __tablename__ = "workflow_platform_connectors"
    __table_args__ = {"comment": "外部工作流平台连接表"}

    id = Column(Integer, primary_key=True, index=True, comment="自增主键")
    name = Column(String(100), nullable=False, comment="连接名称")
    platform_type = Column(String(30), nullable=False, comment="平台类型：openai_compat/coze/dify/n8n/custom")
    base_url = Column(String(500), nullable=False, comment="平台服务地址（AITS调用方向）")
    auth_type = Column(String(30), nullable=False, default="bearer", comment="鉴权方式：bearer/apikey/custom")
    auth_token = Column(Text, comment="凭证（加密存储）")
    auth_header = Column(String(100), default="Authorization", comment="鉴权 Header 名")
    accept_timeout = Column(Integer, default=30, comment="等待受理超时(秒)")
    status = Column(String(20), nullable=False, default="active", comment="启用状态：active/inactive")
    # 预留：外部 agent 通用请求路径模板（按平台适配器解析）
    run_path = Column(String(200), default="/v1/workflows/run", comment="调用外部 agent 的请求路径")


class WorkflowWebhookConfig(Base):
    """固定 Webhook 全局配置表（单行）

    AITS 只暴露一个全局回调端点 /api/workflow/webhook，
    所有模块、所有外部 agent 都回调该地址；AITS 依据回调中的 uuid 定位任务与模块。
    """
    __tablename__ = "workflow_webhook_configs"
    __table_args__ = {"comment": "固定Webhook全局配置表"}

    id = Column(Integer, primary_key=True, index=True, comment="自增主键")
    webhook_url = Column(String(500), nullable=False, comment="AITS对外固定Webhook地址（后续Nginx配置）")
    enabled = Column(Boolean, default=False, comment="Webhook启用开关；关闭时不允许使用workflow后端")
    secret = Column(Text, comment="回调签名密钥（加密存储）")
    callback_timeout = Column(Integer, default=1800, comment="等待回调超时(秒)，默认1800(30分钟)")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")


class AgentBackendConfig(SoftDeleteMixin, Base):
    """AI 模块执行后端配置表

    v0.7 确认 #7：一期全局模块粒度，预留 project_id 扩展字段（NULL=全局）。
    支持软删：is_deleted / deleted_at（SoftDeleteMixin），删除仅置标记不物理删除。
    """
    __tablename__ = "agent_backend_configs"
    __table_args__ = (
        {"comment": "AI模块执行后端配置表"},
    )

    id = Column(Integer, primary_key=True, index=True, comment="自增主键")
    module_id = Column(String(64), nullable=False, index=True, comment="模块ID，如 requirement.generate")
    # 预留项目级扩展：NULL 表示全局配置（一期默认 NULL）
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=True, index=True, comment="项目ID（NULL=全局，预留项目级）")
    default_backend = Column(String(20), nullable=False, default="local", comment="默认执行后端：local/workflow")
    connector_id = Column(Integer, ForeignKey("workflow_platform_connectors.id"), nullable=True, comment="绑定的外部平台连接ID")
    external_agent_id = Column(String(128), nullable=True, comment="外部 agent/工作流标识")
    page_selectable = Column(Boolean, default=True, comment="页面是否可切换执行方式")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")


class WorkflowCallLog(Base):
    """外部工作流平台调用与回调日志表"""
    __tablename__ = "workflow_call_logs"
    __table_args__ = (
        {"comment": "外部工作流平台调用与回调日志表"},
    )

    id = Column(Integer, primary_key=True, index=True, comment="自增主键")
    agent_task_id = Column(Integer, nullable=False, index=True, comment="关联 AgentTask")
    module_id = Column(String(64), nullable=False, comment="模块ID")
    connector_id = Column(Integer, nullable=True, comment="外部平台连接ID")
    uuid = Column(String(64), nullable=True, index=True, comment="AITS回调定位ID")
    request_json = Column(JSON, comment="出参（脱敏）")
    response_json = Column(JSON, comment="受理/回调内容（脱敏）")
    external_task_id = Column(String(128), nullable=True, comment="外部平台受理的任务ID")
    phase = Column(String(20), nullable=False, comment="阶段：invoke/accept/callback/complete/fail")
    status = Column(String(20), nullable=False, comment="状态：success/failed/timeout")
    cost_ms = Column(Integer, nullable=True, comment="耗时(毫秒)")
    retry_times = Column(Integer, default=0, comment="重试次数")
    fallback_used = Column(Boolean, default=False, comment="是否触发降级local")
    error_msg = Column(Text, nullable=True, comment="错误信息")
    created_at = Column(DateTime, default=china_now_naive, index=True, comment="创建时间")


class WorkflowInputMapping(Base):
    """统一 input 字段映射表

    v0.7 确认 #8：input 字段以外部平台 agent 实际输入要求为准，
    可通过此表配置 AITS 字段 → 外部 agent 字段的映射与默认值。
    """
    __tablename__ = "workflow_input_mappings"
    __table_args__ = (
        {"comment": "统一input字段映射表"},
    )

    id = Column(Integer, primary_key=True, index=True, comment="自增主键")
    module_id = Column(String(64), nullable=False, index=True, comment="模块ID")
    aits_field = Column(String(64), nullable=False, comment="AITS侧字段名")
    external_field = Column(String(64), nullable=False, comment="外部agent对应字段名")
    required = Column(Boolean, default=False, comment="是否必填")
    default_value = Column(Text, nullable=True, comment="默认值（静态或模板）")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")
