"""
MCP Server 端点挂载（Streamable HTTP）
- GET  /mcp/sse        SSE 握手：推送 endpoint 事件（兼容 app/mcp/client.py 的 GET→POST 流程）
- POST /mcp/messages   JSON-RPC 统一入口（initialize / tools/list / tools/call / notifications/initialized）
复用 app/mcp/server.py::handle_mcp_request，将其暴露为 HTTP 端点。
"""
import asyncio
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.mcp.server import handle_mcp_request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp", tags=["MCP Server"])

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@router.get("/sse")
async def mcp_sse(request: Request):
    """SSE 握手：推送 endpoint 事件后保持连接（心跳），客户端主要走 POST /mcp/messages"""

    async def event_stream():
        try:
            yield 'event: endpoint\ndata: {"endpoint": "/mcp/messages"}\n\n'
            while True:
                await asyncio.sleep(15)
                yield ": keep-alive\n\n"
        except (asyncio.CancelledError, GeneratorExit):
            return
        except Exception:  # noqa: BLE001
            return

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/messages")
def mcp_messages(payload: dict, request: Request):
    """JSON-RPC 统一入口（支持批处理数组）

    使用同步函数：tools/call 内部通过 run_until_complete 执行工具，
    若此处为 async def 会与已有事件循环冲突。
    """
    if isinstance(payload, list):
        results = []
        for item in payload:
            if isinstance(item, dict):
                results.append(handle_mcp_request(item))
            else:
                results.append({"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}})
        return JSONResponse(results)

    if not isinstance(payload, dict):
        return JSONResponse(
            {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}},
            status_code=400,
        )
    return JSONResponse(handle_mcp_request(payload))
