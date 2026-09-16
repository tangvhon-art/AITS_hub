"""
通用资源路由工厂（ResourceRouter / BaseRouter）

基于 core.crud + core.pagination + core.deps + core.audit 组装标准资源路由，
消除各 API 模块中重复的 search / create / get / update / delete + 审计 + 统一响应样板。

统一成功响应格式::

    {"code": 0, "message": "ok", "data": <any>}

search 端点兼容两种模式（向后兼容旧调用方）：
- 请求体不带 page/page_size → 返回全量数组（旧页面直接消费）
- 请求体带 page/page_size   → 返回分页对象 {"items": [...], "total": n, "page": p, "page_size": s}

用法 - 项目级资源::

    from app.core.base_router import ResourceRouter

    resource = ResourceRouter(
        prefix="/api/projects/{project_id}/cases",
        tags=["用例管理"],
        resource_name="用例",
        model=TestCase,
        create_schema=TestCaseCreate,
        update_schema=TestCaseUpdate,
        search_fields=["module", "priority"],
        keyword_fields=["title"],
        order_by=["created_at_desc"],
    )
    router = resource.build()

用法 - 全局资源（不绑定项目）::

    resource = ResourceRouter(
        prefix="/api/prompts",
        tags=["Prompt 管理"],
        resource_name="Prompt",
        model=Prompt,
        create_schema=PromptCreate,
        update_schema=PromptUpdate,
        global_=True,
        search_fields=["category"],
        keyword_fields=["name", "description"],
        order_by=["is_default_desc", "id_desc"],
        before_create=my_before_create,   # 业务钩子（如默认值互斥）
        before_update=my_before_update,   # 业务钩子（如权限校验）
        before_delete=my_before_delete,
    )
    router = resource.build()
    # 自定义端点继续挂在 router 上
    @router.post("/seed-defaults")
    def seed_defaults(...): ...

业务钩子签名（均为同步函数，可抛 HTTPException / BizException）::

    def before_create(db, data, user, request) -> Optional[dict]: ...
    def before_update(db, obj, data, user, request) -> Optional[dict]: ...
    def before_delete(db, obj, user, request) -> None: ...
"""
import logging
from typing import Any, Callable, Dict, List, Optional, Type

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_user, get_project
from app.core.crud import CRUDBase
from app.core.pagination import paginate
from app.core.audit import audit
from app.models.user import User

logger = logging.getLogger(__name__)

# 业务钩子类型
HookFn = Callable[..., Optional[Dict[str, Any]]]


def ok(data: Any = None, message: str = "ok") -> Dict[str, Any]:
    """统一成功响应"""
    return {"code": 0, "message": message, "data": data}


class ResourceRouter:
    """标准资源路由工厂：CRUD + 分页 + 审计 + 统一响应"""

    def __init__(
        self,
        *,
        prefix: str,
        tags: List[str],
        resource_name: str,
        model: Type,
        create_schema: Optional[Type] = None,
        update_schema: Optional[Type] = None,
        response_schema: Optional[Type] = None,
        global_: bool = False,
        crud: Optional[CRUDBase] = None,
        search_fields: Optional[List[str]] = None,
        keyword_fields: Optional[List[str]] = None,
        order_by: Optional[List[str]] = None,
        audit_actions: Optional[Dict[str, str]] = None,
        wrap_response: bool = True,
        before_create: Optional[HookFn] = None,
        before_update: Optional[HookFn] = None,
        before_delete: Optional[HookFn] = None,
    ):
        self.prefix = prefix
        self.tags = tags
        self.resource_name = resource_name
        self.model = model
        self.create_schema = create_schema
        self.update_schema = update_schema
        self.response_schema = response_schema
        self.global_ = global_
        self.crud = crud or CRUDBase(model, resource_name)
        self.search_fields = search_fields or []
        self.keyword_fields = keyword_fields or []
        self.order_by = order_by or ["id_desc"]
        self.audit_actions = audit_actions or {
            "create": "create",
            "update": "update",
            "delete": "delete",
        }
        self.wrap_response = wrap_response
        self.before_create = before_create
        self.before_update = before_update
        self.before_delete = before_delete
        self.router = APIRouter(prefix=prefix, tags=tags)
        self._register()

    # ──────────── 序列化与响应 ────────────

    def _serialize(self, obj: Any) -> Any:
        """ORM / Schema 对象 → 可 JSON 序列化结构"""
        if self.response_schema is not None and obj is not None:
            try:
                return self.response_schema.model_validate(obj).model_dump()
            except Exception:
                pass  # 回退到 jsonable_encoder，避免 from_attributes 配置差异导致失败
        return jsonable_encoder(obj)

    def _serialize_many(self, objs: List[Any]) -> List[Any]:
        return [self._serialize(o) for o in objs]

    def _respond(self, data: Any = None, message: str = "ok") -> Any:
        if self.wrap_response:
            return ok(data=data, message=message)
        return data

    # ──────────── 查询构造 ────────────

    def _build_query(
        self,
        body: Dict[str, Any],
        db: Session,
        project_id: Optional[int],
    ):
        query = db.query(self.model)
        if not self.global_ and project_id is not None and hasattr(self.model, "project_id"):
            query = query.filter(self.model.project_id == project_id)
        # 显式过滤软删除，保证 count 与 items 一致（不依赖全局 ORM 钩子）
        if hasattr(self.model, "is_deleted"):
            query = query.filter(self.model.is_deleted == False)
        # 精确筛选 / 范围筛选（search_fields 支持 "field__gte" / "field__lte" 后缀）
        for field in self.search_fields:
            op = "eq"
            attr = field
            if "__" in field:
                attr, op = field.rsplit("__", 1)
            value = body.get(field)
            if value is None and attr in body:
                value = body.get(attr)
            if value is None or not hasattr(self.model, attr):
                continue
            col = getattr(self.model, attr)
            if op == "gte":
                query = query.filter(col >= value)
            elif op == "lte":
                query = query.filter(col <= value)
            elif op == "gt":
                query = query.filter(col > value)
            elif op == "lt":
                query = query.filter(col < value)
            elif op == "ne":
                query = query.filter(col != value)
            elif op == "like":
                query = query.filter(col.ilike(f"%{value}%"))
            else:
                query = query.filter(col == value)
        # 关键词 ilike 搜索
        keyword = (body.get("keyword") or "").strip()
        if keyword and self.keyword_fields:
            like_clauses = [
                getattr(self.model, f).ilike(f"%{keyword}%")
                for f in self.keyword_fields
                if hasattr(self.model, f)
            ]
            if like_clauses:
                query = query.filter(or_(*like_clauses))
        # 排序：["field_desc", "field_asc"]
        for order in self.order_by:
            if "_" in order:
                field_name, direction = order.rsplit("_", 1)
            else:
                field_name, direction = order, "desc"
            if hasattr(self.model, field_name):
                col = getattr(self.model, field_name)
                query = query.order_by(col.desc() if direction == "desc" else col.asc())
        return query

    def _check_project(self, project_id: Optional[int], db: Session, user: User):
        if not self.global_ and project_id is not None:
            get_project(project_id, db, user)

    def _audit(
        self,
        request: Request,
        db: Session,
        action: str,
        user: User,
        resource_id: Optional[int] = None,
        resource_name: Optional[str] = None,
        detail: Optional[Dict[str, Any]] = None,
        status: str = "success",
        error_message: Optional[str] = None,
    ):
        try:
            audit(
                request,
                db,
                action=action,
                resource_type=self.resource_name,
                resource_id=resource_id,
                resource_name=resource_name,
                detail=detail,
                user=user,
                status=status,
                error_message=error_message,
            )
        except Exception:
            logger.warning("审计日志写入失败: %s", exc_info=True)

    # ──────────── 端点注册 ────────────

    def _register(self):
        router = self.router
        crud = self.crud

        if self.global_:
            # ── 全局资源（无 project_id 路径参数）──

            @router.post("/search")
            def search(
                body: Dict[str, Any] = Body(default={}),
                db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user),
            ):
                query = self._build_query(body, db, None)
                page = body.get("page")
                page_size = body.get("page_size")
                if page is not None and page_size is not None:
                    result = paginate(query, int(page), int(page_size))
                    data = {
                        "items": self._serialize_many(result.items),
                        "total": result.total,
                        "page": result.page,
                        "page_size": result.page_size,
                    }
                else:
                    data = self._serialize_many(query.all())
                return self._respond(data)

            @router.post("", status_code=201)
            def create(
                data: Dict[str, Any] = Body(...),
                request: Request = None,
                db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user),
            ):
                payload = data
                if self.create_schema is not None:
                    payload = self.create_schema.model_validate(data)
                extra = None
                if self.before_create:
                    extra = self.before_create(db, payload, current_user, request) or {}
                obj = crud.create(db, payload, None, current_user.id, **extra)
                self._audit(
                    request, db, self.audit_actions.get("create", "create"),
                    current_user, obj.id, getattr(obj, "name", None),
                    {"data": jsonable_encoder(payload)},
                )
                db.commit()
                db.refresh(obj)
                return self._respond(self._serialize(obj), "创建成功")

            @router.get("/{item_id}")
            def get_item(
                item_id: int,
                db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user),
            ):
                obj = crud.get(db, item_id)
                return self._respond(self._serialize(obj))

            @router.put("/{item_id}")
            def update(
                item_id: int,
                data: Dict[str, Any] = Body(...),
                request: Request = None,
                db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user),
            ):
                obj = crud.get(db, item_id)
                payload = data
                if self.update_schema is not None:
                    payload = self.update_schema.model_validate(data)
                extra = None
                if self.before_update:
                    extra = self.before_update(db, obj, payload, current_user, request) or {}
                obj = crud.update(db, item_id, payload, None, **extra)
                self._audit(
                    request, db, self.audit_actions.get("update", "update"),
                    current_user, item_id, getattr(obj, "name", None),
                    {"data": jsonable_encoder(data)},
                )
                db.commit()
                db.refresh(obj)
                return self._respond(self._serialize(obj), "更新成功")

            @router.delete("/{item_id}")
            def delete(
                item_id: int,
                request: Request = None,
                db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user),
            ):
                obj = crud.get(db, item_id)
                if self.before_delete:
                    self.before_delete(db, obj, current_user, request)
                name = getattr(obj, "name", None)
                crud.soft_delete(db, item_id)
                self._audit(
                    request, db, self.audit_actions.get("delete", "delete"),
                    current_user, item_id, name,
                )
                db.commit()
                return self._respond(None, "删除成功")

        else:
            # ── 项目级资源（路径含 {project_id}）──

            @router.post("/search")
            def search(
                project_id: int,
                body: Dict[str, Any] = Body(default={}),
                db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user),
            ):
                self._check_project(project_id, db, current_user)
                query = self._build_query(body, db, project_id)
                page = body.get("page")
                page_size = body.get("page_size")
                if page is not None and page_size is not None:
                    result = paginate(query, int(page), int(page_size))
                    data = {
                        "items": self._serialize_many(result.items),
                        "total": result.total,
                        "page": result.page,
                        "page_size": result.page_size,
                    }
                else:
                    data = self._serialize_many(query.all())
                return self._respond(data)

            @router.post("", status_code=201)
            def create(
                project_id: int,
                data: Dict[str, Any] = Body(...),
                request: Request = None,
                db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user),
            ):
                self._check_project(project_id, db, current_user)
                payload = data
                if self.create_schema is not None:
                    payload = self.create_schema.model_validate(data)
                extra = None
                if self.before_create:
                    extra = self.before_create(db, payload, current_user, request) or {}
                obj = crud.create(db, payload, project_id, current_user.id, **extra)
                self._audit(
                    request, db, self.audit_actions.get("create", "create"),
                    current_user, obj.id, getattr(obj, "name", None),
                    {"data": jsonable_encoder(payload)},
                )
                db.commit()
                db.refresh(obj)
                return self._respond(self._serialize(obj), "创建成功")

            @router.get("/{item_id}")
            def get_item(
                project_id: int,
                item_id: int,
                db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user),
            ):
                self._check_project(project_id, db, current_user)
                obj = crud.get(db, item_id, project_id)
                return self._respond(self._serialize(obj))

            @router.put("/{item_id}")
            def update(
                project_id: int,
                item_id: int,
                data: Dict[str, Any] = Body(...),
                request: Request = None,
                db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user),
            ):
                self._check_project(project_id, db, current_user)
                obj = crud.get(db, item_id, project_id)
                payload = data
                if self.update_schema is not None:
                    payload = self.update_schema.model_validate(data)
                extra = None
                if self.before_update:
                    extra = self.before_update(db, obj, payload, current_user, request) or {}
                obj = crud.update(db, item_id, payload, project_id, **extra)
                self._audit(
                    request, db, self.audit_actions.get("update", "update"),
                    current_user, item_id, getattr(obj, "name", None),
                    {"data": jsonable_encoder(data)},
                )
                db.commit()
                db.refresh(obj)
                return self._respond(self._serialize(obj), "更新成功")

            @router.delete("/{item_id}")
            def delete(
                project_id: int,
                item_id: int,
                request: Request = None,
                db: Session = Depends(get_db),
                current_user: User = Depends(get_current_user),
            ):
                self._check_project(project_id, db, current_user)
                obj = crud.get(db, item_id, project_id)
                if self.before_delete:
                    self.before_delete(db, obj, current_user, request)
                name = getattr(obj, "name", None)
                crud.soft_delete(db, item_id, project_id)
                self._audit(
                    request, db, self.audit_actions.get("delete", "delete"),
                    current_user, item_id, name,
                )
                db.commit()
                return self._respond(None, "删除成功")

    def build(self) -> APIRouter:
        """返回组装完成的路由对象"""
        return self.router
