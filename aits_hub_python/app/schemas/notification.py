"""
通知模块 Pydantic Schemas
"""
from app.schemas.common import PaginatedResponse

import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


# ==================== 事件类型元数据 ====================

class EventTypeInfo(BaseModel):
    """事件类型信息（供前端下拉选择）"""
    code: str
    name: str
    category: str
    level: str  # success/info/warning/error
    color: str  # green/blue/orange/red
    description: str = ""


# ==================== NotificationChannel ====================

class NotificationChannelBase(BaseModel):
    name: str = Field(..., max_length=100, description="渠道名称")
    channel_type: str = Field("feishu", description="渠道类型")
    webhook_url: str = Field(..., max_length=500, description="Webhook 地址")
    sign_enabled: bool = Field(False, description="是否启用签名校验")
    secret: Optional[str] = Field(None, description="签名密钥（创建/更新时传入，返回时脱敏）")
    enabled: bool = Field(True, description="是否启用")
    description: Optional[str] = Field(None, max_length=500, description="备注")


class NotificationChannelCreate(NotificationChannelBase):
    pass


class NotificationChannelUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    channel_type: Optional[str] = None
    webhook_url: Optional[str] = Field(None, max_length=500)
    sign_enabled: Optional[bool] = None
    secret: Optional[str] = None
    enabled: Optional[bool] = None
    description: Optional[str] = Field(None, max_length=500)


class NotificationChannelResponse(BaseModel):
    id: int
    name: str
    channel_type: str
    webhook_url: str
    sign_enabled: bool
    enabled: bool
    description: Optional[str] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # 脱敏字段
    secret_masked: Optional[str] = None
    has_secret: bool = False

    class Config:
        from_attributes = True


# ==================== NotificationRule ====================

class NotificationRuleBase(BaseModel):
    name: str = Field(..., max_length=100, description="规则名称")
    event_code: List[str] = Field(..., description="事件编码列表（支持多选）")
    channel_id: int = Field(..., description="关联渠道ID")
    conditions: Optional[Dict[str, Any]] = Field(default_factory=dict, description="触发条件")
    receivers: Optional[Dict[str, Any]] = Field(default_factory=dict, description="接收人配置")
    enabled: bool = Field(True, description="是否启用")

    @field_validator("event_code", mode="before")
    @classmethod
    def parse_event_code(cls, v):
        """数据库中 event_code 以 JSON 字符串存储，读取时反序列化为列表"""
        if isinstance(v, str):
            if not v.strip():
                return []
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass
            return [v]
        if isinstance(v, list):
            return v
        return []


class NotificationRuleCreate(NotificationRuleBase):
    pass


class NotificationRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    event_code: Optional[List[str]] = Field(None, description="事件编码列表")
    channel_id: Optional[int] = None
    conditions: Optional[Dict[str, Any]] = None
    receivers: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None


class NotificationRuleResponse(BaseModel):
    id: int
    name: str
    event_code: List[str] = []
    channel_id: int
    conditions: Optional[Dict[str, Any]] = {}
    receivers: Optional[Dict[str, Any]] = {}
    enabled: bool
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    channel_name: Optional[str] = None

    @field_validator("event_code", mode="before")
    @classmethod
    def parse_event_code(cls, v):
        if isinstance(v, str):
            if not v.strip():
                return []
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass
            return [v]
        return v if isinstance(v, list) else []

    class Config:
        from_attributes = True


# ==================== NotificationRecord ====================

class NotificationRecordResponse(BaseModel):
    id: int
    project_id: Optional[int] = None
    channel_id: Optional[int] = None
    rule_id: Optional[int] = None
    event_code: str
    title: str
    content: Optional[str] = None
    status: str
    response_code: Optional[int] = None
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    sent_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    # 关联名称
    channel_name: Optional[str] = None
    event_name: Optional[str] = None
    duration_ms: Optional[int] = None

    class Config:
        from_attributes = True


# ==================== 通用 ====================

class TestSendResult(BaseModel):
    """测试发送结果"""
    success: bool
    status_code: Optional[int] = None
    message: str = ""
    response: Optional[Any] = None
