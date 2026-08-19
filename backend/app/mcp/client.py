"""
MCP Client — 连接外部 MCP Server，拉取工具并注册到 ToolRegistry

支持 SSE 和 stdio 两种传输方式。
SSE 模式遵循标准 MCP Streamable HTTP 协议：
  1. GET 连接 SSE 端点，读取 endpoint 事件获取 POST 地址
  2. 向 endpoint POST JSON-RPC 请求
  3. 从 SSE 流读取响应
"""
import json
import logging
import subprocess
import asyncio
import os
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


def _parse_sse_endpoint(text: str) -> Optional[str]:
    """从 SSE 响应文本中解析 endpoint 事件的 URL

    MCP SSE endpoint 事件格式：
        event: endpoint
        data: {"endpoint": "https://.../messages?sessionId=..."}

    或直接 data 为 URL：
        event: endpoint
        data: /mcp?sessionId=...
    """
    # 按空行分割 SSE 事件
    events = text.split("\n\n")
    for event_block in events:
        lines = event_block.strip().split("\n")
        event_type = ""
        data_lines = []
        for line in lines:
            line = line.strip()
            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].strip())
        if event_type == "endpoint" and data_lines:
            data = data_lines[0]
            # data 可能是 JSON 或纯 URL
            try:
                obj = json.loads(data)
                if isinstance(obj, dict) and obj.get("endpoint"):
                    return obj["endpoint"]
            except Exception:
                pass
            # 纯 URL
            if data.startswith("http") or data.startswith("/"):
                return data
    # 兜底：直接搜索 endpoint 字段
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("data:"):
            data = line[5:].strip()
            try:
                obj = json.loads(data)
                if isinstance(obj, dict) and obj.get("endpoint"):
                    return obj["endpoint"]
            except Exception:
                pass
    return None


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
        self._process = None  # subprocess.Popen 或 asyncio.subprocess.Process
        self._endpoint: Optional[str] = None  # SSE 模式下从 endpoint 事件获取
        self._msg_id: int = 0
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
        """SSE 模式连接（标准 MCP Streamable HTTP 协议）"""
        if not self.url:
            raise ValueError("SSE 模式需要配置 url")

        base_url = self.url.rstrip("/")
        post_url = base_url  # 默认直接 POST 到配置的 URL

        # 步骤1: 尝试 SSE 握手，获取 endpoint
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                async with client.stream(
                    "GET", base_url,
                    headers={"Accept": "text/event-stream"},
                ) as resp:
                    if resp.status_code == 200:
                        # 逐行读取 SSE 流，按空行分隔事件
                        event_lines = []
                        async for line in resp.aiter_lines():
                            if line.strip() == "":
                                # 事件边界：解析当前事件
                                event_text = "\n".join(event_lines)
                                endpoint = _parse_sse_endpoint(event_text)
                                if endpoint:
                                    if endpoint.startswith("/"):
                                        from urllib.parse import urlparse
                                        parsed = urlparse(base_url)
                                        post_url = f"{parsed.scheme}://{parsed.netloc}{endpoint}"
                                    else:
                                        post_url = endpoint
                                    logger.info(f"MCP SSE endpoint: {post_url}")
                                    break
                                event_lines = []
                            else:
                                event_lines.append(line)
                                # 安全限制：读取过多行仍未找到 endpoint
                                if len(event_lines) > 100:
                                    break
        except Exception as e:
            logger.info(f"MCP SSE 握手失败，将直接 POST 到配置 URL: {e}")

        # 兜底：如果没从 SSE 流获取到 endpoint，根据 URL 模式推导
        if post_url == base_url:
            from urllib.parse import urlparse
            parsed = urlparse(base_url)
            path = parsed.path
            # 常见模式：/xxx/sse → /xxx/mcp 或 /xxx/messages
            if path.endswith("/sse"):
                for suffix in ["/mcp", "/messages"]:
                    candidate = f"{parsed.scheme}://{parsed.netloc}{path[:-4]}{suffix}"
                    post_url = candidate
                    logger.info(f"MCP endpoint 兜底推导: {post_url}")
                    break

        self._endpoint = post_url

        # 步骤2: 发送 initialize
        async with httpx.AsyncClient(timeout=20.0) as client:
            init_resp = await client.post(
                post_url,
                json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                      "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "aits-hub", "version": "1.0.0"}}},
                headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
            )
            init_resp.raise_for_status()

            # 响应可能是 JSON 或 SSE 格式
            init_result = self._parse_mcp_response(init_resp)

            # 发送 initialized 通知（部分服务器需要）
            try:
                await client.post(
                    post_url,
                    json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                    headers={"Content-Type": "application/json"},
                )
            except Exception:
                pass

            # 步骤3: 获取工具列表
            tools_resp = await client.post(
                post_url,
                json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
            )
            tools_resp.raise_for_status()
            data = self._parse_mcp_response(tools_resp)
            self.tools = data.get("result", {}).get("tools", [])
            return self.tools

    @staticmethod
    def _parse_mcp_response(resp: httpx.Response) -> Dict[str, Any]:
        """解析 MCP 响应（兼容 JSON 和 SSE 格式）"""
        content_type = resp.headers.get("content-type", "")
        text = resp.text.strip()

        # SSE 格式：逐行解析，找到 data: 开头的 JSON
        if "text/event-stream" in content_type or text.startswith("data:") or "event:" in text[:200]:
            for line in text.split("\n"):
                line = line.strip()
                if line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str:
                        try:
                            return json.loads(data_str)
                        except Exception:
                            continue
            # 尝试整体解析
            try:
                return json.loads(text)
            except Exception:
                return {}

        # 普通 JSON
        try:
            return resp.json()
        except Exception:
            return {}

    async def _connect_stdio(self) -> List[Dict[str, Any]]:
        """stdio 模式连接：启动子进程，完成 MCP 握手，拉取工具列表"""
        if not self.command:
            raise ValueError("stdio 模式需要配置 command")

        import shutil
        # 解析命令：如果 command 包含空格（如 "npx -y xxx"），拆分
        cmd_parts = self.command.split() if self.command else []
        full_cmd = cmd_parts + (self.args or [])
        if not full_cmd:
            raise ValueError("stdio 模式命令为空")

        # 检查命令是否存在
        if not shutil.which(full_cmd[0]):
            raise ValueError(f"命令不存在: {full_cmd[0]}，请确认已安装并在 PATH 中")

        env = {**os.environ, **(self.env_vars or {})}
        logger.info(f"MCP stdio 启动: {' '.join(full_cmd)}")

        try:
            self._process = await asyncio.create_subprocess_exec(
                *full_cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
        except FileNotFoundError as e:
            raise ValueError(f"启动失败: {e}")
        except Exception as e:
            raise ValueError(f"启动子进程失败: {e}")

        self._msg_id = 0

        async def _send_request(method: str, params: dict = None) -> dict:
            """发送 JSON-RPC 请求并等待响应"""
            self._msg_id += 1
            msg_id = self._msg_id
            request = {"jsonrpc": "2.0", "id": msg_id, "method": method}
            if params is not None:
                request["params"] = params
            line = json.dumps(request) + "\n"
            self._process.stdin.write(line.encode())
            await self._process.stdin.drain()

            # 读取响应（跳过 notification 消息）
            while True:
                try:
                    raw = await asyncio.wait_for(self._process.stdout.readline(), timeout=30.0)
                except asyncio.TimeoutError:
                    # 读取 stderr 用于调试
                    stderr_data = ""
                    try:
                        stderr_data = (await asyncio.wait_for(self._process.stderr.read(4096), timeout=1.0)).decode(errors="replace")
                    except Exception:
                        pass
                    raise TimeoutError(f"MCP {method} 超时，stderr: {stderr_data[:500]}")
                if not raw:
                    raise ConnectionError("MCP 进程 stdout 已关闭")
                try:
                    data = json.loads(raw.decode().strip())
                except json.JSONDecodeError:
                    continue  # 跳过非 JSON 行
                # 只处理对应 id 的响应，跳过 notification
                if data.get("id") == msg_id and "result" in data:
                    return data["result"]
                if data.get("id") == msg_id and "error" in data:
                    raise RuntimeError(f"MCP {method} 错误: {data['error']}")

        # 1. initialize
        await _send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "aits-hub", "version": "1.0.0"},
        })

        # 2. notifications/initialized（不需要响应）
        self._process.stdin.write((json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n").encode())
        await self._process.stdin.drain()

        # 3. tools/list
        result = await _send_request("tools/list")
        self.tools = result.get("tools", [])
        logger.info(f"MCP stdio {self.name} 连接成功，获取 {len(self.tools)} 个工具")
        return self.tools

    async def call_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        """调用远程工具"""
        if self.transport == "sse":
            post_url = self._endpoint or self.url.rstrip("/")
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    post_url,
                    json={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": tool_name, "arguments": args}},
                    headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
                )
                resp.raise_for_status()
                data = self._parse_mcp_response(resp)
                return data.get("result", {})
        elif self.transport == "stdio" and self._process:
            self._msg_id += 1
            msg_id = self._msg_id
            request = {"jsonrpc": "2.0", "id": msg_id, "method": "tools/call",
                       "params": {"name": tool_name, "arguments": args}}
            self._process.stdin.write((json.dumps(request) + "\n").encode())
            await self._process.stdin.drain()
            while True:
                try:
                    raw = await asyncio.wait_for(self._process.stdout.readline(), timeout=60.0)
                except asyncio.TimeoutError:
                    raise TimeoutError(f"MCP 工具调用超时: {tool_name}")
                if not raw:
                    raise ConnectionError("MCP 进程 stdout 已关闭")
                try:
                    data = json.loads(raw.decode().strip())
                except json.JSONDecodeError:
                    continue
                if data.get("id") == msg_id and "result" in data:
                    return data["result"]
                if data.get("id") == msg_id and "error" in data:
                    raise RuntimeError(f"MCP 工具调用错误: {data['error']}")

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
