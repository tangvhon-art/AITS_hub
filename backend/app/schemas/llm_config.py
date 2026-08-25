from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class LLMConfigBase(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    name: str = Field(..., max_length=100)
    provider: str = Field(..., description="openai_compatible / anthropic / ollama")
    base_url: str = ""
    api_key: str = ""
    model_name: str = Field(..., max_length=100)
    max_tokens: int = 4096
    temperature: float = 0.7
    streaming: bool = False
    is_default: bool = False
    status: str = "active"
    priority: int = 0
    description: str = ""


class LLMConfigCreate(LLMConfigBase):
    pass


class LLMConfigUpdate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    name: Optional[str] = None
    provider: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    streaming: Optional[bool] = None
    is_default: Optional[bool] = None
    status: Optional[str] = None
    priority: Optional[int] = None
    description: Optional[str] = None


class LLMConfigResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=(), from_attributes=True)

    id: int
    name: str
    provider: str
    base_url: str
    model_name: str
    max_tokens: int
    temperature: float
    streaming: bool = False
    is_default: bool
    status: str
    priority: int
    description: str
    has_api_key: bool = False
    created_at: datetime
    updated_at: datetime


class LLMConfigTestRequest(BaseModel):
    prompt: str = "你好，请回复一句话确认连接正常。"
