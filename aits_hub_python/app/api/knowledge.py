"""
知识库管理 API
"""
import logging
import io
from typing import Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_user, get_project
from app.core.audit import log_audit
from app.models.user import User
from app.models.knowledge_doc import KnowledgeDoc, KnowledgeChunk
from app.models.project import Project
from app.models.agent_task import AgentTask
from app.core.timezone import china_now_naive
from app.services.knowledge_base import knowledge_base_service
from app.schemas.knowledge import (
    KnowledgeDocCreate,
    KnowledgeDocResponse,
    KnowledgeDocListResponse,
    KnowledgeChunkResponse,
    KnowledgeChunkListResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeStatsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects/{project_id}/knowledge", tags=["知识库管理"])

@router.post("/docs/search", response_model=KnowledgeDocListResponse)
def list_knowledge_docs(
    project_id: int,
    page: int = Body(1),
    page_size: int = Body(20),
    keyword: str = Body(""),
    source_type: str = Body(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取知识库文档列表（支持关键词搜索）"""
    get_project(project_id, db, current_user)

    query = db.query(KnowledgeDoc).filter(KnowledgeDoc.project_id == project_id)
    if keyword:
        from sqlalchemy import or_
        kw = f"%{keyword}%"
        query = query.filter(or_(KnowledgeDoc.title.like(kw), KnowledgeDoc.content.like(kw)))
    if source_type:
        query = query.filter(KnowledgeDoc.source_type == source_type)
    total = query.count()
    docs = query.order_by(KnowledgeDoc.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return KnowledgeDocListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[KnowledgeDocResponse.model_validate(d) for d in docs],
    )


@router.post("/chunks/search", response_model=KnowledgeChunkListResponse)
def list_knowledge_chunks(
    project_id: int,
    page: int = Body(1),
    page_size: int = Body(20),
    keyword: str = Body(""),
    doc_id: int = Body(0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取知识内容（切片）列表，支持关键词和文档筛选"""
    get_project(project_id, db, current_user)

    query = db.query(KnowledgeChunk).filter(KnowledgeChunk.project_id == project_id)
    if doc_id:
        query = query.filter(KnowledgeChunk.doc_id == doc_id)
    if keyword:
        query = query.filter(KnowledgeChunk.content.like(f"%{keyword}%"))

    total = query.count()
    chunks = query.order_by(KnowledgeChunk.doc_id, KnowledgeChunk.chunk_index).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    # 补充文档标题
    doc_ids = list({c.doc_id for c in chunks})
    title_map = {}
    if doc_ids:
        docs = db.query(KnowledgeDoc).filter(KnowledgeDoc.id.in_(doc_ids)).all()
        title_map = {d.id: d.title for d in docs}

    items = []
    for c in chunks:
        item = KnowledgeChunkResponse.model_validate(c)
        item.doc_title = title_map.get(c.doc_id, "")
        items.append(item)

    return KnowledgeChunkListResponse(total=total, page=page, page_size=page_size, items=items)

@router.post("", response_model=KnowledgeDocResponse)
def create_knowledge_doc(
    project_id: int,
    doc_data: KnowledgeDocCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建知识库文档（文本，仅保存内容，不自动切片）"""
    get_project(project_id, db, current_user)

    doc = KnowledgeDoc(
        project_id=project_id,
        title=doc_data.title,
        content=doc_data.content,
        file_type=doc_data.file_type,
        file_size=len(doc_data.content or ""),
        source_type="manual",
        status="pending",
        created_by=current_user.id,
    )
    db.add(doc)
    db.flush()

    log_audit(
        db, action="create", resource_type="knowledge",
        resource_id=doc.id, resource_name=doc.title,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "title": doc.title, "file_type": doc.file_type},
    )
    db.commit()
    db.refresh(doc)

    return KnowledgeDocResponse.model_validate(doc)

@router.post("/upload", response_model=KnowledgeDocResponse)
async def upload_knowledge_doc(
    project_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传知识库文档（仅解析保存内容，不自动切片）"""
    get_project(project_id, db, current_user)

    raw_content = await file.read()
    content = ""
    file_type = "text"
    filename = file.filename or "unknown"

    try:
        if filename.endswith(".md"):
            content = raw_content.decode("utf-8")
            file_type = "markdown"
        elif filename.endswith(".txt"):
            content = raw_content.decode("utf-8")
            file_type = "text"
        elif filename.endswith(".docx"):
            from docx import Document
            doc_file = Document(io.BytesIO(raw_content))
            content = "\n".join([p.text for p in doc_file.paragraphs])
            file_type = "docx"
        elif filename.endswith(".pdf"):
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw_content))
            content = "\n".join([page.extract_text() or "" for page in reader.pages])
            file_type = "pdf"
        else:
            content = raw_content.decode("utf-8", errors="ignore")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件解析失败: {str(e)}")

    doc = KnowledgeDoc(
        project_id=project_id,
        title=filename,
        content=content,
        file_type=file_type,
        file_size=len(raw_content),
        source_type="upload",
        status="pending",
        created_by=current_user.id,
    )
    db.add(doc)
    db.flush()

    log_audit(
        db, action="import", resource_type="knowledge",
        resource_id=doc.id, resource_name=filename,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "filename": filename, "file_type": file_type, "content_length": len(content)},
    )
    db.commit()
    db.refresh(doc)

    return KnowledgeDocResponse.model_validate(doc)

@router.post("/search", response_model=KnowledgeSearchResponse)
def search_knowledge(
    project_id: int,
    req: KnowledgeSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """语义检索知识库"""
    get_project(project_id, db, current_user)

    results = knowledge_base_service.search(
        db=db,
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
    get_project(project_id, db, current_user)
    stats = knowledge_base_service.get_stats(db, project_id)
    return KnowledgeStatsResponse(
        project_id=project_id,
        total_docs=stats.get("total_docs", 0),
        total_chunks=stats.get("total_chunks", 0),
    )

@router.post("/sync-requirements")
def sync_requirements_to_knowledge(
    project_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    requirement_ids: list = Body(default=[]),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    同步需求到知识库。
    - requirement_ids 为空时同步项目下所有需求
    - 已同步的需求（source_type=requirement, source_id=需求ID）会更新内容并重新切片
    """
    get_project(project_id, db, current_user)

    from app.models.requirement import TestRequirement

    req_query = db.query(TestRequirement).filter(
        TestRequirement.project_id == project_id,
        TestRequirement.is_deleted == False,
    )
    if requirement_ids:
        req_query = req_query.filter(TestRequirement.id.in_(requirement_ids))
    requirements = req_query.all()

    if not requirements:
        return {"synced": 0, "message": "没有需要同步的需求"}

    synced_ids = []
    for req in requirements:
        # 查找是否已同步
        existing = db.query(KnowledgeDoc).filter(
            KnowledgeDoc.project_id == project_id,
            KnowledgeDoc.source_type == "requirement",
            KnowledgeDoc.source_id == req.id,
        ).first()

        content = f"# {req.title}\n\n{req.content or ''}"
        if existing:
            existing.title = f"[需求] {req.title}"
            existing.content = content
            existing.status = "pending"
            existing.error_message = ""
            doc_id = existing.id
        else:
            doc = KnowledgeDoc(
                project_id=project_id,
                title=f"[需求] {req.title}",
                content=content,
                file_type="markdown",
                file_size=len(content),
                source_type="requirement",
                source_id=req.id,
                status="pending",
                created_by=current_user.id,
            )
            db.add(doc)
            db.flush()
            doc_id = doc.id

        synced_ids.append(doc_id)

    log_audit(
        db, action="sync", resource_type="knowledge",
        resource_id=0, resource_name=f"同步{len(synced_ids)}条需求到知识库",
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"project_id": project_id, "requirement_count": len(synced_ids)},
    )
    db.commit()

    # 后台异步生成切片
    def _process_docs():
        from app.tasks.knowledge_tasks import process_knowledge_doc_task
        for did in synced_ids:
            try:
                process_knowledge_doc_task.delay(did, project_id)
            except Exception:
                process_knowledge_doc_task(did, project_id)

    background_tasks.add_task(_process_docs)

    return {
        "synced": len(synced_ids),
        "doc_ids": synced_ids,
        "message": f"已同步 {len(synced_ids)} 条需求到知识库，正在后台生成向量切片",
    }


@router.post("/{doc_id}/generate-chunks")
def generate_chunks(
    project_id: int,
    doc_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """手动触发生成切片（异步 Celery 任务）"""
    get_project(project_id, db, current_user)
    doc = db.query(KnowledgeDoc).filter(
        KnowledgeDoc.id == doc_id,
        KnowledgeDoc.project_id == project_id,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    if doc.status == "processing":
        raise HTTPException(status_code=400, detail="切片正在处理中，请勿重复操作")

    doc.status = "processing"
    doc.error_message = ""

    agent_task = AgentTask(
        project_id=project_id,
        agent_type="knowledge_processor",
        status="running",
        input_params={"doc_id": doc.id, "title": doc.title, "content_length": len(doc.content or "")},
        created_by=current_user.id,
    )
    db.add(agent_task)
    db.flush()
    db.commit()
    db.refresh(agent_task)

    use_celery = False
    celery_task_id = None
    try:
        from app.tasks.knowledge_tasks import process_knowledge_doc_task
        task_result = process_knowledge_doc_task.delay(doc.id, project_id, agent_task.id)
        celery_task_id = task_result.id
        use_celery = True
        logger.info(f"知识库文档 #{doc.id} 切片任务已提交 Celery: task_id={celery_task_id}")
    except Exception as celery_e:
        logger.warning(f"Celery 任务提交失败，降级到 BackgroundTasks: {celery_e}")

        def _process_in_background(doc_id: int, pid: int, at_id: int):
            from app.tasks.knowledge_tasks import process_knowledge_doc_task
            process_knowledge_doc_task(doc_id, pid, at_id)

        background_tasks.add_task(_process_in_background, doc.id, project_id, agent_task.id)

    try:
        agent_task.input_params["celery_task_id"] = celery_task_id
        agent_task.input_params["executor"] = "celery" if use_celery else "background"
        db.commit()
    except Exception:
        pass

    return {
        "doc_id": doc.id,
        "status": "processing",
        "message": "切片任务已提交",
    }


@router.get("/{doc_id}", response_model=KnowledgeDocResponse)
def get_knowledge_doc(
    project_id: int,
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取知识库文档详情"""
    get_project(project_id, db, current_user)
    doc = db.query(KnowledgeDoc).filter(KnowledgeDoc.id == doc_id, KnowledgeDoc.project_id == project_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return KnowledgeDocResponse.model_validate(doc)

@router.delete("/{doc_id}")
def delete_knowledge_doc(
    project_id: int,
    doc_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除知识库文档"""
    get_project(project_id, db, current_user)
    doc = db.query(KnowledgeDoc).filter(KnowledgeDoc.id == doc_id, KnowledgeDoc.project_id == project_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    doc_name = doc.title
    knowledge_base_service.delete_document(db, project_id, doc_id)

    doc.soft_delete()
    log_audit(
        db, action="delete", resource_type="knowledge",
        resource_id=doc_id, resource_name=doc_name,
        user=current_user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return {"message": "文档已删除"}
