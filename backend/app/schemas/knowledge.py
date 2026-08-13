"""
知识库 Pydantic 模型
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class KnowledgeDocBase(BaseModel):
    title: str = Field(..., max_length=200, description="文档标题")
    content: str = Field(default="", description="文档内容")
    file_type: str = Field(default="text", description="文件类型")


class KnowledgeDocCreate(KnowledgeDocBase):
    pass


class KnowledgeDocResponse(KnowledgeDocBase):
    id: int
    project_id: int
    file_path: str = ""
    chunk_count: int = 0
    status: str
    error_message: str = ""
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KnowledgeDocListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[KnowledgeDocResponse]


class KnowledgeSearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)


class KnowledgeSearchResponse(BaseModel):
    query: str
    results: List[Dict[str, Any]]
    total: int


class KnowledgeStatsResponse(BaseModel):
    project_id: int
    total_docs: int
    total_chunks: int
