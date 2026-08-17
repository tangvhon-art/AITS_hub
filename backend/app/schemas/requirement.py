from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class RequirementBase(BaseModel):
    title: str = Field(..., max_length=200)
    content: str = ""
    source: str = "manual"
    source_url: str = ""
    version_id: Optional[int] = None


class RequirementCreate(RequirementBase):
    pass


class RequirementUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None
    version_id: Optional[int] = None


class RequirementResponse(RequirementBase):
    id: int
    project_id: int
    status: str
    version_id: Optional[int] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CaseGenerateRequest(BaseModel):
    requirement_id: Optional[int] = None
    content: str = ""
    count: int = 10
    llm_config_id: Optional[int] = None
    prompt_id: Optional[int] = None


class RequirementGenerateRequest(BaseModel):
    description: str = Field(..., description="用户输入的需求简要描述")
    llm_config_id: Optional[int] = None
    prompt_id: Optional[int] = None
    version_id: Optional[int] = None
