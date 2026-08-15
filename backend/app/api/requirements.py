from fastapi import APIRouter, Depends, HTTPException, Request, status, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from app.database import get_db
from app.core.deps import get_current_user, get_project
from app.core.audit import audit
from app.models.user import User
from app.models.project import Project
from app.models.requirement import TestRequirement
from app.models.test_case import TestCase
from app.schemas.requirement import RequirementCreate, RequirementUpdate, RequirementResponse

router = APIRouter(prefix="/api/projects/{project_id}/requirements", tags=["需求管理"])

@router.get("", response_model=List[RequirementResponse])
def list_requirements(
    project_id: int,
    version_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取需求列表"""
    get_project(project_id, db, current_user)
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
    get_project(project_id, db, current_user)
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
    get_project(project_id, db, current_user)
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
    get_project(project_id, db, current_user)
    requirement = db.query(TestRequirement).filter(
        TestRequirement.id == req_id,
        TestRequirement.project_id == project_id,
    ).first()
    if not requirement:
        raise HTTPException(status_code=404, detail="需求不存在")

    old_data = {"title": requirement.title, "content": requirement.content, "status": requirement.status}
    update_data = req_data.model_dump(exclude_unset=True)
    content_changed = bool(
        ("content" in update_data and update_data["content"] != requirement.content) or
        ("title" in update_data and update_data["title"] != requirement.title)
    )
    for key, value in update_data.items():
        setattr(requirement, key, value)

    # P1-11: 需求内容变更时，标记关联用例为「待更新」
    affected_cases = 0
    if content_changed:
        affected_cases = db.query(TestCase).filter(
            TestCase.req_id == req_id,
            TestCase.is_deleted == False,
        ).update({TestCase.needs_update: True}, synchronize_session=False)

    audit(
        request, db, action="update", resource_type="requirement",
        resource_id=requirement.id, resource_name=requirement.title,
        user=current_user,
        detail={"before": old_data, "after": update_data, "affected_cases": affected_cases},
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
    get_project(project_id, db, current_user)
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


@router.get("/stats/coverage")
def requirement_coverage(
    project_id: int,
    version_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    P1-11: 需求覆盖率统计。
    返回需求总数、已关联用例的需求数、未关联需求数、待更新用例数。
    """
    get_project(project_id, db, current_user)
    req_query = db.query(TestRequirement).filter(
        TestRequirement.project_id == project_id,
        TestRequirement.is_deleted == False,
    )
    if version_id is not None:
        req_query = req_query.filter(TestRequirement.version_id == version_id)
    total_requirements = req_query.count()

    # 已关联用例的需求 ID 列表
    covered_req_ids = db.query(TestCase.req_id).filter(
        TestCase.project_id == project_id,
        TestCase.req_id.isnot(None),
        TestCase.is_deleted == False,
    ).distinct().subquery()

    covered_query = req_query.filter(TestRequirement.id.in_(covered_req_ids))
    covered_requirements = covered_query.count()
    uncovered_requirements = total_requirements - covered_requirements

    # 待更新用例数
    needs_update_cases = db.query(func.count(TestCase.id)).filter(
        TestCase.project_id == project_id,
        TestCase.needs_update == True,
        TestCase.is_deleted == False,
    ).scalar() or 0

    # 用例总数
    total_cases = db.query(func.count(TestCase.id)).filter(
        TestCase.project_id == project_id,
        TestCase.is_deleted == False,
    ).scalar() or 0

    coverage_rate = round(covered_requirements / total_requirements * 100, 1) if total_requirements > 0 else 0.0

    return {
        "total_requirements": total_requirements,
        "covered_requirements": covered_requirements,
        "uncovered_requirements": uncovered_requirements,
        "coverage_rate": coverage_rate,
        "total_cases": total_cases,
        "needs_update_cases": needs_update_cases,
    }


@router.post("/{req_id}/cases/acknowledged")
def acknowledge_cases_update(
    project_id: int,
    req_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    P1-11: 确认用例已根据需求变更更新，清除 needs_update 标记。
    """
    get_project(project_id, db, current_user)
    requirement = db.query(TestRequirement).filter(
        TestRequirement.id == req_id,
        TestRequirement.project_id == project_id,
    ).first()
    if not requirement:
        raise HTTPException(status_code=404, detail="需求不存在")

    updated = db.query(TestCase).filter(
        TestCase.req_id == req_id,
        TestCase.needs_update == True,
        TestCase.is_deleted == False,
    ).update({TestCase.needs_update: False}, synchronize_session=False)

    audit(
        request, db, action="acknowledge", resource_type="requirement",
        resource_id=req_id, resource_name=requirement.title,
        user=current_user,
        detail={"cleared_cases": updated},
    )
    db.commit()
    return {"cleared_cases": updated}


@router.post("/upload", response_model=RequirementResponse)
async def upload_requirement(
    project_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传需求文档（Word/PDF/文本）"""
    get_project(project_id, db, current_user)

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
