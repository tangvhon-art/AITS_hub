"""
版本管理 Pydantic 模型
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class VersionBase(BaseModel):
    name: str = Field(..., max_length=100, description="版本名称")
    description: Optional[str] = ""
    status: Optional[str] = "draft"
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    released_at: Optional[datetime] = None


class VersionCreate(VersionBase):
    pass


class VersionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    released_at: Optional[datetime] = None


class VersionResponse(VersionBase):
    id: int
    project_id: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VersionListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[VersionResponse]
