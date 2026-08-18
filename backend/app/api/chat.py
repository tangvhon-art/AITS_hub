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
        try:
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
