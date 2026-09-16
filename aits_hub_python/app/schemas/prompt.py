"""
Prompt 管理 Pydantic Schemas（全局公用）
"""
from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel, Field


class PromptBase(BaseModel):
    name: str = Field(..., max_length=200)
    description: Optional[str] = ""
    category: str = "case_generation"
    system_prompt: str
    user_prompt_template: Optional[str] = ""
    variables: Optional[List[Any]] = []
    is_default: bool = False
    status: str = "active"


class PromptCreate(PromptBase):
    pass


class PromptUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    system_prompt: Optional[str] = None
    user_prompt_template: Optional[str] = None
    variables: Optional[List[Any]] = None
    is_default: Optional[bool] = None
    status: Optional[str] = None


class PromptResponse(PromptBase):
    id: int
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
