"""
测试计划相关 Schema
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class TestEnvironmentBase(BaseModel):
    name: str = Field(..., max_length=100)
    base_url: str = Field(..., max_length=500)
    description: Optional[str] = ""
    config: Optional[Dict[str, Any]] = {}
    is_default: Optional[bool] = False


class TestEnvironmentCreate(TestEnvironmentBase):
    pass


class TestEnvironmentUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    is_default: Optional[bool] = None
    status: Optional[str] = None


class TestEnvironmentResponse(TestEnvironmentBase):
    id: int
    project_id: int
    status: str
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TestPlanBase(BaseModel):
    name: str = Field(..., max_length=200)
    description: Optional[str] = ""
    priority: Optional[str] = "P2"
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    environment_id: Optional[int] = None
    config: Optional[Dict[str, Any]] = {}
    schedule_type: Optional[str] = "manual"
    schedule_cron: Optional[str] = None


class TestPlanCreate(TestPlanBase):
    case_ids: Optional[List[int]] = []


class TestPlanUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    environment_id: Optional[int] = None
    config: Optional[Dict[str, Any]] = None
    schedule_type: Optional[str] = None
    schedule_cron: Optional[str] = None


class TestPlanCaseUpdate(BaseModel):
    case_ids: List[int]


class TestPlanResponse(TestPlanBase):
    id: int
    project_id: int
    status: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: int
    next_run_time: Optional[datetime] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TestPlanCaseResponse(BaseModel):
    id: int
    plan_id: int
    case_id: int
    sort_order: int
    status: str
    run_id: Optional[int] = None
    case_title: Optional[str] = None
    case_priority: Optional[str] = None

    class Config:
        from_attributes = True


class TestPlanListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[TestPlanResponse]


class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    action: str
    resource_type: str
    resource_id: Optional[int] = None
    resource_name: Optional[str] = None
    detail: Optional[Dict[str, Any]] = {}
    ip_address: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[AuditLogResponse]


class QualityMetricsResponse(BaseModel):
    total_cases: int
    active_cases: int
    total_runs: int
    passed_runs: int
    failed_runs: int
    pass_rate: float
    total_defects: int
    open_defects: int
    resolved_defects: int
    defect_density: float
    avg_duration: float
    total_plans: int
    completed_plans: int


class TrendDataPoint(BaseModel):
    date: str
    value: float


class QualityTrendResponse(BaseModel):
    pass_rate_trend: List[TrendDataPoint]
    defect_trend: List[TrendDataPoint]
    execution_trend: List[TrendDataPoint]


class DefectDistributionItem(BaseModel):
    category: str
    count: int


class QualityDashboardResponse(BaseModel):
    metrics: QualityMetricsResponse
    trend: QualityTrendResponse
    severity_distribution: List[DefectDistributionItem]
    category_distribution: List[DefectDistributionItem]
    module_pass_rate: List[Dict[str, Any]]


class RiskAlertItem(BaseModel):
    id: str
    level: str
    title: str
    description: str
    module: Optional[str] = None
    metric: Optional[str] = None
    current_value: Optional[float] = None
    threshold: Optional[float] = None
    created_at: datetime


class RiskAlertResponse(BaseModel):
    total: int
    high: int
    medium: int
    low: int
    items: List[RiskAlertItem]
