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
    feature_split_status: str = "pending"
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
    feature_ids: Optional[List[int]] = None
    version_id: Optional[int] = None
    llm_config_id: Optional[int] = None
    prompt_id: Optional[int] = None
    backend: Optional[str] = Field(default=None, description="页面选择的执行后端 local/workflow，不传则跟随系统配置")


class RequirementGenerateRequest(BaseModel):
    description: str = Field(..., description="用户输入的需求简要描述")
    llm_config_id: Optional[int] = None
    prompt_id: Optional[int] = None
    version_id: Optional[int] = None
    backend: Optional[str] = Field(default=None, description="页面选择的执行后端 local/workflow，不传则跟随系统配置")


class FeatureSplitRequest(BaseModel):
    """功能点拆分请求（支持页面选择执行后端）"""
    backend: Optional[str] = Field(default=None, description="页面选择的执行后端 local/workflow，不传则跟随系统配置")
    llm_config_id: Optional[int] = None


# ── 功能点 ──────────────────────────────────────────────

class RequirementFeatureBase(BaseModel):
    module_name: str = Field(..., max_length=200)
    module_desc: str = ""
    name: str = Field(..., max_length=200)
    description: str = ""
    priority: str = "P1"
    design_methods: List[str] = []
    preconditions: str = ""
    sort_order: int = 0


class RequirementFeatureCreate(RequirementFeatureBase):
    pass


class RequirementFeatureUpdate(BaseModel):
    module_name: Optional[str] = None
    module_desc: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    design_methods: Optional[List[str]] = None
    preconditions: Optional[str] = None
    sort_order: Optional[int] = None


class RequirementFeatureResponse(RequirementFeatureBase):
    id: int
    requirement_id: int
    project_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FeatureModuleGroup(BaseModel):
    """按模块分组的功能点"""
    module_name: str
    module_desc: str = ""
    features: List[RequirementFeatureResponse] = []
