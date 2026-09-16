"""
聊天历史记录 API — 会话管理和消息查询
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_user
from app.core.timezone import china_now_naive
from app.models.chat_history import ChatSession, ChatMessage
from app.schemas.chat_history import (
    ChatSessionCreate, ChatSessionUpdate, ChatSessionResponse,
    ChatSessionListResponse, ChatSessionDetailResponse,
)

router = APIRouter(prefix="/api/chat", tags=["智能助手-历史记录"])


@router.get("/sessions", response_model=ChatSessionListResponse)
def list_sessions(
    project_id: Optional[int] = Query(None, description="按项目筛选，不传则返回所有（含通用问答）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取当前用户的聊天会话列表"""
    query = db.query(ChatSession).filter(
        ChatSession.user_id == current_user.id,
        ChatSession.is_deleted == False,
    )
    if project_id is not None:
        query = query.filter(ChatSession.project_id == project_id)
    else:
        # 不传 project_id 时返回所有会话（包括通用问答 project_id=NULL）
        pass
    total = query.count()
    items = query.order_by(ChatSession.last_message_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    return {"total": total, "items": items}


@router.post("/sessions", response_model=ChatSessionResponse)
def create_session(
    data: ChatSessionCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """创建新会话"""
    session = ChatSession(
        user_id=current_user.id,
        project_id=data.project_id,
        title=data.title,
        llm_config_id=data.llm_config_id,
        use_knowledge=data.use_knowledge,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/sessions/{session_id}", response_model=ChatSessionDetailResponse)
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """获取会话详情（含消息列表）"""
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id,
        ChatSession.is_deleted == False,
    ).first()
    if not session:
        raise HTTPException(404, "会话不存在")
    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.sort_order.asc(), ChatMessage.id.asc()).all()
    return {"session": session, "messages": messages}


@router.put("/sessions/{session_id}", response_model=ChatSessionResponse)
def update_session(
    session_id: int,
    data: ChatSessionUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """更新会话（重命名）"""
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id,
        ChatSession.is_deleted == False,
    ).first()
    if not session:
        raise HTTPException(404, "会话不存在")
    if data.title is not None:
        session.title = data.title
    db.commit()
    db.refresh(session)
    return session


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """删除会话（软删除）"""
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id,
        ChatSession.is_deleted == False,
    ).first()
    if not session:
        raise HTTPException(404, "会话不存在")
    session.is_deleted = True
    session.deleted_at = china_now_naive()
    db.commit()
    return {"message": "删除成功"}
