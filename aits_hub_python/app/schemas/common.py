"""
通用 Schema 定义

提供跨模块复用的通用响应模型，如泛型分页响应。
"""
from typing import Generic, List, TypeVar, Optional, Any
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """
    泛型分页响应。

    用法:
        from app.schemas.common import PaginatedResponse

        @router.get("/items", response_model=PaginatedResponse[ItemSchema])
        def list_items(...):
            ...
    """
    items: List[T] = Field(default_factory=list, description="当前页数据列表")
    total: int = Field(0, description="总记录数")
    page: int = Field(1, description="当前页码")
    page_size: int = Field(20, description="每页条数")
    total_pages: int = Field(0, description="总页数")

    model_config = {"from_attributes": False}


class ApiResponse(BaseModel, Generic[T]):
    """通用 API 响应包装"""
    code: int = Field(0, description="业务状态码，0 表示成功")
    message: str = Field("success", description="提示信息")
    data: Optional[T] = Field(None, description="响应数据")


class SuccessResponse(ApiResponse[T]):
    """成功响应，code 固定为 0"""
    code: int = Field(0, description="业务状态码，0 表示成功")
    message: str = Field("success", description="提示信息")


class ErrorResponse(BaseModel):
    """错误响应格式"""
    code: int = Field(..., description="业务错误码，非 0 表示错误")
    message: str = Field(..., description="面向用户的错误描述")
    detail: Optional[Any] = Field(None, description="额外详情（字符串、字典或列表）")
