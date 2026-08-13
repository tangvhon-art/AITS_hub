from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ============ 编排套件 ============
class AutomationSuiteBase(BaseModel):
    name: str = Field(..., max_length=200)
    description: Optional[str] = ""
    plan_id: Optional[int] = None
    environment_id: Optional[int] = None
    status: Optional[str] = "active"
    schedule_type: Optional[str] = "manual"
    schedule_cron: Optional[str] = ""
    config: Optional[Dict[str, Any]] = None


class AutomationSuiteCreate(AutomationSuiteBase):
    pass


class AutomationSuiteUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    plan_id: Optional[int] = None
    environment_id: Optional[int] = None
    status: Optional[str] = None
    schedule_type: Optional[str] = None
    schedule_cron: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class AutomationSuiteResponse(BaseModel):
    id: int
    project_id: int
    name: str
    description: Optional[str] = ""
    plan_id: Optional[int] = None
    environment_id: Optional[int] = None
    status: Optional[str] = ""
    total_steps: Optional[int] = 0
    schedule_type: Optional[str] = ""
    schedule_cron: Optional[str] = ""
    next_run_time: Optional[datetime] = None
    last_run_status: Optional[str] = None
    last_run_at: Optional[datetime] = None
    config: Optional[Dict[str, Any]] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============ 编排步骤 ============
class SuiteStepBase(BaseModel):
    step_name: str
    script_id: Optional[int] = None
    case_id: Optional[int] = None
    sort_order: Optional[int] = 0
    step_type: Optional[str] = "script"
    params: Optional[Dict[str, Any]] = None
    continue_on_failure: Optional[bool] = False
    max_retries: Optional[int] = 0
    timeout: Optional[int] = 300


class SuiteStepCreate(SuiteStepBase):
    pass


class SuiteStepUpdate(BaseModel):
    step_name: Optional[str] = None
    script_id: Optional[int] = None
    case_id: Optional[int] = None
    sort_order: Optional[int] = None
    step_type: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    continue_on_failure: Optional[bool] = None
    max_retries: Optional[int] = None
    timeout: Optional[int] = None


class SuiteStepResponse(BaseModel):
    id: int
    suite_id: int
    step_name: str
    script_id: Optional[int] = None
    case_id: Optional[int] = None
    sort_order: Optional[int] = 0
    step_type: Optional[str] = ""
    params: Optional[Dict[str, Any]] = None
    continue_on_failure: Optional[bool] = False
    max_retries: Optional[int] = 0
    timeout: Optional[int] = 300
    status: Optional[str] = "pending"
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SuiteStepsBatchUpdate(BaseModel):
    steps: List[SuiteStepBase]


# ============ 编排执行记录 ============
class SuiteRunResponse(BaseModel):
    id: int
    suite_id: int
    project_id: int
    plan_id: Optional[int] = None
    status: Optional[str] = ""
    total_steps: Optional[int] = 0
    passed_steps: Optional[int] = 0
    failed_steps: Optional[int] = 0
    skipped_steps: Optional[int] = 0
    pass_rate: Optional[float] = 0.0
    total_duration: Optional[float] = 0.0
    trigger_type: Optional[str] = ""
    executed_by: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = ""
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SuiteRunResultResponse(BaseModel):
    id: int
    suite_run_id: int
    step_id: Optional[int] = None
    script_id: Optional[int] = None
    case_id: Optional[int] = None
    run_id: Optional[int] = None
    step_name: Optional[str] = ""
    sort_order: Optional[int] = 0
    status: Optional[str] = ""
    duration: Optional[float] = 0.0
    retry_count: Optional[int] = 0
    error_message: Optional[str] = ""
    screenshot_url: Optional[str] = ""
    execution_log: Optional[str] = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SuiteExecuteRequest(BaseModel):
    headless: bool = True
    trigger_type: Optional[str] = "manual"
