"""
Responses API 客户端（OpenAI /v1/responses 接口）

与 Chat Completions 的区别：
- 请求：input 字段（字符串或消息数组），tools 扁平化（type:function + name + parameters）
- 响应：output 数组，包含 message 和 function_call 项
- 工具调用：function_call 类型，arguments 为 JSON 字符串
"""
import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx
from langchain_core.callbacks import AsyncCallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

logger = logging.getLogger(__name__)


class ResponsesChat(BaseChatModel):
    """OpenAI Responses API 兼容的 Chat Model"""

    model: str
    api_key: str = ""
    base_url: str = ""
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 60

    @property
    def _llm_type(self) -> str:
        return "responses_api"

    def _convert_messages_to_input(self, messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        """将 LangChain 消息转为 Responses API 的 input 格式"""
        items = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                items.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                items.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                content = msg.content if msg.content else ""
                # 处理 tool_calls
                tool_calls = []
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_calls.append({
                            "type": "function_call",
                            "name": tc.get("name", ""),
                            "arguments": json.dumps(tc.get("args", {}), ensure_ascii=False),
                            "call_id": tc.get("id", ""),
                        })
                if tool_calls:
                    items.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
                else:
                    items.append({"role": "assistant", "content": content})
            elif isinstance(msg, ToolMessage):
                items.append({
                    "type": "function_call_output",
                    "call_id": msg.tool_call_id,
                    "output": msg.content,
                })
        return items

    def _convert_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """将 Chat Completions 格式的 tools 转为 Responses API 扁平化格式"""
        result = []
        for t in tools:
            if t.get("type") == "function" and "function" in t:
                # Chat Completions 格式 → 扁平化
                func = t["function"]
                result.append({
                    "type": "function",
                    "name": func.get("name", ""),
                    "description": func.get("description", ""),
                    "parameters": func.get("parameters", {}),
                })
            else:
                # 已经是扁平化格式
                result.append(t)
        return result

    def _parse_response(self, resp_data: Dict[str, Any]) -> ChatResult:
        """解析 Responses API 响应为 LangChain ChatResult"""
        output = resp_data.get("output", [])
        content_parts = []
        tool_calls = []

        for item in output:
            item_type = item.get("type", "")
            if item_type == "message":
                for c in item.get("content", []):
                    if c.get("type") in ("output_text", "text"):
                        content_parts.append(c.get("text", ""))
            elif item_type == "function_call":
                args_str = item.get("arguments", "{}")
                try:
                    args = json.loads(args_str) if isinstance(args_str, str) else args_str
                except Exception:
                    args = {}
                tool_calls.append({
                    "name": item.get("name", ""),
                    "args": args,
                    "id": item.get("call_id", item.get("id", "")),
                })

        content = "\n".join(content_parts) if content_parts else ""
        ai_msg = AIMessage(content=content, tool_calls=tool_calls if tool_calls else None)
        # 同时写入 additional_kwargs 兼容旧格式
        if tool_calls:
            ai_msg.additional_kwargs = {
                "tool_calls": [
                    {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": json.dumps(tc["args"], ensure_ascii=False)}}
                    for tc in tool_calls
                ]
            }
        return ChatResult(generations=[ChatGeneration(message=ai_msg)])

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        """同步生成（同步调用异步）"""
        import asyncio
        return asyncio.run(self._agenerate(messages, stop, run_manager, **kwargs))

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        url = f"{self.base_url.rstrip('/')}/responses"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}" if self.api_key else "",
        }
        payload = {
            "model": self.model,
            "input": self._convert_messages_to_input(messages),
            "max_output_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        # 工具
        tools = kwargs.get("tools", [])
        if tools:
            payload["tools"] = self._convert_tools(tools)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        return self._parse_response(data)

    def bind_tools(self, tools, **kwargs):
        """绑定工具，存储供 _agenerate 使用"""
        return self.bind(tools=tools, **kwargs)

    async def astream(self, messages, **kwargs) -> AsyncIterator[BaseMessage]:
        """流式输出（简化版：非流式调用后逐字 yield）"""
        result = await self._agenerate(messages, **kwargs)
        msg = result.generations[0].message
        if msg.content:
            for char in msg.content:
                yield AIMessage(content=char)
        else:
            yield msg
