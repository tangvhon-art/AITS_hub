"""Skill Schema"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class SkillCreate(BaseModel):
    name: str = Field(..., max_length=100)
    title: str = Field(..., max_length=200)
    description: Optional[str] = ""
    category: Optional[str] = "other"
    version: Optional[str] = "1.0.0"
    author: Optional[str] = ""
    trigger_config: Dict[str, Any] = Field(default_factory=dict)
    skill_config: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    sort_order: int = 0


class SkillUpdate(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    version: Optional[str] = None
    author: Optional[str] = None
    trigger_config: Optional[Dict[str, Any]] = None
    skill_config: Optional[Dict[str, Any]] = None
    prompts: Optional[Dict[str, str]] = None
    scripts: Optional[Dict[str, str]] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class SkillResponse(BaseModel):
    id: int
    name: str
    title: str
    description: Optional[str] = ""
    category: Optional[str] = "other"
    version: Optional[str] = "1.0.0"
    author: Optional[str] = ""
    source: str = "manual"
    trigger_config: Optional[Dict[str, Any]] = None
    skill_config: Optional[Dict[str, Any]] = None
    prompts: Optional[Dict[str, str]] = None
    scripts: Optional[Dict[str, str]] = None
    icon_path: Optional[str] = ""
    is_active: bool = True
    is_builtin: bool = False
    sort_order: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SkillListResponse(BaseModel):
    total: int
    items: List[SkillResponse]


class SkillMatchRequest(BaseModel):
    message: str
    project_id: Optional[int] = None


class SkillMatchResponse(BaseModel):
    matched: bool
    skill: Optional[SkillResponse] = None
    reason: Optional[str] = ""


class SkillExecuteRequest(BaseModel):
    message: str
    project_id: Optional[int] = None
    user_id: Optional[int] = None


class SkillImportResult(BaseModel):
    id: Optional[int] = None
    name: str
    title: str
    version: str
    source: str = "imported"
    warnings: List[str] = []
    success: bool = True
    message: str = ""
