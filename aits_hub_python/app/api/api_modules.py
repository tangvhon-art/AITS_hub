"""
接口目录管理 API
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.core.deps import get_current_user, get_project
from app.core.audit import log_audit
from app.models.user import User
from app.models.project import Project
from app.models.api_test import ApiModule, ApiDefinition
from app.schemas.api_test import ApiModuleCreate, ApiModuleUpdate, ApiModuleResponse

router = APIRouter(prefix="/api/projects/{project_id}/api-modules", tags=["接口测试-目录管理"])

def _build_tree(modules: List[ApiModule], parent_id: Optional[int] = None) -> List[dict]:
    """构建目录树"""
    tree = []
    for m in modules:
        if m.parent_id == parent_id:
            node = {
                "id": m.id,
                "project_id": m.project_id,
                "parent_id": m.parent_id,
                "name": m.name,
                "sort_order": m.sort_order,
                "created_by": m.created_by,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "updated_at": m.updated_at.isoformat() if m.updated_at else None,
                "children": _build_tree(modules, m.id),
            }
            tree.append(node)
    return tree

@router.get("", response_model=List[ApiModuleResponse])
def list_modules(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取目录树"""
    get_project(project_id, db, current_user)
    modules = db.query(ApiModule).filter(
        ApiModule.project_id == project_id,
        ApiModule.is_deleted == False,
    ).order_by(ApiModule.sort_order, ApiModule.id).all()
    return _build_tree(modules)

@router.post("", response_model=ApiModuleResponse, status_code=status.HTTP_201_CREATED)
def create_module(
    project_id: int,
    data: ApiModuleCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建目录（最多三级：全部接口为第一级）"""
    get_project(project_id, db, current_user)

    # 层级校验：最多三级
    # parent_id=null → 二级分组（全部接口下）→ OK
    # parent_id=X 且 X.parent_id=null → 三级分组 → OK
    # parent_id=X 且 X.parent_id 不为 null → 超过三级 → 拒绝
    if data.parent_id is not None:
        parent = db.query(ApiModule).filter(
            ApiModule.id == data.parent_id,
            ApiModule.project_id == project_id,
        ).first()
        if not parent:
            raise HTTPException(status_code=400, detail="父分组不存在")
        if parent.parent_id is not None:
            raise HTTPException(status_code=400, detail="接口分组最多支持三级，不允许在三级分组下创建子分组")

    module = ApiModule(
        project_id=project_id,
        parent_id=data.parent_id,
        name=data.name,
        sort_order=data.sort_order,
        created_by=current_user.id,
    )
    db.add(module)
    db.flush()
    log_audit(
        db, action="create", resource_type="project",
        resource_id=module.id, resource_name=module.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "module_name": module.name, "type": "api_module"},
    )
    db.commit()
    db.refresh(module)
    return module

@router.put("/{module_id}", response_model=ApiModuleResponse)
def update_module(
    project_id: int,
    module_id: int,
    data: ApiModuleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新目录"""
    get_project(project_id, db, current_user)
    module = db.query(ApiModule).filter(
        ApiModule.id == module_id, ApiModule.project_id == project_id
    ).first()
    if not module:
        raise HTTPException(status_code=404, detail="目录不存在")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(module, key, value)

    log_audit(
        db, action="update", resource_type="project",
        resource_id=module.id, resource_name=module.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "module_name": module.name, "type": "api_module"},
    )
    db.commit()
    db.refresh(module)
    return module

@router.delete("/{module_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_module(
    project_id: int,
    module_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除目录（软删，同时删除子目录和接口）"""
    get_project(project_id, db, current_user)
    module = db.query(ApiModule).filter(
        ApiModule.id == module_id, ApiModule.project_id == project_id
    ).first()
    if not module:
        raise HTTPException(status_code=404, detail="目录不存在")

    # 收集所有子目录ID
    all_module_ids = [module_id]
    def _collect_children(parent_id: int):
        children = db.query(ApiModule).filter(ApiModule.parent_id == parent_id).all()
        for child in children:
            all_module_ids.append(child.id)
            _collect_children(child.id)
    _collect_children(module_id)

    # 软删接口定义
    db.query(ApiDefinition).filter(
        ApiDefinition.project_id == project_id,
        ApiDefinition.module_id.in_(all_module_ids),
    ).update({ApiDefinition.is_deleted: True}, synchronize_session=False)

    # 软删目录
    db.query(ApiModule).filter(ApiModule.id.in_(all_module_ids)).update(
        {ApiModule.is_deleted: True}, synchronize_session=False
    )

    log_audit(
        db, action="delete", resource_type="project",
        resource_id=module.id, resource_name=module.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "module_name": module.name, "type": "api_module"},
    )
    db.commit()
