from datetime import datetime
from typing import Optional, Any, Dict
from pydantic import BaseModel


class AgentTaskResponse(BaseModel):
    id: int
    project_id: Optional[int] = None
    agent_type: str
    status: str
    input_params: Dict[str, Any] = {}
    output_result: Dict[str, Any] = {}
    llm_config_id: Optional[int] = None
    token_usage: Dict[str, Any] = {}
    error_message: str
    retry_count: int
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True
