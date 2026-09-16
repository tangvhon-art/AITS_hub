from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel


class ExecutionRequest(BaseModel):
    instruction: str
    target_url: str = ""
    case_id: Optional[int] = None
    llm_config_id: Optional[int] = None
    headless: bool = True


class TestRunResponse(BaseModel):
    id: int
    project_id: int
    case_id: Optional[int] = None
    status: str
    actual_result: str
    execution_log: Any = []
    screenshot_url: str
    error_message: str
    duration: float
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
