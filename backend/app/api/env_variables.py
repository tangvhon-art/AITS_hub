import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_user, get_project
from app.core.audit import log_audit
from app.models.user import User
from app.models.test_data_pool import EnvironmentVariableOverride
from app.schemas.test_data_pool import (
    EnvironmentVariableCreate, EnvironmentVariableUpdate, EnvironmentVariableResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/projects/{project_id}/environments",
    tags=["环境变量管理"],
)


@router.get("/{env_id}/variables")
def list_variables(
    project_id: int,
    env_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project(project_id, db, current_user)
    from app.services.environment_manager import EnvironmentManager
    mgr = EnvironmentManager(db)
    return mgr.get_variables(project_id, env_id)


@router.post("/{env_id}/variables")
def upsert_variable(
    project_id: int,
    env_id: int,
    data: EnvironmentVariableCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project(project_id, db, current_user)
    from app.services.environment_manager import EnvironmentManager
    mgr = EnvironmentManager(db)
    result = mgr.upsert_variable(
        project_id=project_id,
        environment_id=env_id,
        key=data.key,
        value=data.value,
        description=data.description,
        is_sensitive=data.is_sensitive,
    )
    log_audit(
        db, action="upsert", resource_type="env_variable",
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "env_id": env_id, "key": data.key},
    )
    db.commit()
    return result


@router.delete("/{env_id}/variables/{var_id}")
def delete_variable(
    project_id: int,
    env_id: int,
    var_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project(project_id, db, current_user)
    from app.services.environment_manager import EnvironmentManager
    mgr = EnvironmentManager(db)
    if mgr.delete_variable(project_id, var_id):
        return {"detail": "删除成功"}
    raise HTTPException(status_code=404, detail="变量不存在")


compare_router = APIRouter(
    prefix="/api/projects/{project_id}/environments",
    tags=["环境变量管理"],
)


@compare_router.get("/compare")
def compare_environments(
    project_id: int,
    env_ids: str = Query(..., description="逗号分隔的环境ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project(project_id, db, current_user)
    from app.services.environment_manager import EnvironmentManager
    mgr = EnvironmentManager(db)
    ids = [int(x.strip()) for x in env_ids.split(",") if x.strip()]
    if len(ids) < 2:
        raise HTTPException(status_code=400, detail="至少需要两个环境进行对比")
    return mgr.compare_environments(project_id, ids)


@compare_router.post("/{env_id}/clone")
def clone_environment(
    project_id: int,
    env_id: int,
    target_env_id: int = Query(..., description="目标环境ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project(project_id, db, current_user)
    from app.services.environment_manager import EnvironmentManager
    mgr = EnvironmentManager(db)
    count = mgr.clone_environment(project_id, env_id, target_env_id)
    return {"detail": f"已克隆 {count} 个变量", "cloned_count": count}


@compare_router.post("/{env_id}/sync-variables")
def sync_variables(
    project_id: int,
    env_id: int,
    target_env_ids: str = Query(..., description="逗号分隔的目标环境ID"),
    keys: Optional[str] = Query(None, description="逗号分隔的变量key，为空则同步全部"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_project(project_id, db, current_user)
    from app.services.environment_manager import EnvironmentManager
    mgr = EnvironmentManager(db)
    target_ids = [int(x.strip()) for x in target_env_ids.split(",") if x.strip()]
    key_list = [k.strip() for k in keys.split(",")] if keys else None
    result = mgr.sync_variables(project_id, env_id, target_ids, key_list)
    return {"detail": "同步完成", "results": result}
