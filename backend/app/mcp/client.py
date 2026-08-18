"""
MCP Client — 连接外部 MCP Server，拉取工具并注册到 ToolRegistry

支持 SSE 和 stdio 两种传输方式。
"""
import json
import logging
import subprocess
from typing import Any, Dict, List, Optional

import httpx

from app.agents.tools.base import BaseTool, ToolParameter
from app.agents.tools.registry import tool_registry

logger = logging.getLogger(__name__)


class MCPRemoteTool(BaseTool):
    """远程 MCP 工具包装"""

    def __init__(self, name: str, description: str, parameters: Dict[str, Any], client: "MCPClient"):
        self.name = name
        self.description = description
        self.parameters = ToolParameter(
            type=parameters.get("type", "object"),
            properties=parameters.get("properties", {}),
            required=parameters.get("required", []),
        )
        self.category = "mcp_remote"
        self._client = client

    async def execute(self, args: Dict[str, Any], db=None, project_id=None, user_id=None) -> Any:
        return await self._client.call_tool(self.name, args)


class MCPClient:
    """MCP 客户端管理器"""

    def __init__(self, connector_id: int, name: str, transport: str = "sse",
                 url: str = "", command: str = "", args: list = None, env_vars: dict = None):
        self.connector_id = connector_id
        self.name = name
        self.transport = transport
        self.url = url
        self.command = command
        self.args = args or []
        self.env_vars = env_vars or {}
        self._process: Optional[subprocess.Popen] = None
        self._client: Optional[httpx.AsyncClient] = None
        self.tools: List[Dict[str, Any]] = []

    async def connect(self) -> List[Dict[str, Any]]:
        """连接 MCP Server 并获取工具列表"""
        if self.transport == "sse":
            return await self._connect_sse()
        elif self.transport == "stdio":
            return await self._connect_stdio()
        else:
            raise ValueError(f"不支持的传输方式: {self.transport}")

    async def _connect_sse(self) -> List[Dict[str, Any]]:
        """SSE 模式连接"""
        if not self.url:
            raise ValueError("SSE 模式需要配置 url")
        async with httpx.AsyncClient(timeout=10.0) as client:
            # MCP initialize + tools/list
            init_resp = await client.post(
                self.url.rstrip("/") + "/mcp",
                json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}}},
                headers={"Content-Type": "application/json"},
            )
            init_resp.raise_for_status()
            tools_resp = await client.post(
                self.url.rstrip("/") + "/mcp",
                json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                headers={"Content-Type": "application/json"},
            )
            tools_resp.raise_for_status()
            data = tools_resp.json()
            self.tools = data.get("result", {}).get("tools", [])
            return self.tools

    async def _connect_stdio(self) -> List[Dict[str, Any]]:
        """stdio 模式连接（简化实现）"""
        if not self.command:
            raise ValueError("stdio 模式需要配置 command")
        # 启动子进程
        self._process = subprocess.Popen(
            [self.command] + self.args,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env={**__import__('os').environ, **self.env_vars},
            text=True,
        )
        # 发送 initialize
        self._process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}}) + "\n")
        self._process.stdin.flush()
        self._process.stdout.readline()
        # 发送 tools/list
        self._process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}) + "\n")
        self._process.stdin.flush()
        line = self._process.stdout.readline()
        data = json.loads(line)
        self.tools = data.get("result", {}).get("tools", [])
        return self.tools

    async def call_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """调用远程工具"""
        if self.transport == "sse":
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    self.url.rstrip("/") + "/mcp",
                    json={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": tool_name, "arguments": args}},
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                return resp.json().get("result", {})
        elif self.transport == "stdio" and self._process:
            self._process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": tool_name, "arguments": args}}) + "\n")
            self._process.stdin.flush()
            line = self._process.stdout.readline()
            return json.loads(line).get("result", {})

    def register_tools(self):
        """将拉取的工具注册到 ToolRegistry"""
        for t in self.tools:
            remote_tool = MCPRemoteTool(
                name=t["name"],
                description=t.get("description", ""),
                parameters=t.get("inputSchema", {"type": "object", "properties": {}}),
                client=self,
            )
            tool_registry.register_mcp_tool(self.name, remote_tool)

    def disconnect(self):
        """断开连接"""
        tool_registry.unregister_mcp_tools(self.name)
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass
            self._process = None
