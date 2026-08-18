"""MCP 连接器 Schema"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class MCPConnectorCreate(BaseModel):
    name: str = Field(..., max_length=100)
    description: Optional[str] = ""
    transport: str = Field("sse", description="sse/stdio/http")
    url: Optional[str] = ""
    command: Optional[str] = ""
    args: Optional[List[str]] = None
    env_vars: Optional[Dict[str, str]] = None
    is_active: bool = True


class MCPConnectorUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    transport: Optional[str] = None
    url: Optional[str] = None
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env_vars: Optional[Dict[str, str]] = None
    is_active: Optional[bool] = None


class MCPConnectorResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = ""
    transport: str
    url: Optional[str] = ""
    command: Optional[str] = ""
    args: Optional[List[str]] = None
    env_vars: Optional[Dict[str, str]] = None
    status: str
    tools_count: int = 0
    tools_list: Optional[List[Dict[str, Any]]] = None
    last_connected_at: Optional[datetime] = None
    error_message: Optional[str] = ""
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MCPConnectorListResponse(BaseModel):
    total: int
    items: List[MCPConnectorResponse]


class MCPConnectResult(BaseModel):
    success: bool
    message: str
    tools_count: int = 0
    tools: List[Dict[str, Any]] = []
