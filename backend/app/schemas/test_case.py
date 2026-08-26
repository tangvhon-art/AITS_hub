import json
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, field_validator


class TestCaseStep(BaseModel):
    action: str = ""
    expected: str = ""


class TestCaseBase(BaseModel):
    title: str = Field(..., max_length=200)
    module: str = ""
    priority: str = "P1"
    case_type: str = "functional"
    preconditions: str = ""
    steps: Any = []  # List[TestCaseStep] 或 JSON 字符串
    expected_result: str = ""
    bdd_content: str = ""

    @field_validator("steps", mode="before")
    @classmethod
    def parse_steps(cls, v):
        """数据库中 steps 以 JSON 字符串存储，读取时反序列化为列表"""
        if isinstance(v, str):
            if not v.strip():
                return []
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        return v if isinstance(v, list) else []


class TestCaseCreate(TestCaseBase):
    req_id: Optional[int] = None
    status: Optional[str] = None


class TestCaseUpdate(BaseModel):
    title: Optional[str] = None
    module: Optional[str] = None
    req_id: Optional[int] = None
    priority: Optional[str] = None
    case_type: Optional[str] = None
    preconditions: Optional[str] = None
    steps: Optional[Any] = None
    expected_result: Optional[str] = None
    status: Optional[str] = None
    bdd_content: Optional[str] = None


class TestCaseResponse(TestCaseBase):
    id: int
    project_id: int
    req_id: Optional[int] = None
    status: str
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TestCaseBatchCreate(BaseModel):
    cases: List[TestCaseCreate]
