from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class AutomationScriptBase(BaseModel):
    name: Optional[str] = Field(None, max_length=200, description="脚本名称（AI生成模式下可不填，由AI自动生成）")
    description: Optional[str] = ""
    case_id: Optional[int] = None
    script_content: str = ""
    script_type: Optional[str] = "manual"
    target_url: Optional[str] = ""
    language: Optional[str] = "python"
    status: Optional[str] = "active"
    tags: Optional[str] = ""


class AutomationScriptCreate(AutomationScriptBase):
    ai_generate: bool = False
    llm_config_id: Optional[int] = None


class AutomationScriptUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    case_id: Optional[int] = None
    script_content: Optional[str] = None
    script_type: Optional[str] = None
    target_url: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[str] = None


class AutomationScriptResponse(BaseModel):
    id: int
    project_id: int
    name: str
    description: Optional[str] = ""
    case_id: Optional[int] = None
    source_run_id: Optional[int] = None
    script_content: Optional[str] = ""
    script_type: Optional[str] = ""
    target_url: Optional[str] = ""
    language: Optional[str] = ""
    status: Optional[str] = ""
    version: Optional[int] = 1
    tags: Optional[str] = ""
    last_run_status: Optional[str] = None
    last_run_at: Optional[datetime] = None
    total_runs: Optional[int] = 0
    pass_count: Optional[int] = 0
    fail_count: Optional[int] = 0
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ScriptRunRequest(BaseModel):
    headless: bool = True
    params: Optional[Dict[str, Any]] = None
    auto_fix: bool = True  # 执行失败时是否自动调用AI修复脚本
    max_retries: int = 2  # 最大自动修复重试次数
