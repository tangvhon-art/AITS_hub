"""
Agent 任务 Pydantic 模型
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class AgentTaskResponse(BaseModel):
    id: int
    project_id: Optional[int] = None
    agent_type: str
    status: str
    input_params: Dict[str, Any] = {}
    output_result: Dict[str, Any] = {}
    llm_config_id: Optional[int] = None
    token_usage: Dict[str, Any] = {}
    error_message: Optional[str] = ""
    retry_count: int = 0
    created_by: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AgentTaskListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[AgentTaskResponse]


class SupervisorRunRequest(BaseModel):
    requirement_content: str = Field(..., description="需求内容")
    requirement_title: str = Field(default="", description="需求标题")
    generate_count: int = Field(default=10, ge=1, le=50, description="生成用例数量")
    target_url: str = Field(default="", description="执行目标URL")
    llm_config_id: Optional[int] = None
    auto_execute: bool = Field(default=False, description="是否自动执行用例")
    notification_config: Optional[Dict[str, Any]] = None


class ReviewRequest(BaseModel):
    cases: List[Dict[str, Any]] = Field(..., description="待评审用例列表")
    requirement: str = Field(default="", description="原始需求")
    llm_config_id: Optional[int] = None


class BDDGenerateRequest(BaseModel):
    requirement: str = Field(default="", description="需求描述")
    cases: Optional[List[Dict[str, Any]]] = Field(default=None, description="标准用例列表（可选）")
    feature_name: str = Field(default="", description="Feature 名称")
    llm_config_id: Optional[int] = None
