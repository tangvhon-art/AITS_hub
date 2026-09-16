"""
通用查询构建器

封装 SQLAlchemy Query 的常见操作：精确筛选、模糊搜索、IN 查询、排序、分页。
支持链式调用，减少各模块 list 接口中的重复筛选代码。

用法::

    from app.core.query_builder import QueryBuilder

    query = db.query(Defect).filter(Defect.project_id == project_id)
    result = (
        QueryBuilder(query)
        .filter_eq("status", status, Defect)
        .filter_like("title", keyword, Defect)
        .filter_in("severity", severities, Defect)
        .order("created_at", "desc", Defect)
        .paginate(page=1, page_size=20)
    )
    # result = {"items": [...], "total": 100, "page": 1, "page_size": 20}
"""
from typing import Any, Dict, List, Optional, Type

from sqlalchemy.orm import Query


class QueryBuilder:
    """通用查询构建器，支持筛选、排序、分页、搜索的链式调用。

    Args:
        query: SQLAlchemy Query 对象
    """

    def __init__(self, query: Query):
        self.query = query

    def filter_eq(
        self,
        field: str,
        value: Any,
        model: Type[Any],
    ) -> "QueryBuilder":
        """等于筛选。值为 None 时跳过。

        Args:
            field: 模型字段名
            value: 筛选值
            model: 模型类（用于 getattr 获取列对象）

        Returns:
            self，支持链式调用
        """
        if value is not None and hasattr(model, field):
            self.query = self.query.filter(getattr(model, field) == value)
        return self

    def filter_like(
        self,
        field: str,
        value: Optional[str],
        model: Type[Any],
    ) -> "QueryBuilder":
        """模糊搜索（LIKE %value%）。值为空时跳过。

        Args:
            field: 模型字段名
            value: 搜索关键词
            model: 模型类

        Returns:
            self
        """
        if value and hasattr(model, field):
            self.query = self.query.filter(
                getattr(model, field).like(f"%{value}%")
            )
        return self

    def filter_in(
        self,
        field: str,
        values: Optional[List[Any]],
        model: Type[Any],
    ) -> "QueryBuilder":
        """IN 查询。值为空列表或 None 时跳过。

        Args:
            field: 模型字段名
            values: 值列表
            model: 模型类

        Returns:
            self
        """
        if values and hasattr(model, field):
            self.query = self.query.filter(getattr(model, field).in_(values))
        return self

    def order(
        self,
        field: str,
        direction: str = "desc",
        model: Optional[Type[Any]] = None,
    ) -> "QueryBuilder":
        """排序。

        Args:
            field: 排序字段名
            direction: "desc" 或 "asc"，默认 "desc"
            model: 模型类（为 None 时跳过）

        Returns:
            self
        """
        if model and hasattr(model, field):
            col = getattr(model, field)
            self.query = self.query.order_by(
                col.desc() if direction == "desc" else col.asc()
            )
        return self

    def paginate(
        self,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """执行分页查询。

        Args:
            page: 页码，从 1 开始
            page_size: 每页条数

        Returns:
            字典 {"items": [...], "total": int, "page": int, "page_size": int}
        """
        page = max(1, page)
        page_size = max(1, min(page_size, 200))

        total = self.query.count()
        items = (
            self.query.offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def all(self) -> List[Any]:
        """执行查询，返回所有结果（不分页）。"""
        return self.query.all()

    def first(self) -> Optional[Any]:
        """执行查询，返回第一条结果。"""
        return self.query.first()

    def count(self) -> int:
        """返回查询结果总数。"""
        return self.query.count()
