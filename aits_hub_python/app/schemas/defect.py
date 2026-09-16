"""
缺陷 Pydantic 模型
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class DefectBase(BaseModel):
    title: str = Field(..., max_length=200, description="缺陷标题")
    description: str = Field(default="", description="缺陷描述")
    severity: str = Field(default="major", description="严重程度：blocker/critical/major/minor/trivial")
    priority: str = Field(default="P2", description="优先级：P0/P1/P2/P3")
    status: Optional[str] = Field(default="open", description="状态")
    root_cause: str = Field(default="", description="根因分析")
    root_cause_category: str = Field(default="", description="根因分类")
    reproduce_steps: str = Field(default="", description="复现步骤")
    expected_result: str = Field(default="", description="预期结果")
    actual_result: str = Field(default="", description="实际结果")
    screenshot_url: str = Field(default="", description="截图路径")
    error_log: str = Field(default="", description="错误日志")
    run_id: Optional[int] = Field(default=None, description="关联执行记录ID")
    case_id: Optional[int] = Field(default=None, description="关联用例ID")
    assignee_id: Optional[int] = Field(default=None, description="指派给")
    version_id: Optional[int] = Field(default=None, description="所属版本ID")


class DefectCreate(DefectBase):
    pass


class DefectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    root_cause: Optional[str] = None
    root_cause_category: Optional[str] = None
    reproduce_steps: Optional[str] = None
    expected_result: Optional[str] = None
    actual_result: Optional[str] = None
    screenshot_url: Optional[str] = None
    error_log: Optional[str] = None
    assignee_id: Optional[int] = None
    version_id: Optional[int] = None


class DefectResponse(DefectBase):
    id: int
    project_id: int
    version_id: Optional[int] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DefectListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[DefectResponse]
