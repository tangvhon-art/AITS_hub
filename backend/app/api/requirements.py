from fastapi import APIRouter, Depends, HTTPException, Request, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.core.deps import get_current_user
from app.core.audit import log_audit
from app.models.user import User
from app.models.project import Project
from app.models.requirement import TestRequirement
from app.schemas.requirement import RequirementCreate, RequirementUpdate, RequirementResponse

router = APIRouter(prefix="/api/projects/{project_id}/requirements", tags=["需求管理"])


def _check_project_access(project_id: int, db: Session, user: User) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if project.owner_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="无权访问该项目")
    return project


@router.get("", response_model=List[RequirementResponse])
def list_requirements(
    project_id: int,
    version_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取需求列表"""
    _check_project_access(project_id, db, current_user)
    query = db.query(TestRequirement).filter(
        TestRequirement.project_id == project_id
    )
    if version_id is not None:
        query = query.filter(TestRequirement.version_id == version_id)
    requirements = query.order_by(TestRequirement.created_at.desc()).all()
    return requirements


@router.post("", response_model=RequirementResponse, status_code=status.HTTP_201_CREATED)
def create_requirement(
    project_id: int,
    req_data: RequirementCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建需求"""
    _check_project_access(project_id, db, current_user)
    requirement = TestRequirement(
        project_id=project_id,
        title=req_data.title,
        content=req_data.content,
        source=req_data.source,
        source_url=req_data.source_url,
        version_id=req_data.version_id,
        created_by=current_user.id,
    )
    db.add(requirement)
    db.flush()
    log_audit(
        db, action="create", resource_type="requirement",
        resource_id=requirement.id, resource_name=requirement.title,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "title": requirement.title, "source": requirement.source},
    )
    db.commit()
    db.refresh(requirement)
    return requirement


@router.get("/{req_id}", response_model=RequirementResponse)
def get_requirement(
    project_id: int,
    req_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取需求详情"""
    _check_project_access(project_id, db, current_user)
    requirement = db.query(TestRequirement).filter(
        TestRequirement.id == req_id,
        TestRequirement.project_id == project_id,
    ).first()
    if not requirement:
        raise HTTPException(status_code=404, detail="需求不存在")
    return requirement


@router.put("/{req_id}", response_model=RequirementResponse)
def update_requirement(
    project_id: int,
    req_id: int,
    req_data: RequirementUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新需求"""
    _check_project_access(project_id, db, current_user)
    requirement = db.query(TestRequirement).filter(
        TestRequirement.id == req_id,
        TestRequirement.project_id == project_id,
    ).first()
    if not requirement:
        raise HTTPException(status_code=404, detail="需求不存在")

    old_data = {"title": requirement.title, "content": requirement.content, "status": requirement.status}
    update_data = req_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(requirement, key, value)
    log_audit(
        db, action="update", resource_type="requirement",
        resource_id=requirement.id, resource_name=requirement.title,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"before": old_data, "after": update_data},
    )
    db.commit()
    db.refresh(requirement)
    return requirement


@router.delete("/{req_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_requirement(
    project_id: int,
    req_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除需求"""
    _check_project_access(project_id, db, current_user)
    requirement = db.query(TestRequirement).filter(
        TestRequirement.id == req_id,
        TestRequirement.project_id == project_id,
    ).first()
    if not requirement:
        raise HTTPException(status_code=404, detail="需求不存在")
    req_name = requirement.title
    requirement.soft_delete()
    log_audit(
        db, action="delete", resource_type="requirement",
        resource_id=req_id, resource_name=req_name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()


@router.post("/upload", response_model=RequirementResponse)
async def upload_requirement(
    project_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传需求文档（Word/PDF/文本）"""
    _check_project_access(project_id, db, current_user)

    content = ""
    filename = file.filename or "uploaded_requirement"

    if filename.endswith(".docx"):
        from docx import Document
        import io
        doc = Document(io.BytesIO(await file.read()))
        content = "\n".join([para.text for para in doc.paragraphs])
    elif filename.endswith(".pdf"):
        from pypdf import PdfReader
        import io
        reader = PdfReader(io.BytesIO(await file.read()))
        content = "\n".join([page.extract_text() or "" for page in reader.pages])
    elif filename.endswith(".txt") or filename.endswith(".md"):
        content = (await file.read()).decode("utf-8")
    else:
        raise HTTPException(status_code=400, detail="不支持的文件格式，请上传 .docx/.pdf/.txt/.md")

    requirement = TestRequirement(
        project_id=project_id,
        title=filename,
        content=content,
        source="upload",
        created_by=current_user.id,
    )
    db.add(requirement)
    db.flush()
    log_audit(
        db, action="import", resource_type="requirement",
        resource_id=requirement.id, resource_name=filename,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "filename": filename, "content_length": len(content)},
    )
    db.commit()
    db.refresh(requirement)
    return requirement
