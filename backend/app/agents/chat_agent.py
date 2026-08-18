"""
Chat 智能助手 Agent

支持意图识别、知识库检索增强、MCP工具调用
"""
import json
import logging
from typing import Optional, List, Dict, Any, AsyncGenerator, Tuple

from sqlalchemy.orm import Session

from app.agents.llm_factory import llm_factory
from app.agents.mcp_tools import mcp_registry
from app.agents.base_agent import BaseAgent
from app.services.knowledge_base import knowledge_base_service

logger = logging.getLogger(__name__)

# 工具调用判断提示词
TOOL_DECISION_PROMPT = """你是 AITS 智能测试管理平台的助手。请判断用户的问题是否需要调用工具来获取数据或执行操作。

可用工具：
{tools_description}

请判断是否需要调用工具。如果需要，请输出 JSON 格式：
{{"need_tool": true, "tool_name": "工具名称", "tool_args": {{"参数名": "参数值"}}}}

如果不需要调用工具，直接回答用户问题，请输出：
{{"need_tool": false}}

注意：
- 查询项目统计、用例列表、缺陷列表、缺陷分析、知识库检索、创建缺陷等需要调用工具
- 纯理论问题、方法论解释、通用问答不需要调用工具
- 只输出 JSON，不要输出其他内容

用户问题：{question}
"""

# 系统提示词
SYSTEM_PROMPT = """你是 AITS 智能测试管理平台的助手，专业、简洁、有帮助。

你可以帮助用户：
- 解答测试相关的理论和方法论问题
- 分析测试策略和用例设计思路
- 解释缺陷分析方法和质量保障实践
- 基于项目知识库回答项目相关问题
- 提供自动化测试和脚本编写建议
- 调用工具查询项目数据、创建缺陷等

回答要求：
1. 用中文回答
2. 简洁明了，重点突出
3. 涉及代码时使用代码块
4. 如果有工具返回的数据，请基于数据回答，并标注数据来源
5. 不确定的内容如实说明，不要编造

{knowledge_context}

{tool_result_context}
"""


class ChatAgent(BaseAgent):
    """Chat 智能助手"""

    def __init__(
        self,
        db: Session,
        project_id: Optional[int] = None,
        llm_config_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ):
        super().__init__(db, agent_name="chat_agent", project_id=project_id, llm_config_id=llm_config_id)
        self.user_id = user_id

    def run(self, **kwargs) -> Dict[str, Any]:
        """BaseAgent 抽象方法实现：同步聊天入口"""
        message = kwargs.get("message", "")
        history = kwargs.get("history", [])
        return {"content": self.chat(message, history)}

    def _get_tools_description(self) -> str:
        """获取工具描述文本"""
        lines = []
        for tool in mcp_registry.list_tools():
            params = []
            props = tool.parameters.get("properties", {})
            for pname, pinfo in props.items():
                required = pname in tool.parameters.get("required", [])
                params.append(f"  - {pname}: {pinfo.get('description', '')} {'(必填)' if required else '(可选)'}")
            lines.append(f"【{tool.name}】{tool.description}\n" + "\n".join(params))
        return "\n\n".join(lines)

    async def _decide_tool(self, message: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        判断是否需要调用工具

        Returns:
            (need_tool, tool_name, tool_args)
        """
        tools_desc = self._get_tools_description()
        prompt = TOOL_DECISION_PROMPT.format(
            tools_description=tools_desc,
            question=message,
        )

        try:
            messages = [{"role": "user", "content": prompt}]
            response = await llm_factory.acall_with_fallback(
                self.db, messages, preferred_config_id=self.llm_config_id
            )
            content = response.content if hasattr(response, 'content') else str(response)
            content = content.strip()
            logger.info(f"工具决策原始返回: {content[:200]}")

            # 尝试解析 JSON
            from app.agents.utils import extract_json
            result = extract_json(content)
            if result:
                need_tool = result.get("need_tool", False)
                tool_name = result.get("tool_name", "")
                tool_args = result.get("tool_args", {})
                logger.info(f"工具决策结果: need_tool={need_tool}, tool_name={tool_name}, args={tool_args}")
                return need_tool, tool_name, tool_args
            logger.warning(f"工具决策 JSON 解析失败, content: {content[:200]}")
            return False, "", {}
        except Exception as e:
            logger.warning(f"工具决策失败，降级为不调用工具: {e}", exc_info=True)
            return False, "", {}

    def search_knowledge(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """检索知识库"""
        if not self.project_id:
            return []
        try:
            results = knowledge_base_service.search(
                db=self.db,
                project_id=self.project_id,
                query=query,
                top_k=top_k,
            )
            return results if isinstance(results, list) else []
        except Exception as e:
            logger.warning(f"知识库检索失败: {e}")
            return []

    def _build_knowledge_context(self, knowledge_results: List[Dict[str, Any]]) -> str:
        """构建知识库上下文"""
        if not knowledge_results:
            return ""

        context_parts = ["\n【知识库参考资料】"]
        for i, item in enumerate(knowledge_results, 1):
            title = item.get("title", f"文档{i}")
            content = item.get("content", item.get("text", ""))
            score = item.get("score", item.get("similarity", ""))
            if len(content) > 500:
                content = content[:500] + "..."
            context_parts.append(f"\n[{i}] {title}" + (f" (相关度: {score:.2f})" if score else ""))
            context_parts.append(content)

        return "\n".join(context_parts)

    def _build_tool_result_context(self, tool_name: str, tool_result: Dict[str, Any]) -> str:
        """构建工具结果上下文"""
        if not tool_result:
            return ""
        result_str = json.dumps(tool_result, ensure_ascii=False, indent=2)
        if len(result_str) > 2000:
            result_str = result_str[:2000] + "\n... (数据已截断)"
        return f"\n【工具调用结果】\n工具: {tool_name}\n返回数据:\n{result_str}\n"

    async def chat(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
        use_knowledge: bool = True,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        对话（流式输出，支持工具调用）

        Yields:
            事件字典: {"type": "tool_call"|"tool_result"|"content", ...}
        """
        history = history or []

        # 1. 判断是否需要调用工具
        need_tool, tool_name, tool_args = await self._decide_tool(message)
        tool_result = None

        if need_tool and tool_name:
            logger.info(f"需要调用工具: {tool_name}, args: {tool_args}")
            yield {"type": "tool_call", "tool_call": {"name": tool_name, "args": tool_args, "status": "running"}}

            # 执行工具
            tool_result = await mcp_registry.execute_tool(
                tool_name, tool_args, self.db, self.project_id, self.user_id
            )

            yield {
                "type": "tool_result",
                "tool_call": {
                    "name": tool_name,
                    "args": tool_args,
                    "status": "success" if tool_result.get("success") else "failed",
                    "result": tool_result.get("result") if tool_result.get("success") else tool_result.get("error"),
                },
            }

        # 2. 知识库检索
        knowledge_results = []
        if use_knowledge and self.project_id and not need_tool:
            knowledge_results = self.search_knowledge(message)
            if knowledge_results:
                yield {
                    "type": "knowledge",
                    "results": [
                        {
                            "title": r.get("title", ""),
                            "content": r.get("content", "")[:300],
                            "doc_id": r.get("doc_id"),
                            "similarity": round(r.get("similarity", 0), 4),
                        }
                        for r in knowledge_results[:5]
                    ],
                }

        # 3. 构建消息
        knowledge_context = self._build_knowledge_context(knowledge_results)
        tool_result_context = self._build_tool_result_context(tool_name, tool_result) if tool_result else ""

        system_msg = SYSTEM_PROMPT.format(
            knowledge_context=knowledge_context,
            tool_result_context=tool_result_context,
        )

        messages = [{"role": "system", "content": system_msg}]

        # 添加历史对话
        for h in history[-10:]:
            if h.get("role") == "user":
                messages.append({"role": "user", "content": h.get("content", "")})
            elif h.get("role") == "assistant":
                messages.append({"role": "assistant", "content": h.get("content", "")})

        messages.append({"role": "user", "content": message})

        # 4. 调用 LLM（流式）
        try:
            llm, _ = llm_factory.get_llm_with_fallback(self.db, preferred_config_id=self.llm_config_id)
            if hasattr(llm, 'astream'):
                async for chunk in llm.astream(messages):
                    content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    if content:
                        yield {"type": "content", "content": content}
            else:
                response = await llm_factory.acall_with_fallback(
                    self.db, messages, preferred_config_id=self.llm_config_id
                )
                content = response.content if hasattr(response, 'content') else str(response)
                yield {"type": "content", "content": content}
        except Exception as e:
            logger.error(f"Chat LLM 调用失败: {e}", exc_info=True)
            yield {"type": "content", "content": f"\n\n抱歉，回答生成时出现错误：{str(e)}"}

    async def chat_non_stream(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
        use_knowledge: bool = True,
    ) -> Dict[str, Any]:
        """对话（非流式）"""
        full_content = ""
        tool_calls = []

        async for event in self.chat(message, history, use_knowledge):
            if event["type"] == "content":
                full_content += event["content"]
            elif event["type"] == "tool_call":
                tool_calls.append(event["tool_call"])
            elif event["type"] == "tool_result":
                if tool_calls:
                    tool_calls[-1].update(event["tool_call"])

        knowledge_results = []
        if use_knowledge and self.project_id:
            knowledge_results = self.search_knowledge(message)

        return {
            "content": full_content,
            "knowledge_results": knowledge_results[:5],
            "tool_calls": tool_calls,
        }
