from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class TestDataPoolBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., max_length=200)
    description: Optional[str] = None
    data_type: str = "static"
    schema_config: List[dict] = Field(default_factory=list, alias="schema")
    data: List[dict] = Field(default_factory=list)
    generator_config: dict = Field(default_factory=dict)
    environment_id: Optional[int] = None


class TestDataPoolCreate(TestDataPoolBase):
    pass


class TestDataPoolUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: Optional[str] = None
    description: Optional[str] = None
    data_type: Optional[str] = None
    schema_config: Optional[List[dict]] = Field(default=None, alias="schema")
    data: Optional[List[dict]] = None
    generator_config: Optional[dict] = None
    environment_id: Optional[int] = None


class TestDataPoolResponse(TestDataPoolBase):
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    id: int
    project_id: int
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class EnvironmentVariableBase(BaseModel):
    key: str = Field(..., max_length=200)
    value: Optional[str] = None
    description: Optional[str] = None
    is_sensitive: bool = False


class EnvironmentVariableCreate(EnvironmentVariableBase):
    pass


class EnvironmentVariableUpdate(BaseModel):
    value: Optional[str] = None
    description: Optional[str] = None
    is_sensitive: Optional[bool] = None


class EnvironmentVariableResponse(EnvironmentVariableBase):
    id: int
    project_id: int
    environment_id: int

    class Config:
        from_attributes = True


class PaginatedResponse(BaseModel):
    total: int = 0
    page: int = 1
    page_size: int = 20
    items: List[Any] = []
