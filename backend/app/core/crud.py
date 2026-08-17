"""
通用 CRUD 基类

消除各模块 API 中重复的增删改查样板代码。
支持项目级资源（project_id 过滤）和全局资源（project_id=None）。

用法::

    from app.core.crud import CRUDBase
    from app.models.defect import Defect
    from app.schemas.defect import DefectCreate, DefectUpdate

    defect_crud = CRUDBase(Defect, "缺陷")

    # 在路由中
    defect = defect_crud.get(db, defect_id, project_id)
    defect = defect_crud.create(db, data, project_id, current_user.id)
    defect = defect_crud.update(db, defect_id, data, project_id)
    defect_crud.soft_delete(db, defect_id, project_id)
    result = defect_crud.list(db, project_id, page=1, page_size=20)
"""
from typing import Any, Dict, Generic, Optional, Type, TypeVar

from fastapi import HTTPException
from sqlalchemy.orm import Session

ModelType = TypeVar("ModelType")
CreateSchemaType = TypeVar("CreateSchemaType")
UpdateSchemaType = TypeVar("UpdateSchemaType")


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """通用 CRUD 基类，消除各模块重复的增删改查代码。

    Args:
        model: SQLAlchemy 模型类
        resource_name: 资源中文名称，用于 404 错误提示
        by_alias: create/update 时是否使用 schema 字段别名（处理 schema_config->schema 等映射）
    """

    def __init__(
        self,
        model: Type[ModelType],
        resource_name: str = "资源",
        by_alias: bool = False,
    ):
        self.model = model
        self.resource_name = resource_name
        self.by_alias = by_alias

    def get(
        self,
        db: Session,
        id: int,
        project_id: Optional[int] = None,
    ) -> ModelType:
        """按 ID 查询，不存在抛 404。

        Args:
            db: 数据库会话
            id: 资源 ID
            project_id: 项目 ID（全局资源传 None）

        Returns:
            模型实例

        Raises:
            HTTPException: 404 资源不存在
        """
        query = db.query(self.model).filter(self.model.id == id)
        if project_id is not None and hasattr(self.model, "project_id"):
            query = query.filter(self.model.project_id == project_id)
        obj = query.first()
        if not obj:
            raise HTTPException(status_code=404, detail=f"{self.resource_name}不存在")
        return obj

    def list(
        self,
        db: Session,
        project_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = "id_desc",
    ) -> Dict[str, Any]:
        """分页查询，自动过滤软删除（依赖全局 ORM 钩子）。

        Args:
            db: 数据库会话
            project_id: 项目 ID（全局资源传 None）
            page: 页码，从 1 开始
            page_size: 每页条数
            filters: 精确筛选字典 {字段名: 值}，值为 None 时跳过
            order_by: 排序字段，支持 "id_desc" / "id_asc" / "field_desc" / "field_asc"

        Returns:
            字典 {"items": [...], "total": int, "page": int, "page_size": int}
        """
        query = db.query(self.model)
        if project_id is not None and hasattr(self.model, "project_id"):
            query = query.filter(self.model.project_id == project_id)

        if filters:
            for key, value in filters.items():
                if value is not None and hasattr(self.model, key):
                    query = query.filter(getattr(self.model, key) == value)

        total = query.count()

        if order_by:
            if "_" in order_by:
                field_name, direction = order_by.rsplit("_", 1)
            else:
                field_name, direction = order_by, "desc"
            if hasattr(self.model, field_name):
                col = getattr(self.model, field_name)
                query = query.order_by(col.desc() if direction == "desc" else col.asc())

        items = query.offset((page - 1) * page_size).limit(page_size).all()
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def create(
        self,
        db: Session,
        obj_in: CreateSchemaType,
        project_id: Optional[int] = None,
        created_by: Optional[int] = None,
        **extra: Any,
    ) -> ModelType:
        """创建记录，自动填充 project_id 和 created_by。

        Args:
            db: 数据库会话
            obj_in: Pydantic Create schema
            project_id: 项目 ID（模型有 project_id 字段时自动填充）
            created_by: 创建人 ID（模型有 created_by 字段时自动填充）
            **extra: 额外字段，覆盖 schema 中的值

        Returns:
            创建后的模型实例（已 refresh）
        """
        obj_data = obj_in.model_dump(exclude_unset=True, by_alias=self.by_alias)
        if project_id is not None and hasattr(self.model, "project_id"):
            obj_data["project_id"] = project_id
        if created_by is not None and hasattr(self.model, "created_by"):
            obj_data["created_by"] = created_by
        if extra:
            obj_data.update(extra)

        db_obj = self.model(**obj_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(
        self,
        db: Session,
        id: int,
        obj_in: UpdateSchemaType,
        project_id: Optional[int] = None,
        **extra: Any,
    ) -> ModelType:
        """更新记录，自动 404 检查。

        Args:
            db: 数据库会话
            id: 资源 ID
            obj_in: Pydantic Update schema
            project_id: 项目 ID（用于 404 查询时的范围限定）
            **extra: 额外字段，覆盖 schema 中的值

        Returns:
            更新后的模型实例（已 refresh）
        """
        db_obj = self.get(db, id, project_id)
        update_data = obj_in.model_dump(exclude_unset=True, by_alias=self.by_alias)
        if extra:
            update_data.update(extra)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def soft_delete(
        self,
        db: Session,
        id: int,
        project_id: Optional[int] = None,
    ) -> None:
        """软删除记录，自动 404 检查。

        依赖模型具有 soft_delete() 方法（由 SoftDeleteMixin 提供）。

        Args:
            db: 数据库会话
            id: 资源 ID
            project_id: 项目 ID（用于 404 查询时的范围限定）
        """
        db_obj = self.get(db, id, project_id)
        if hasattr(db_obj, "soft_delete"):
            db_obj.soft_delete()
        db.commit()
