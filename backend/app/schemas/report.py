"""
报告 Pydantic 模型
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ReportBase(BaseModel):
    title: str = Field(..., max_length=200, description="报告标题")
    report_type: str = Field(default="summary", description="报告类型")


class ReportCreate(ReportBase):
    pass


class ReportGenerateRequest(BaseModel):
    title: Optional[str] = None
    report_type: str = Field(default="full", description="报告类型：summary/execution/defect/full")
    llm_config_id: Optional[int] = None


class ReportUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None


class ReportResponse(ReportBase):
    id: int
    project_id: int
    status: str
    content: str = ""
    summary: Dict[str, Any] = {}
    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    pass_rate: float = 0.0
    total_defects: int = 0
    open_defects: int = 0
    total_runs: int = 0
    avg_duration: float = 0.0
    file_url: str = ""
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ReportListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[ReportResponse]
