"""
聊天历史记录 Schema
"""
from typing import Optional, List, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field


class ChatSessionCreate(BaseModel):
    project_id: Optional[int] = None
    title: str = "新对话"
    llm_config_id: Optional[int] = None
    use_knowledge: bool = False


class ChatSessionUpdate(BaseModel):
    title: Optional[str] = None


class ChatSessionResponse(BaseModel):
    id: int
    user_id: int
    project_id: Optional[int] = None
    title: str
    llm_config_id: Optional[int] = None
    use_knowledge: bool = False
    message_count: int = 0
    last_message_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ChatSessionListResponse(BaseModel):
    total: int
    items: List[ChatSessionResponse]


class ChatMessageResponse(BaseModel):
    id: int
    session_id: int
    role: str
    content: Optional[str] = None
    tool_calls: Optional[Any] = None
    knowledge_results: Optional[Any] = None
    progress: Optional[Any] = None
    token_usage: Optional[Any] = None
    sort_order: int = 0
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ChatSessionDetailResponse(BaseModel):
    session: ChatSessionResponse
    messages: List[ChatMessageResponse]
