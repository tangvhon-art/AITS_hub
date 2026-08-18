"""
Skill 执行引擎 — 触发匹配 + 限定工具集执行

Skill = 触发条件 + System Prompt + 工具白名单 + 执行配置
"""
import logging
import re
from typing import Any, Dict, List, Optional, AsyncGenerator

from sqlalchemy.orm import Session
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage, SystemMessage

from app.agents.llm_factory import llm_factory
from app.agents.tools.registry import tool_registry
from app.agents.progress import progress, ProgressNode, get_tool_label

logger = logging.getLogger(__name__)


class SkillEngine:
    """Skill 引擎"""

    def __init__(self):
        self._skills_cache: List = []
        self._cache_dirty = True

    def _load_skills(self, db: Session) -> List:
        """加载所有启用的 Skill"""
        from app.models.skill import Skill
        if self._cache_dirty:
            self._skills_cache = db.query(Skill).filter(
                Skill.is_active == True, Skill.is_deleted == False
            ).order_by(Skill.sort_order.asc()).all()
            self._cache_dirty = False
        return self._skills_cache

    def invalidate_cache(self):
        self._cache_dirty = True

    def match(self, message: str, project_id: Optional[int] = None, db: Optional[Session] = None) -> Optional[Any]:
        """根据触发条件匹配 Skill"""
        if not db:
            return None
        skills = self._load_skills(db)
        for skill in skills:
            if self._match_trigger(message, skill.trigger_config or {}):
                return skill
        return None

    def _match_trigger(self, message: str, config: Dict[str, Any]) -> bool:
        """匹配触发条件"""
        trigger_type = config.get("type", "keyword")
        if trigger_type in ("keyword", "keyword_or_intent"):
            keywords = config.get("keywords", [])
            if keywords and any(kw.lower() in message.lower() for kw in keywords):
                return True
        if trigger_type in ("regex", "keyword_or_intent"):
            pattern = config.get("pattern", "")
            if pattern:
                try:
                    if re.search(pattern, message, re.IGNORECASE):
                        return True
                except re.error:
                    pass
        if trigger_type == "intent":
            # 意图匹配（简化：关键词匹配，后续可接入意图分类模型）
            intent = config.get("intent", "")
            if intent and intent.lower() in message.lower():
                return True
        return False

    async def execute(
        self,
        skill: Any,
        message: str,
        db: Session,
        project_id: Optional[int] = None,
        user_id: Optional[int] = None,
        history: Optional[List[Dict]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """执行 Skill：限定工具集 + 自定义 System Prompt + 工具调用循环"""
        history = history or []
        config = skill.skill_config or {}
        system_prompt = config.get("system_prompt", "你是一个专业助手。")
        allowed_tools = config.get("allowed_tools", [])
        max_rounds = config.get("max_tool_calls", 10)

        # 构建消息
        messages: List = [SystemMessage(content=system_prompt)]
        for h in history[-10:]:
            if h.get("role") == "user":
                messages.append(HumanMessage(content=h.get("content", "")))
            elif h.get("role") == "assistant":
                messages.append(AIMessage(content=h.get("content", "")))
        messages.append(HumanMessage(content=message))

        # 限定工具集
        tool_schemas = []
        if allowed_tools:
            tool_schemas = [
                t.to_function_schema() for t in tool_registry.list_tools()
                if t.name in allowed_tools
            ]

        llm, _ = llm_factory.get_llm_with_fallback(db, preferred_config_id=None)

        for round_idx in range(max_rounds):
            yield progress(ProgressNode.THINKING, "思考中...", "running")
            try:
                llm_with_tools = llm.bind_tools(tool_schemas) if tool_schemas else llm
                response = await llm_with_tools.ainvoke(messages)
            except Exception as e:
                yield progress(ProgressNode.THINKING, "思考中...", "done")
                yield {"type": "error", "message": str(e)}
                return
            yield progress(ProgressNode.THINKING, "思考中...", "done")
            messages.append(response)

            if not response.tool_calls:
                yield progress(ProgressNode.GENERATING, "生成回答中...", "running")
                if response.content:
                    yield {"type": "content", "content": response.content}
                else:
                    async for chunk in self._stream(llm, messages):
                        yield chunk
                yield progress(ProgressNode.GENERATING, "生成回答中...", "done")
                return

            for tc in response.tool_calls:
                tool_name = tc["name"]
                tool_args = tc.get("args", {})
                tool_label = get_tool_label(tool_name)
                yield progress(ProgressNode.TOOL_CALLING, f"调用 {tool_label} 中...", "running", detail=tool_name)
                yield {"type": "tool_call", "tool_call": {"name": tool_name, "args": tool_args, "status": "running"}}
                result = await tool_registry.execute(tool_name, tool_args, db, project_id, user_id)
                yield progress(ProgressNode.TOOL_DONE, f"{tool_label} 完成", "done")
                yield {"type": "tool_result", "tool_call": {
                    "name": tool_name, "args": tool_args,
                    "status": "success" if result.get("success") else "failed",
                    "result": result.get("result") if result.get("success") else result.get("error"),
                }}
                import json
                tool_content = json.dumps(result.get("result") if result.get("success") else {"error": result.get("error")}, ensure_ascii=False)
                messages.append(ToolMessage(content=tool_content, tool_call_id=tc["id"]))

        yield progress(ProgressNode.GENERATING, "生成回答中...", "running")
        async for chunk in self._stream(llm, messages):
            yield chunk
        yield progress(ProgressNode.GENERATING, "生成回答中...", "done")

    async def _stream(self, llm, messages: List) -> AsyncGenerator[Dict[str, Any], None]:
        try:
            async for chunk in llm.astream(messages):
                content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                if content:
                    yield {"type": "content", "content": content}
        except Exception as e:
            yield {"type": "content", "content": f"生成失败: {e}"}


# 全局单例
skill_engine = SkillEngine()
