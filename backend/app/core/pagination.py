"""
分页工具

提供统一的分页查询函数，消除各路由中重复的 offset/limit/total 样板代码。
"""
from typing import Any, Optional, Sequence, TypeVar, Generic
from fastapi import Query
from pydantic import BaseModel
from sqlalchemy.orm import Query as SQLAQuery
from sqlalchemy import func

T = TypeVar("T")


class PageParams:
    """
    分页参数依赖注入。

    用法:
        from fastapi import Depends
        from app.core.pagination import PageParams

        @router.get("/items")
        def list_items(page: PageParams = Depends(), db: Session = Depends(get_db)):
            query = db.query(Model)
            result = paginate(query, page.page, page.page_size)
            return result
    """

    def __init__(
        self,
        page: int = Query(1, ge=1, description="页码，从 1 开始"),
        page_size: int = Query(20, ge=1, le=200, description="每页条数，最大 200"),
    ):
        self.page = page
        self.page_size = page_size


class Page(Generic[T]):
    """分页结果"""

    def __init__(
        self,
        items: Sequence[T],
        total: int,
        page: int,
        page_size: int,
    ):
        self.items = list(items)
        self.total = total
        self.page = page
        self.page_size = page_size
        self.total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

    def to_dict(self) -> dict:
        """转换为前端期望的字典格式"""
        return {
            "items": self.items,
            "total": self.total,
            "page": self.page,
            "page_size": self.page_size,
            "total_pages": self.total_pages,
        }


def paginate(
    query: SQLAQuery,
    page: int = 1,
    page_size: int = 20,
) -> Page:
    """
    对 SQLAlchemy Query 执行分页查询。

    Args:
        query: SQLAlchemy Query 对象（未调用 all()）
        page: 页码，从 1 开始
        page_size: 每页条数

    Returns:
        Page 对象，包含 items/total/page/page_size/total_pages
    """
    page = max(1, page)
    page_size = max(1, min(page_size, 200))

    total = query.with_entities(func.count()).order_by(None).scalar() or 0
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return Page(items=items, total=total, page=page, page_size=page_size)
