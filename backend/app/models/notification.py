"""
通知模块数据模型（公共模块，渠道/规则全局共享）

包含3张表：
- notification_channels：通知渠道（飞书机器人等，全局公共配置）
- notification_rules：通知规则（事件→渠道映射，全局公共）
- notification_records：通知发送记录（保留 project_id 标识事件来源）
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean, JSON
from app.database import Base, SoftDeleteMixin
from app.core.timezone import china_now_naive


class NotificationChannel(SoftDeleteMixin, Base):
    """通知渠道表（全局公共，所有项目共享）"""
    __tablename__ = "notification_channels"
    __table_args__ = {"comment": "通知渠道表（飞书机器人等，全局公共配置）"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    name = Column(String(100), nullable=False, comment="渠道名称（如：测试团队飞书群）")
    channel_type = Column(String(20), nullable=False, default="feishu", comment="渠道类型：feishu/email/dingtalk/wecom/webhook")
    webhook_url = Column(String(500), nullable=False, comment="Webhook 地址")
    secret = Column(String(500), nullable=True, comment="签名密钥（Fernet 加密存储）")
    sign_enabled = Column(Boolean, default=False, nullable=False, comment="是否启用签名校验")
    enabled = Column(Boolean, default=True, nullable=False, comment="是否启用")
    description = Column(String(500), nullable=True, comment="备注说明")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment="创建人ID")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")


class NotificationRule(SoftDeleteMixin, Base):
    """通知规则表（全局公共，可通过 conditions.project_ids 限定项目）"""
    __tablename__ = "notification_rules"
    __table_args__ = {"comment": "通知规则表（事件编码→渠道映射，全局公共）"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    name = Column(String(100), nullable=False, comment="规则名称")
    event_code = Column(String(50), nullable=False, index=True, comment="事件编码（如 plan.execution.completed）")
    channel_id = Column(Integer, ForeignKey("notification_channels.id"), nullable=False, index=True, comment="关联通知渠道ID")
    conditions = Column(JSON, default=dict, comment="触发条件（如 {\"min_failures\": 1, \"project_ids\": [1,2]}）")
    receivers = Column(JSON, default=dict, comment="接收人配置（预留）")
    enabled = Column(Boolean, default=True, nullable=False, comment="是否启用")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment="创建人ID")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")


class NotificationRecord(Base):
    """通知发送记录表（保留 project_id 标识事件来源项目）"""
    __tablename__ = "notification_records"
    __table_args__ = {"comment": "通知发送记录表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=True, index=True, comment="事件来源项目ID")
    channel_id = Column(Integer, ForeignKey("notification_channels.id"), nullable=True, index=True, comment="使用的渠道ID")
    rule_id = Column(Integer, ForeignKey("notification_rules.id"), nullable=True, index=True, comment="触发的规则ID（手动发送时为空）")
    event_code = Column(String(50), nullable=False, index=True, comment="事件编码")
    title = Column(String(200), nullable=False, comment="通知标题")
    content = Column(Text, nullable=True, comment="通知内容（卡片 JSON 字符串）")
    status = Column(String(20), default="pending", nullable=False, index=True, comment="发送状态：pending/success/failed")
    response_code = Column(Integer, nullable=True, comment="HTTP 响应码")
    response_body = Column(Text, nullable=True, comment="响应内容")
    error_message = Column(String(500), nullable=True, comment="失败原因")
    retry_count = Column(Integer, default=0, nullable=False, comment="重试次数")
    sent_at = Column(DateTime, nullable=True, comment="发送完成时间")
    created_at = Column(DateTime, default=china_now_naive, index=True, comment="创建时间")
