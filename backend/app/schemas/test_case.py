from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field


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


class TestCaseCreate(TestCaseBase):
    req_id: Optional[int] = None


class TestCaseUpdate(BaseModel):
    title: Optional[str] = None
    module: Optional[str] = None
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
