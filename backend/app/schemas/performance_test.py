from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel, Field


class PerformanceTestBase(BaseModel):
    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    target_type: str = "api_case"
    target_id: Optional[int] = None
    target_url: Optional[str] = None
    users: int = 10
    spawn_rate: int = 1
    duration: int = 60
    headers: dict = Field(default_factory=dict)
    body_template: Optional[str] = None
    variable_config: dict = Field(default_factory=dict)
    data_pool_id: Optional[int] = None
    environment_id: Optional[int] = None


class PerformanceTestCreate(PerformanceTestBase):
    pass


class PerformanceTestUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[int] = None
    target_url: Optional[str] = None
    users: Optional[int] = None
    spawn_rate: Optional[int] = None
    duration: Optional[int] = None
    headers: Optional[dict] = None
    body_template: Optional[str] = None
    variable_config: Optional[dict] = None
    data_pool_id: Optional[int] = None
    environment_id: Optional[int] = None


class PerformanceTestResponse(PerformanceTestBase):
    id: int
    project_id: int
    status: str
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PerformanceTestRunResponse(BaseModel):
    id: int
    test_id: int
    project_id: int
    config_snapshot: Optional[dict] = None
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    total_requests: int = 0
    total_failures: int = 0
    avg_response_time: float = 0.0
    min_response_time: float = 0.0
    max_response_time: float = 0.0
    p50_response_time: float = 0.0
    p95_response_time: float = 0.0
    p99_response_time: float = 0.0
    requests_per_second: float = 0.0
    failure_rate: float = 0.0
    stats_history: Optional[list] = None
    error_summary: Optional[dict] = None
    triggered_by: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PaginatedResponse(BaseModel):
    total: int = 0
    page: int = 1
    page_size: int = 20
    items: List[Any] = []
