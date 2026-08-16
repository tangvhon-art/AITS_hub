from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel, Field


class CoverageConfigBase(BaseModel):
    excluded_paths: List[str] = Field(default_factory=list)
    excluded_methods: List[str] = Field(default_factory=list)
    critical_scenario_ids: List[int] = Field(default_factory=list)
    version_id: Optional[int] = None


class CoverageConfigUpdate(BaseModel):
    excluded_paths: Optional[List[str]] = None
    excluded_methods: Optional[List[str]] = None
    critical_scenario_ids: Optional[List[int]] = None
    version_id: Optional[int] = None


class CoverageConfigResponse(CoverageConfigBase):
    id: int
    project_id: int

    class Config:
        from_attributes = True


class CoverageSnapshotResponse(BaseModel):
    id: int
    project_id: int
    version_id: Optional[int] = None
    total_apis: int = 0
    covered_apis: int = 0
    api_coverage_rate: float = 0.0
    uncovered_apis: Optional[list] = None
    total_scenarios: int = 0
    covered_scenarios: int = 0
    scenario_coverage_rate: float = 0.0
    total_cases: int = 0
    cases_with_api: int = 0
    coverage_matrix: Optional[dict] = None
    calculated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
