"""
知识库管理 API
"""
import logging
import os
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_user, get_project
from app.core.audit import log_audit
from app.models.user import User
from app.models.knowledge_doc import KnowledgeDoc
from app.models.project import Project
from app.models.agent_task import AgentTask
from app.core.timezone import china_now_naive
from app.services.knowledge_base import knowledge_base_service
from app.schemas.knowledge import (
    KnowledgeDocCreate,
    KnowledgeDocResponse,
    KnowledgeDocListResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeStatsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects/{project_id}/knowledge", tags=["知识库管理"])

@router.post("/search", response_model=KnowledgeDocListResponse)
def list_knowledge_docs(
    project_id: int,
    page: int = Body(1),
    page_size: int = Body(20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取知识库文档列表"""
    get_project(project_id, db, current_user)

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
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建知识库文档（文本）"""
    get_project(project_id, db, current_user)

    doc = KnowledgeDoc(
        project_id=project_id,
        title=doc_data.title,
        content=doc_data.content,
        file_type=doc_data.file_type,
        status="processing",
        created_by=current_user.id,
    )
    db.add(doc)
    db.flush()

    # 创建 Agent 任务记录（知识库处理）
    agent_task = AgentTask(
        project_id=project_id,
        agent_type="knowledge_processor",
        status="running",
        input_params={"doc_id": doc.id, "title": doc.title, "content_length": len(doc_data.content or "")},
        created_by=current_user.id,
    )
    db.add(agent_task)
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
    db.refresh(agent_task)

    # 异步处理：优先 Celery，降级 BackgroundTasks
    use_celery = False
    celery_task_id = None
    try:
        from app.tasks.knowledge_tasks import process_knowledge_doc_task
        task_result = process_knowledge_doc_task.delay(doc.id, project_id, agent_task.id)
        celery_task_id = task_result.id
        use_celery = True
        logger.info(f"知识库文档 #{doc.id} 已提交 Celery 任务: task_id={celery_task_id}")
    except Exception as celery_e:
        logger.warning(f"Celery 任务提交失败，降级到 BackgroundTasks: {celery_e}")

        def _process_in_background(doc_id: int, pid: int, at_id: int):
            from app.tasks.knowledge_tasks import process_knowledge_doc_task
            process_knowledge_doc_task(doc_id, pid, at_id)

        background_tasks.add_task(_process_in_background, doc.id, project_id, agent_task.id)

    # 在 AgentTask 中记录 celery_task_id
    try:
        agent_task.input_params["celery_task_id"] = celery_task_id
        agent_task.input_params["executor"] = "celery" if use_celery else "background"
        db.commit()
    except Exception:
        pass

    return KnowledgeDocResponse.model_validate(doc)

@router.post("/upload", response_model=KnowledgeDocResponse)
async def upload_knowledge_doc(
    project_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传知识库文档"""
    get_project(project_id, db, current_user)

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
    db.flush()

    # 创建 Agent 任务记录
    agent_task = AgentTask(
        project_id=project_id,
        agent_type="knowledge_processor",
        status="running",
        input_params={"doc_id": doc.id, "title": filename, "file_type": file_type, "content_length": len(content)},
        created_by=current_user.id,
    )
    db.add(agent_task)
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
    db.refresh(agent_task)

    # 异步处理：优先 Celery，降级 BackgroundTasks
    use_celery = False
    celery_task_id = None
    try:
        from app.tasks.knowledge_tasks import process_knowledge_doc_task
        task_result = process_knowledge_doc_task.delay(doc.id, project_id, agent_task.id)
        celery_task_id = task_result.id
        use_celery = True
        logger.info(f"知识库文档 #{doc.id} 已提交 Celery 任务: task_id={celery_task_id}")
    except Exception as celery_e:
        logger.warning(f"Celery 任务提交失败，降级到 BackgroundTasks: {celery_e}")

        def _process_in_background(doc_id: int, pid: int, at_id: int):
            from app.tasks.knowledge_tasks import process_knowledge_doc_task
            process_knowledge_doc_task(doc_id, pid, at_id)

        background_tasks.add_task(_process_in_background, doc.id, project_id, agent_task.id)

    # 在 AgentTask 中记录 celery_task_id
    try:
        agent_task.input_params["celery_task_id"] = celery_task_id
        agent_task.input_params["executor"] = "celery" if use_celery else "background"
        db.commit()
    except Exception:
        pass

    return KnowledgeDocResponse.model_validate(doc)

@router.post("/search", response_model=KnowledgeSearchResponse)
def search_knowledge(
    project_id: int,
    req: KnowledgeSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """检索知识库"""
    get_project(project_id, db, current_user)

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
    get_project(project_id, db, current_user)
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
    # 从向量库中删除
    knowledge_base_service.delete_document(project_id, doc_id)

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
