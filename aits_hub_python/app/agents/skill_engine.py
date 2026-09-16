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
        self._registered_script_tools: List[str] = []  # 本次对话注册的 Skill 脚本工具名
        self._registered_skill_tools: Dict[str, str] = {}  # skill_name -> tool_name，已注册为工具的 Skill

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

    # ==================== Skill 工具注册（暴露给大模型 Function Calling） ====================

    def register_skill_as_tool(self, skill) -> str:
        """
        将单个 Skill 注册为大模型可调用的工具。
        工具名为 skill_{name}，描述为 Skill 的 description。
        返回注册的工具名。
        """
        from app.agents.tools.skill_tool import SkillTool
        import re
        safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", skill.name)
        tool_name = f"skill_{safe_name}"
        # 如果已注册，先注销旧的
        if skill.name in self._registered_skill_tools:
            old_tool = self._registered_skill_tools[skill.name]
            try:
                tool_registry.unregister(old_tool)
            except Exception:
                pass
        tool = SkillTool(skill)
        tool_registry.register(tool)
        self._registered_skill_tools[skill.name] = tool_name
        logger.info(f"Skill 已注册为工具: {tool_name} (skill={skill.name})")
        return tool_name

    def unregister_skill_tool(self, skill_name: str) -> bool:
        """注销某个 Skill 对应的工具"""
        import re
        safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", skill_name)
        tool_name = f"skill_{safe_name}"
        try:
            tool_registry.unregister(tool_name)
            self._registered_skill_tools.pop(skill_name, None)
            logger.info(f"Skill 工具已注销: {tool_name}")
            return True
        except Exception as e:
            logger.warning(f"注销 Skill 工具失败 [{tool_name}]: {e}")
            return False

    def register_all_active_skills(self, db: Session) -> int:
        """
        系统启动时调用：将所有启用的 Skill 批量注册为大模型工具。
        返回成功注册的数量。
        """
        from app.models.skill import Skill
        skills = db.query(Skill).filter(
            Skill.is_active == True, Skill.is_deleted == False
        ).all()
        count = 0
        for skill in skills:
            try:
                self.register_skill_as_tool(skill)
                count += 1
            except Exception as e:
                logger.warning(f"注册 Skill 工具失败 [{skill.name}]: {e}")
        logger.info(f"系统启动：已注册 {count}/{len(skills)} 个 Skill 为工具")
        return count

    def list_registered_skills(self) -> List[Dict[str, str]]:
        """列出所有已注册为工具的 Skill"""
        return [
            {"skill_name": name, "tool_name": tool}
            for name, tool in self._registered_skill_tools.items()
        ]

    def is_registered(self, skill_name: str) -> bool:
        """检查某个 Skill 是否已注册为工具"""
        return skill_name in self._registered_skill_tools

    def resync_skill_tool(self, skill) -> str:
        """Skill 内容更新后，重新注册工具（刷新描述等信息）"""
        return self.register_skill_as_tool(skill)

    def match(self, message: str, project_id: Optional[int] = None, db: Optional[Session] = None) -> Optional[Any]:
        """根据触发条件匹配 Skill（关键词/正则）"""
        if not db:
            return None
        skills = self._load_skills(db)
        for skill in skills:
            if self._match_trigger(message, skill.trigger_config or {}):
                return skill
        return None

    async def match_llm(self, message: str, project_id: Optional[int] = None,
                        db: Optional[Session] = None) -> Optional[Any]:
        """用 LLM 语义匹配 Skill（失败时降级到关键词匹配）"""
        if not db:
            return None
        skills = self._load_skills(db)
        if not skills:
            return None

        # 构建 Skill 列表描述
        skill_list = []
        for i, s in enumerate(skills):
            trigger = s.trigger_config or {}
            keywords = trigger.get("keywords", [])
            skill_list.append(
                f"{i+1}. 名称：{s.name}\n"
                f"   描述：{s.description or ''}\n"
                f"   触发关键词：{', '.join(keywords) if keywords else '无'}"
            )
        skills_text = "\n".join(skill_list)

        prompt = f"""用户问题：{message}

可用 Skill 列表：
{skills_text}

请判断用户问题是否匹配上述某个 Skill。
如果匹配，返回 JSON：{{"matched": true, "skill_index": 序号}}
如果不匹配，返回：{{"matched": false}}
只返回 JSON，不要其他内容。"""

        try:
            from app.agents.utils import extract_json
            response = await llm_factory.acall_with_fallback(
                db, [{"role": "user", "content": prompt}], preferred_config_id=None
            )
            content = response.content if hasattr(response, 'content') else str(response)
            result = extract_json(content.strip())
            if result and result.get("matched"):
                idx = int(result.get("skill_index", 0)) - 1
                if 0 <= idx < len(skills):
                    logger.info(f"LLM 语义匹配到 Skill: {skills[idx].name}")
                    return skills[idx]
        except Exception as e:
            logger.warning(f"LLM Skill 匹配失败，降级到关键词匹配: {e}")

        # 降级到关键词匹配
        return self.match(message, project_id, db)

    def match_and_register(self, message: str, project_id: Optional[int] = None,
                           db: Optional[Session] = None, use_llm: bool = True) -> Optional[Any]:
        """匹配 Skill 并注册其脚本为工具（同步入口，LLM 匹配需提前调用 match_llm）"""
        skill = self.match(message, project_id, db)
        if skill:
            self._register_skill_scripts(skill)
        return skill

    def _register_skill_scripts(self, skill: Any):
        """将 Skill 包中的 Python 脚本注册为工具"""
        from app.agents.tools.skill_tool import SkillScriptTool
        scripts = skill.scripts or {}
        for filename, content in scripts.items():
            if isinstance(filename, str) and filename.endswith('.py'):
                try:
                    tool = SkillScriptTool(skill.name, filename, content)
                    tool_registry.register(tool)
                    self._registered_script_tools.append(tool.name)
                    logger.info(f"注册 Skill 脚本工具: {tool.name}")
                except Exception as e:
                    logger.warning(f"注册 Skill 脚本工具失败 [{filename}]: {e}")

    def cleanup(self):
        """对话结束后注销本次注册的 Skill 脚本工具"""
        for name in self._registered_script_tools:
            try:
                tool_registry.unregister(name)
            except Exception as e:
                logger.warning(f"注销 Skill 脚本工具失败 [{name}]: {e}")
        self._registered_script_tools.clear()

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
