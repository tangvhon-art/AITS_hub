"""测试用例集 Schema"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class CaseSuiteCreate(BaseModel):
    name: str = Field(..., max_length=200, description="用例集名称")
    description: str = Field(default="", description="用例集描述")


class CaseSuiteUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200, description="用例集名称")
    description: Optional[str] = Field(None, description="用例集描述")


class CaseSuiteCasesBody(BaseModel):
    """批量关联用例：三种方式可组合（至少提供一种）
    - case_ids: 直接按用例 ID
    - req_ids: 按需求 ID（加入该需求下全部有效用例）
    - module_names: 按模块（加入该模块下全部有效用例）
    """
    case_ids: List[int] = Field(default=[], description="用例ID列表")
    req_ids: List[int] = Field(default=[], description="需求ID列表（加入该需求下的用例）")
    module_names: List[str] = Field(default=[], description="模块名列表（加入该模块下的用例）")


class CaseSuiteResponse(BaseModel):
    id: int
    project_id: int
    name: str
    description: str = ""
    case_count: int = 0
    module_count: int = 0
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CaseSuiteListResponse(BaseModel):
    items: List[CaseSuiteResponse]
    total: int
    page: int
    page_size: int


class CaseExecStatusUpdate(BaseModel):
    """用例集内用例执行状态更新"""
    exec_status: str = Field(..., description="执行状态：pending-待执行，passed-通过，failed-失败，blocked-阻塞，skipped-跳过")
