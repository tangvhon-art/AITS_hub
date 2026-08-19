"""
Chat 智能助手 API
支持 SSE 流式返回和工具调用事件
"""
import json
import logging
import asyncio
from typing import Optional, List, Dict
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.core.deps import get_current_user
from app.models.user import User
from app.agents.chat_agent import ChatAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["智能助手"])

# P3: 单用户并发对话数限制
MAX_CONCURRENT_PER_USER = 3
_user_concurrent: Dict[int, int] = {}


def _acquire_concurrent(user_id: int) -> bool:
    """获取并发槽位，返回是否成功"""
    current = _user_concurrent.get(user_id, 0)
    if current >= MAX_CONCURRENT_PER_USER:
        return False
    _user_concurrent[user_id] = current + 1
    return True


def _release_concurrent(user_id: int):
    """释放并发槽位"""
    if user_id in _user_concurrent:
        _user_concurrent[user_id] = max(0, _user_concurrent[user_id] - 1)


class ChatMessage(BaseModel):
    role: str = Field(..., description="角色: user/assistant")
    content: str = Field(..., description="消息内容")


class ChatRequest(BaseModel):
    message: str = Field(..., description="用户消息")
    project_id: Optional[int] = Field(None, description="项目ID")
    llm_config_id: Optional[int] = Field(None, description="LLM配置ID")
    history: Optional[List[ChatMessage]] = Field(None, description="对话历史")
    use_knowledge: bool = Field(True, description="是否使用知识库检索")
    stream: bool = Field(True, description="是否流式返回")
    session_id: Optional[int] = Field(None, description="会话ID（不传则新建会话）")


@router.post("")
async def chat(
    req: ChatRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """
    Chat 对话接口
    支持 SSE 流式返回、工具调用事件
    """
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="消息内容不能为空")

    # P3: 并发对话数限制
    if not _acquire_concurrent(current_user.id):
        raise HTTPException(status_code=429, detail=f"并发对话数已达上限（{MAX_CONCURRENT_PER_USER}），请等待当前对话完成")

    history = [h.model_dump() for h in req.history] if req.history else None

    if not req.stream:
        # 非流式返回 - 使用独立的 db session
        db = SessionLocal()
        try:
            agent = ChatAgent(
                db=db,
                project_id=req.project_id,
                llm_config_id=req.llm_config_id,
                user_id=current_user.id,
            )
            result = await agent.chat_non_stream(
                message=req.message,
                history=history,
                use_knowledge=req.use_knowledge,
            )
            return result
        finally:
            db.close()
            _release_concurrent(current_user.id)

    # SSE 流式返回 - 在生成器内部创建独立的 db session
    async def event_generator():
        db = SessionLocal()
        session_id = None
        assistant_content_parts = []
        assistant_tool_calls = []
        assistant_knowledge = None
        assistant_progress = []
        try:
            # === 历史记录：创建/获取会话，保存用户消息 ===
            from app.models.chat_history import ChatSession, ChatMessage
            from app.core.timezone import china_now_naive
            if req.session_id:
                session = db.query(ChatSession).filter(
                    ChatSession.id == req.session_id,
                    ChatSession.user_id == current_user.id,
                    ChatSession.is_deleted == False,
                ).first()
                if session:
                    session_id = session.id
                    session.last_message_at = china_now_naive()
                    db.commit()
            if not session_id:
                # 新建会话，标题取用户消息前30字
                title = req.message.strip()[:30]
                if len(req.message.strip()) > 30:
                    title += "..."
                session = ChatSession(
                    user_id=current_user.id,
                    project_id=req.project_id,
                    title=title or "新对话",
                    llm_config_id=req.llm_config_id,
                    use_knowledge=req.use_knowledge,
                )
                db.add(session)
                db.commit()
                db.refresh(session)
                session_id = session.id

            # 保存用户消息
            max_sort = db.query(ChatMessage).filter(
                ChatMessage.session_id == session_id
            ).count()
            user_msg = ChatMessage(
                session_id=session_id,
                role="user",
                content=req.message,
                sort_order=max_sort,
            )
            db.add(user_msg)
            session.message_count = (session.message_count or 0) + 1
            db.commit()

            # 发送会话ID事件，供前端记录
            yield f"data: {json.dumps({'type': 'session', 'session_id': session_id}, ensure_ascii=False)}\n\n"

            agent = ChatAgent(
                db=db,
                project_id=req.project_id,
                llm_config_id=req.llm_config_id,
                user_id=current_user.id,
            )

            # P3: 心跳 + 事件流合并
            event_queue: asyncio.Queue = asyncio.Queue()
            heartbeat_task = None

            async def heartbeat():
                """每15秒发送心跳注释，防止代理超时断开"""
                while True:
                    await asyncio.sleep(15)
                    await event_queue.put((": keep-alive\n\n", True))

            async def consume_events():
                try:
                    async for event in agent.chat(
                        message=req.message,
                        history=history,
                        use_knowledge=req.use_knowledge,
                    ):
                        # 收集助手消息用于历史保存
                        etype = event.get("type")
                        if etype == "content":
                            assistant_content_parts.append(event.get("content", ""))
                        elif etype == "tool_call":
                            assistant_tool_calls.append(event.get("tool_call", {}))
                        elif etype == "knowledge":
                            assistant_knowledge = event.get("results", [])
                        elif etype == "progress":
                            assistant_progress.append(event)
                        await event_queue.put((f"data: {json.dumps(event, ensure_ascii=False)}\n\n", False))
                except Exception as e:
                    logger.error(f"Agent chat 生成异常: {e}", exc_info=True)
                    await event_queue.put((f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n", False))
                finally:
                    await event_queue.put(("__done__", False))

            heartbeat_task = asyncio.create_task(heartbeat())
            consumer_task = asyncio.create_task(consume_events())

            try:
                while True:
                    if await request.is_disconnected():
                        break
                    item, is_heartbeat = await event_queue.get()
                    if item == "__done__":
                        break
                    yield item
            finally:
                heartbeat_task.cancel()
                consumer_task.cancel()

            # === 历史记录：保存助手消息 ===
            try:
                assistant_full = "".join(assistant_content_parts)
                if assistant_full or assistant_tool_calls:
                    # 规范化 progress：按 node 去重，保留最终状态（running 节点在已完成消息中标记为 done）
                    normalized_progress = []
                    if assistant_progress:
                        p_map = {}
                        for p in assistant_progress:
                            node = p.get("node") or p.get("label") or "unknown"
                            p_map[node] = {
                                "type": "progress",
                                "node": p.get("node") or node,
                                "label": p.get("label") or node,
                                "status": p.get("status") or "done",
                                "detail": p.get("detail"),
                                "duration": p.get("duration"),
                            }
                        normalized_progress = list(p_map.values())
                        # 已生成回答内容，所有进度节点视为已完成
                        if assistant_full:
                            for np in normalized_progress:
                                if np["status"] == "running":
                                    np["status"] = "done"
                    ai_msg = ChatMessage(
                        session_id=session_id,
                        role="assistant",
                        content=assistant_full,
                        tool_calls=assistant_tool_calls if assistant_tool_calls else None,
                        knowledge_results=assistant_knowledge,
                        progress=normalized_progress if normalized_progress else None,
                        sort_order=max_sort + 1,
                    )
                    db.add(ai_msg)
                    session.message_count = (session.message_count or 0) + 1
                    session.last_message_at = china_now_naive()
                    db.commit()
            except Exception as e:
                logger.warning(f"保存助手消息到历史失败: {e}")

            # 发送结束信号
            end_data = {"type": "done"}
            yield f"data: {json.dumps(end_data, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.error(f"Chat 流式输出异常: {e}", exc_info=True)
            error_data = {"type": "error", "message": str(e)}
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
        finally:
            db.close()
            _release_concurrent(current_user.id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
