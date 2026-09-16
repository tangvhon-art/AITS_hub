"""
系统定时任务（sys_crontab）Pydantic Schema
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class CrontabBase(BaseModel):
    name: str = Field(..., max_length=200)
    task: str = Field(..., max_length=255)
    args: Optional[List[Any]] = []
    kwargs: Optional[Dict[str, Any]] = {}
    queue: str = "default"
    schedule_type: str = "interval"
    every_seconds: Optional[int] = None
    minute: Optional[str] = "*"
    hour: Optional[str] = "*"
    day_of_week: Optional[str] = "*"
    day_of_month: Optional[str] = "*"
    month_of_year: Optional[str] = "*"
    enabled: bool = True
    description: Optional[str] = ""


class CrontabCreate(CrontabBase):
    pass


class CrontabUpdate(BaseModel):
    name: Optional[str] = None
    task: Optional[str] = None
    args: Optional[List[Any]] = None
    kwargs: Optional[Dict[str, Any]] = None
    queue: Optional[str] = None
    schedule_type: Optional[str] = None
    every_seconds: Optional[int] = None
    minute: Optional[str] = None
    hour: Optional[str] = None
    day_of_week: Optional[str] = None
    day_of_month: Optional[str] = None
    month_of_year: Optional[str] = None
    enabled: Optional[bool] = None
    description: Optional[str] = None


class CrontabResponse(BaseModel):
    id: int
    name: str
    task: str
    args: Optional[List[Any]] = []
    kwargs: Optional[Dict[str, Any]] = {}
    queue: str = "default"
    schedule_type: str = "interval"
    every_seconds: Optional[int] = None
    minute: Optional[str] = "*"
    hour: Optional[str] = "*"
    day_of_week: Optional[str] = "*"
    day_of_month: Optional[str] = "*"
    month_of_year: Optional[str] = "*"
    enabled: bool = True
    last_run_at: Optional[datetime] = None
    total_run_count: int = 0
    description: Optional[str] = ""
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CrontabListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[CrontabResponse]
