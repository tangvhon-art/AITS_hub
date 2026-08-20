from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.core.deps import get_current_user, get_project
from app.core.audit import log_audit
from app.models.user import User
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse,
    ProjectMemberResponse, ProjectMemberCreate, ProjectMemberUpdate,
)

router = APIRouter(prefix="/api/projects", tags=["项目管理"])

VALID_MEMBER_ROLES = {"owner", "admin", "developer", "tester"}


@router.get("", response_model=List[ProjectResponse])
def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户参与的项目列表"""
    if current_user.is_admin:
        return db.query(Project).order_by(Project.created_at.desc()).all()

    project_ids = db.query(ProjectMember.project_id).filter(
        ProjectMember.user_id == current_user.id,
    ).subquery()
    return db.query(Project).filter(
        Project.id.in_(project_ids),
    ).order_by(Project.created_at.desc()).all()


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    project_data: ProjectCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建项目"""
    project = Project(
        name=project_data.name,
        description=project_data.description,
        owner_id=current_user.id,
    )
    db.add(project)
    db.flush()

    membership = ProjectMember(
        project_id=project.id,
        user_id=current_user.id,
        role="owner",
    )
    db.add(membership)

    log_audit(
        db, action="create", resource_type="project",
        resource_id=project.id, resource_name=project.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"name": project.name, "description": project.description},
    )
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project_detail(
    project: Project = Depends(get_project),
):
    """获取项目详情"""
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_data: ProjectUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project: Project = Depends(get_project),
):
    """更新项目"""
    _check_manage_permission(db, project, current_user)

    old_data = {"name": project.name, "description": project.description}
    update_data = project_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(project, key, value)
    log_audit(
        db, action="update", resource_type="project",
        resource_id=project.id, resource_name=project.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"before": old_data, "after": update_data},
    )
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project: Project = Depends(get_project),
):
    """删除项目"""
    _check_manage_permission(db, project, current_user)

    project_name = project.name
    project.soft_delete()
    for m in db.query(ProjectMember).filter(
        ProjectMember.project_id == project.id,
    ).all():
        m.soft_delete()
    log_audit(
        db, action="delete", resource_type="project",
        resource_id=project.id, resource_name=project_name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()


# ─── 成员管理 ───


def _check_manage_permission(db: Session, project: Project, user: User):
    """检查用户是否有项目管理权限（owner/admin 角色 或 系统管理员）"""
    if user.is_admin:
        return
    membership = db.query(ProjectMember).filter(
        ProjectMember.project_id == project.id,
        ProjectMember.user_id == user.id,
    ).first()
    if membership and membership.role in ("owner", "admin"):
        return
    raise HTTPException(status_code=403, detail="无权管理该项目")


@router.get("/{project_id}/members", response_model=List[ProjectMemberResponse])
def list_members(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project: Project = Depends(get_project),
):
    """获取项目成员列表"""
    memberships = db.query(ProjectMember).filter(
        ProjectMember.project_id == project.id,
    ).all()
    result = []
    for m in memberships:
        user = db.query(User).filter(User.id == m.user_id).first()
        if not user:
            continue
        result.append(ProjectMemberResponse(
            id=m.id,
            project_id=m.project_id,
            user_id=m.user_id,
            username=user.username,
            full_name=user.full_name or "",
            email=user.email,
            role=m.role,
            joined_at=m.joined_at,
        ))
    return result


@router.get("/{project_id}/members/search", response_model=List[dict])
def search_users_for_member(
    project_id: int,
    q: str = Query("", min_length=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project: Project = Depends(get_project),
):
    """搜索可添加为成员的用户（排除已是成员的）"""
    existing_ids = db.query(ProjectMember.user_id).filter(
        ProjectMember.project_id == project_id,
    ).subquery()
    query = db.query(User).filter(
        ~User.id.in_(existing_ids),
        User.is_active == True,
    )
    if q:
        query = query.filter(
            (User.username.contains(q)) | (User.email.contains(q))
        )
    users = query.limit(20).all()
    return [{"id": u.id, "username": u.username, "email": u.email, "full_name": u.full_name} for u in users]


@router.post("/{project_id}/members", response_model=ProjectMemberResponse, status_code=201)
def add_member(
    member_data: ProjectMemberCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project: Project = Depends(get_project),
):
    """添加项目成员"""
    _check_manage_permission(db, project, current_user)

    user = db.query(User).filter(User.id == member_data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="该用户已被禁用")

    existing = db.query(ProjectMember).filter(
        ProjectMember.project_id == project.id,
        ProjectMember.user_id == member_data.user_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="该用户已是项目成员")

    if member_data.role not in VALID_MEMBER_ROLES or member_data.role == "owner":
        raise HTTPException(status_code=400, detail="角色只能是 admin、developer 或 tester")

    membership = ProjectMember(
        project_id=project.id,
        user_id=member_data.user_id,
        role=member_data.role,
    )
    db.add(membership)
    log_audit(
        db, action="create", resource_type="project_member",
        resource_id=project.id, resource_name=project.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"user_id": member_data.user_id, "username": user.username, "role": member_data.role},
    )
    db.commit()
    db.refresh(membership)
    return ProjectMemberResponse(
        id=membership.id,
        project_id=membership.project_id,
        user_id=membership.user_id,
        username=user.username,
        full_name=user.full_name or "",
        email=user.email,
        role=membership.role,
        joined_at=membership.joined_at,
    )


@router.put("/{project_id}/members/{user_id}", response_model=ProjectMemberResponse)
def update_member_role(
    user_id: int,
    member_data: ProjectMemberUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project: Project = Depends(get_project),
):
    """修改成员角色"""
    _check_manage_permission(db, project, current_user)

    membership = db.query(ProjectMember).filter(
        ProjectMember.project_id == project.id,
        ProjectMember.user_id == user_id,
    ).first()
    if not membership:
        raise HTTPException(status_code=404, detail="该用户不是项目成员")
    if membership.role == "owner":
        raise HTTPException(status_code=400, detail="不能修改项目创建者的角色")

    if member_data.role not in VALID_MEMBER_ROLES or member_data.role == "owner":
        raise HTTPException(status_code=400, detail="角色只能是 admin、developer 或 tester")

    old_role = membership.role
    membership.role = member_data.role
    log_audit(
        db, action="update", resource_type="project_member",
        resource_id=project.id, resource_name=project.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"user_id": user_id, "before": old_role, "after": member_data.role},
    )
    db.commit()
    db.refresh(membership)
    target_user = db.query(User).filter(User.id == user_id).first()
    return ProjectMemberResponse(
        id=membership.id,
        project_id=membership.project_id,
        user_id=membership.user_id,
        username=target_user.username if target_user else "",
        full_name=target_user.full_name if target_user else "",
        email=target_user.email if target_user else "",
        role=membership.role,
        joined_at=membership.joined_at,
    )


@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project: Project = Depends(get_project),
):
    """移除项目成员"""
    _check_manage_permission(db, project, current_user)

    membership = db.query(ProjectMember).filter(
        ProjectMember.project_id == project.id,
        ProjectMember.user_id == user_id,
    ).first()
    if not membership:
        raise HTTPException(status_code=404, detail="该用户不是项目成员")
    if membership.role == "owner":
        raise HTTPException(status_code=400, detail="不能移除项目创建者")

    membership.soft_delete()
    log_audit(
        db, action="delete", resource_type="project_member",
        resource_id=project.id, resource_name=project.name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"user_id": user_id},
    )
    db.commit()
