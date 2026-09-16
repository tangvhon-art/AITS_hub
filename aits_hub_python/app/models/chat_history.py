"""
聊天历史记录模型 — 智能助手的会话和消息存储
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from app.core.timezone import china_now_naive


class ChatSession(Base):
    """聊天会话表"""
    __tablename__ = "chat_sessions"
    __table_args__ = {"comment": "智能助手聊天会话表"}

    id = Column(Integer, primary_key=True, comment="主键ID")
    user_id = Column(Integer, nullable=False, index=True, comment="用户ID")
    project_id = Column(Integer, nullable=True, index=True, comment="关联项目ID（通用问答为NULL）")
    title = Column(String(200), default="新对话", comment="会话标题（自动取首条消息摘要）")
    llm_config_id = Column(Integer, nullable=True, comment="使用的模型配置ID")
    use_knowledge = Column(Boolean, default=False, comment="是否使用知识库")
    message_count = Column(Integer, default=0, comment="消息数量")
    last_message_at = Column(DateTime, default=china_now_naive, comment="最后消息时间")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")
    is_deleted = Column(Boolean, default=False, index=True, comment="软删除标记")
    deleted_at = Column(DateTime, nullable=True, comment="删除时间")

    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    """聊天消息表"""
    __tablename__ = "chat_messages"
    __table_args__ = {"comment": "智能助手聊天消息表"}

    id = Column(Integer, primary_key=True, comment="主键ID")
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False, index=True, comment="会话ID")
    role = Column(String(20), nullable=False, comment="角色: user/assistant/system")
    content = Column(Text, comment="消息内容")
    tool_calls = Column(JSON, comment="工具调用记录")
    knowledge_results = Column(JSON, comment="知识库检索结果")
    progress = Column(JSON, comment="处理进度节点")
    token_usage = Column(JSON, comment="Token 使用量")
    sort_order = Column(Integer, default=0, comment="排序")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")

    session = relationship("ChatSession", back_populates="messages")
