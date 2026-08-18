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
    file_size: int = 0
    source_type: str = "manual"
    source_id: Optional[int] = None
    chunk_count: int = 0
    chunk_strategy: str = "fixed"
    chunk_size: int = 500
    overlap: int = 50
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


class KnowledgeChunkResponse(BaseModel):
    """切片响应"""
    id: int
    doc_id: int
    project_id: int = 0
    chunk_index: int
    content: str
    token_count: int = 0
    doc_title: str = ""
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class KnowledgeChunkListResponse(BaseModel):
    """切片列表响应"""
    total: int
    page: int
    page_size: int
    items: List[KnowledgeChunkResponse]


class KnowledgeSearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)


class KnowledgeSearchResult(BaseModel):
    """单条检索结果"""
    doc_id: int
    chunk_id: int
    title: str = ""
    content: str
    chunk_index: int = 0
    score: float = 0.0
    similarity: float = 0.0


class KnowledgeSearchResponse(BaseModel):
    query: str
    results: List[Dict[str, Any]]
    total: int


class KnowledgeStatsResponse(BaseModel):
    project_id: int
    total_docs: int
    total_chunks: int
