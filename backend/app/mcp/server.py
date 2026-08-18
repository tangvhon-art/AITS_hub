"""
MCP Server — 将 AITS 内置工具暴露为 MCP 协议服务（SSE 模式）

外部 MCP Client 可连接此端点，调用 AITS 的工具。
"""
import json
import logging
from typing import Any, Dict

from app.agents.tools.registry import tool_registry

logger = logging.getLogger(__name__)


def handle_mcp_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    """处理 MCP JSON-RPC 请求"""
    method = payload.get("method", "")
    req_id = payload.get("id")
    params = payload.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "AITS MCP Server", "version": "1.0.0"},
            },
        }

    elif method == "tools/list":
        tools = []
        for t in tool_registry.list_builtin_tools():
            tools.append({
                "name": t.name,
                "description": t.description,
                "inputSchema": t.parameters.to_dict(),
            })
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}}

    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        tool = tool_registry.get(tool_name)
        if not tool:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Tool not found: {tool_name}"}}
        # 同步执行（MCP Server 端点不传入 db，工具内部自行获取）
        try:
            import asyncio
            from app.database import SessionLocal
            db = SessionLocal()
            try:
                result = asyncio.get_event_loop().run_until_complete(
                    tool.execute(arguments, db, project_id=None, user_id=None)
                )
            finally:
                db.close()
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32000, "message": str(e)}}

    elif method == "notifications/initialized":
        return {}

    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown method: {method}"}}
