"""
知识库管理 API
"""
import os
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.knowledge_doc import KnowledgeDoc
from app.models.project import Project
from app.services.knowledge_base import knowledge_base_service
from app.schemas.knowledge import (
    KnowledgeDocCreate,
    KnowledgeDocResponse,
    KnowledgeDocListResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeStatsResponse,
)

router = APIRouter(prefix="/api/projects/{project_id}/knowledge", tags=["知识库管理"])


def _check_project_access(db: Session, user: User, project_id: int):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not user.is_admin and project.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权限访问该项目")
    return project


@router.get("", response_model=KnowledgeDocListResponse)
def list_knowledge_docs(
    project_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取知识库文档列表"""
    _check_project_access(db, current_user, project_id)

    query = db.query(KnowledgeDoc).filter(KnowledgeDoc.project_id == project_id)
    total = query.count()
    docs = query.order_by(KnowledgeDoc.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return KnowledgeDocListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[KnowledgeDocResponse.model_validate(d) for d in docs],
    )


@router.post("", response_model=KnowledgeDocResponse)
def create_knowledge_doc(
    project_id: int,
    doc_data: KnowledgeDocCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建知识库文档（文本）"""
    _check_project_access(db, current_user, project_id)

    doc = KnowledgeDoc(
        project_id=project_id,
        title=doc_data.title,
        content=doc_data.content,
        file_type=doc_data.file_type,
        status="processing",
        created_by=current_user.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # 异步处理：添加到知识库
    try:
        result = knowledge_base_service.add_document(
            project_id=project_id,
            doc_id=doc.id,
            title=doc.title,
            content=doc.content,
        )
        if result.get("success"):
            doc.status = "ready"
            doc.chunk_count = result.get("chunk_count", 0)
        else:
            doc.status = "failed"
            doc.error_message = result.get("error", "")
        db.commit()
        db.refresh(doc)
    except Exception as e:
        doc.status = "failed"
        doc.error_message = str(e)
        db.commit()

    return KnowledgeDocResponse.model_validate(doc)


@router.post("/upload", response_model=KnowledgeDocResponse)
async def upload_knowledge_doc(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传知识库文档"""
    _check_project_access(db, current_user, project_id)

    # 读取文件内容
    content = ""
    file_type = "text"
    filename = file.filename or "unknown"

    try:
        raw_content = await file.read()
        if filename.endswith(".md"):
            content = raw_content.decode("utf-8")
            file_type = "markdown"
        elif filename.endswith(".txt"):
            content = raw_content.decode("utf-8")
            file_type = "text"
        elif filename.endswith(".docx"):
            from docx import Document
            import io
            doc_file = Document(io.BytesIO(raw_content))
            content = "\n".join([p.text for p in doc_file.paragraphs])
            file_type = "docx"
        elif filename.endswith(".pdf"):
            from pypdf import PdfReader
            import io
            reader = PdfReader(io.BytesIO(raw_content))
            content = "\n".join([page.extract_text() or "" for page in reader.pages])
            file_type = "pdf"
        else:
            content = raw_content.decode("utf-8", errors="ignore")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件解析失败: {str(e)}")

    # 保存文档记录
    doc = KnowledgeDoc(
        project_id=project_id,
        title=filename,
        content=content,
        file_type=file_type,
        status="processing",
        created_by=current_user.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # 添加到知识库
    try:
        result = knowledge_base_service.add_document(
            project_id=project_id,
            doc_id=doc.id,
            title=doc.title,
            content=doc.content,
        )
        if result.get("success"):
            doc.status = "ready"
            doc.chunk_count = result.get("chunk_count", 0)
        else:
            doc.status = "failed"
            doc.error_message = result.get("error", "")
        db.commit()
        db.refresh(doc)
    except Exception as e:
        doc.status = "failed"
        doc.error_message = str(e)
        db.commit()

    return KnowledgeDocResponse.model_validate(doc)


@router.post("/search", response_model=KnowledgeSearchResponse)
def search_knowledge(
    project_id: int,
    req: KnowledgeSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """检索知识库"""
    _check_project_access(db, current_user, project_id)

    results = knowledge_base_service.search(
        project_id=project_id,
        query=req.query,
        top_k=req.top_k,
    )

    return KnowledgeSearchResponse(
        query=req.query,
        results=results,
        total=len(results),
    )


@router.get("/stats", response_model=KnowledgeStatsResponse)
def get_knowledge_stats(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取知识库统计"""
    _check_project_access(db, current_user, project_id)
    stats = knowledge_base_service.get_stats(project_id)
    return KnowledgeStatsResponse(
        project_id=project_id,
        total_docs=stats.get("total_docs", 0),
        total_chunks=stats.get("total_chunks", 0),
    )


@router.get("/{doc_id}", response_model=KnowledgeDocResponse)
def get_knowledge_doc(
    project_id: int,
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取知识库文档详情"""
    _check_project_access(db, current_user, project_id)
    doc = db.query(KnowledgeDoc).filter(KnowledgeDoc.id == doc_id, KnowledgeDoc.project_id == project_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return KnowledgeDocResponse.model_validate(doc)


@router.delete("/{doc_id}")
def delete_knowledge_doc(
    project_id: int,
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除知识库文档"""
    _check_project_access(db, current_user, project_id)
    doc = db.query(KnowledgeDoc).filter(KnowledgeDoc.id == doc_id, KnowledgeDoc.project_id == project_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    # 从向量库中删除
    knowledge_base_service.delete_document(project_id, doc_id)

    db.delete(doc)
    db.commit()
    return {"message": "文档已删除"}
