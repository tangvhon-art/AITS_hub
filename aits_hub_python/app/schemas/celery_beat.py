"""
任务调度管理（Celery Beat 可视化管理）Pydantic Schema

调度值统一为单一表达式 schedule_expr：
- interval 类型：正整数秒数字符串（如 "60"）
- cron 类型：5 段标准 cron 表达式（如 "0 2 * * *"，顺序 分 时 日 月 周）
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class BeatTaskCreate(BaseModel):
    name: str = Field(..., max_length=200)
    task_key: str = Field(..., max_length=100)
    task: str = Field(..., max_length=255)
    schedule_type: str = "interval"
    schedule_expr: str = Field(..., max_length=200)
    queue: str = "default"
    args: Optional[List[Any]] = []
    kwargs: Optional[Dict[str, Any]] = {}
    description: Optional[str] = ""
    enabled: bool = True


class BeatTaskUpdate(BaseModel):
    id: int
    name: Optional[str] = None
    task_key: Optional[str] = None
    task: Optional[str] = None
    schedule_type: Optional[str] = None
    schedule_expr: Optional[str] = None
    queue: Optional[str] = None
    args: Optional[List[Any]] = None
    kwargs: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None


class BeatTaskStatus(BaseModel):
    id: int
    enabled: bool


class BeatTaskRunOnce(BaseModel):
    id: int


class BeatTaskResponse(BaseModel):
    id: int
    name: str
    task_key: Optional[str] = None
    task: str
    schedule_type: str
    schedule_expr: str = ""
    queue: str
    args: Optional[List[Any]] = []
    kwargs: Optional[Dict[str, Any]] = {}
    description: Optional[str] = ""
    enabled: bool = True
    last_run_at: Optional[datetime] = None
    total_run_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BeatTaskListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[BeatTaskResponse]


class BeatTaskLogResponse(BaseModel):
    id: int
    task_name: str
    task_key: Optional[str] = None
    task_id: str
    args: Optional[List[Any]] = []
    kwargs: Optional[Dict[str, Any]] = {}
    queue: Optional[str] = "default"
    state: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    exception: Optional[str] = None
    traceback: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BeatTaskLogListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[BeatTaskLogResponse]
