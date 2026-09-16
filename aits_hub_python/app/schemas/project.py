from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = ""


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class ProjectResponse(ProjectBase):
    id: int
    owner_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectMemberResponse(BaseModel):
    id: int
    project_id: int
    user_id: int
    username: str
    full_name: str = ""
    email: str
    role: str
    joined_at: datetime

    class Config:
        from_attributes = True


class ProjectMemberCreate(BaseModel):
    user_id: int
    role: str = "tester"


class ProjectMemberUpdate(BaseModel):
    role: str
