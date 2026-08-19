"""
Chat 智能助手 Agent（Function Calling 重构版）

支持：
- 原生 Function Calling（bind_tools）多轮工具调用
- 进度事件推送（intent_recognition → knowledge_search → thinking → tool_calling → generating）
- 知识库检索增强（RAG）
- Skill 匹配钩子（阶段三填充）
- 不支持 Function Calling 的模型自动降级为两步式
"""
import json
import logging
import time
from typing import Optional, List, Dict, Any, AsyncGenerator

from sqlalchemy.orm import Session
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage, SystemMessage

from app.agents.llm_factory import llm_factory
from app.agents.tools.registry import tool_registry
from app.agents.progress import progress, ProgressNode, get_tool_label
from app.agents.base_agent import BaseAgent
from app.services.knowledge_base import knowledge_base_service

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是 AITS 智能测试管理平台的助手，专业、简洁、有帮助。

你可以帮助用户：
- 解答测试相关的理论和方法论问题
- 分析测试策略和用例设计思路
- 解释缺陷分析方法和质量保障实践
- 基于项目知识库回答项目相关问题
- 提供自动化测试和脚本编写建议
- 调用工具查询项目数据、创建缺陷等

【重要规则 - 工具调用】
1. 当用户的问题涉及系统中的任何数据（项目数量、用例数量、缺陷列表、测试计划、执行记录、版本、需求、报告、接口等）时，**必须先调用对应工具查询数据**，绝对不能凭记忆或猜测回答。
2. 例如：用户问"有多少个项目"→ 调用 list_projects；问"有哪些用例"→ 调用 list_cases；问"缺陷情况"→ 调用 list_defects。
3. **绝对禁止输出 Python 代码或代码片段来代替工具调用**。如果需要获取数据，必须通过工具调用，不要自己写代码。
4. 调用工具后，基于工具返回的真实数据回答，并标注数据来源。
5. 如果没有合适的工具，才直接回答，并说明无法查询实时数据。

回答要求：
1. 用中文回答
2. 简洁明了，重点突出
3. 涉及代码时使用代码块
4. 如果有工具返回的数据，请基于数据回答，并标注数据来源
5. 不确定的内容如实说明，不要编造

{knowledge_context}
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
        """BaseAgent 抽象方法实现"""
        message = kwargs.get("message", "")
        history = kwargs.get("history", [])
        return {"content": self.chat(message, history)}

    # ---------- 知识库 ----------

    async def search_knowledge(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """异步知识库检索（offload 到线程池，避免阻塞事件循环）"""
        if not self.project_id:
            return []
        try:
            import asyncio
            results = await asyncio.to_thread(
                knowledge_base_service.search,
                db=self.db, project_id=self.project_id, query=query, top_k=top_k,
            )
            return results if isinstance(results, list) else []
        except Exception as e:
            logger.warning(f"知识库检索失败: {e}")
            return []

    def _build_knowledge_context(self, results: List[Dict[str, Any]]) -> str:
        if not results:
            return ""
        parts = ["\n【知识库参考资料】"]
        for i, item in enumerate(results, 1):
            title = item.get("title", f"文档{i}")
            content = item.get("content", item.get("text", ""))
            score = item.get("score", item.get("similarity", ""))
            if len(content) > 500:
                content = content[:500] + "..."
            parts.append(f"\n[{i}] {title}" + (f" (相关度: {score:.2f})" if isinstance(score, (int, float)) else ""))
            parts.append(content)
        return "\n".join(parts)

    # ---------- 历史消息处理 ----------

    MAX_HISTORY_MESSAGES = 20

    def _prepare_history(self, history: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        P3: 智能历史截断
        - 超过 MAX_HISTORY_MESSAGES 时，保留首条用户消息（上下文锚点）+ 最近消息
        - 避免长对话内存占用过高和 token 超限
        """
        if not history or len(history) <= self.MAX_HISTORY_MESSAGES:
            return history

        first_user = None
        for h in history:
            if h.get("role") == "user":
                first_user = h
                break

        recent = history[-(self.MAX_HISTORY_MESSAGES - 1):]
        if first_user and first_user not in recent:
            return [first_user, {"role": "system", "content": "[历史消息已截断，保留上下文锚点和最近对话]"}] + recent
        return recent

    @staticmethod
    def _extract_tool_calls(response) -> List[Dict[str, Any]]:
        """
        兼容提取工具调用（不同 provider / API 格式字段位置不同）

        支持格式：
        1. LangChain 标准：response.tool_calls = [{"name":..., "args":{...}, "id":...}]
        2. OpenAI 原始：response.additional_kwargs["tool_calls"] = [{"id":..., "type":"function", "function":{"name":..., "arguments":"{...}"}}]
        3. Responses API 扁平格式：[{"name":..., "arguments":{...}, "id":...}]
        """
        tool_calls = []

        # 方式1: LangChain 标准属性
        if hasattr(response, 'tool_calls') and response.tool_calls:
            for tc in response.tool_calls:
                if isinstance(tc, dict):
                    name = tc.get("name", "")
                    args = tc.get("args", tc.get("arguments", {}))
                    # arguments 可能是 JSON 字符串
                    if isinstance(args, str):
                        try: args = json.loads(args)
                        except: args = {}
                    tool_calls.append({"name": name, "args": args, "id": tc.get("id", "")})

        # 方式2: additional_kwargs（部分 provider）
        if not tool_calls and hasattr(response, 'additional_kwargs') and response.additional_kwargs:
            raw_tcs = response.additional_kwargs.get("tool_calls", [])
            for tc in raw_tcs:
                func = tc.get("function", {})
                name = func.get("name", tc.get("name", ""))
                args_str = func.get("arguments", tc.get("arguments", "{}"))
                if isinstance(args_str, str):
                    try: args = json.loads(args_str)
                    except: args = {}
                else:
                    args = args_str
                tool_calls.append({"name": name, "args": args, "id": tc.get("id", "")})

        return tool_calls

    @staticmethod
    def _try_extract_tool_from_text(content: str, tool_names: List[str]) -> Optional[Dict[str, Any]]:
        """
        兜底：从模型输出的文本中提取工具调用

        部分模型/服务不支持原生 Function Calling，会输出代码或自然语言描述工具调用。
        此方法检测文本中是否提到工具名，尝试构造工具调用。

        支持的模式：
        1. 直接提到工具名：如"调用 list_projects 工具"
        2. 代码片段：如 list_projects() 或 list_projects({...})
        3. JSON 格式：如 {"name": "list_projects", "args": {...}}
        """
        import re
        if not content or len(content) > 3000:
            return None

        # 模式1: 检测 JSON 格式的工具调用
        json_match = re.search(r'\{["\']name["\']:\s*["\'](\w+)["\'].*?\}', content, re.DOTALL)
        if json_match:
            try:
                tc = json.loads(json_match.group(0).replace("'", '"'))
                if tc.get("name") in tool_names:
                    return {"name": tc["name"], "args": tc.get("args", tc.get("arguments", {})), "id": f"fallback_{int(time.time())}"}
            except Exception:
                pass

        # 模式2: 检测工具名 + 括号调用，如 list_projects() 或 list_projects({...})
        for name in tool_names:
            # 匹配 tool_name(...) 或 tool_name({...})
            pattern = rf'{name}\s*\((.*?)\)'
            m = re.search(pattern, content, re.DOTALL)
            if m:
                args_str = m.group(1).strip()
                args = {}
                if args_str:
                    try:
                        args = json.loads(args_str)
                    except Exception:
                        # 尝试解析 key=value 格式
                        for kv in re.findall(r'(\w+)\s*=\s*["\']?([^,\'"]+)["\']?', args_str):
                            args[kv[0]] = kv[1]
                return {"name": name, "args": args, "id": f"fallback_{int(time.time())}"}

        # 模式3: 文本中直接提到工具名（如"调用 list_projects"）
        for name in tool_names:
            if name in content and ('调用' in content or '使用' in content or 'call' in content.lower()):
                return {"name": name, "args": {}, "id": f"fallback_{int(time.time())}"}

        return None

    def _supports_function_calling(self) -> bool:
        """检测当前模型是否支持 Function Calling"""
        try:
            from app.models.llm_config import LLMConfig
            if self.llm_config_id:
                cfg = self.db.query(LLMConfig).filter(LLMConfig.id == self.llm_config_id).first()
                if cfg and hasattr(cfg, 'supports_function_calling'):
                    return bool(cfg.supports_function_calling)
            # 默认尝试使用（大部分 OpenAI 兼容模型支持）
            return True
        except Exception:
            return True

    async def _classify_intent(self, message: str) -> str:
        """用 LLM 显式分类用户意图：data_query / action / knowledge / chat"""
        prompt = f"""用户问题：{message}

请判断用户意图类型，只返回一个英文单词：
- data_query：查询数据（项目、用例、缺陷、报告、需求等列表或统计）
- action：执行操作（创建、修改、删除、执行测试、生成等）
- knowledge：知识问答（概念解释、方法论、需要检索知识库）
- chat：闲聊/通用问答（不需要工具）"""
        try:
            response = await llm_factory.acall_with_fallback(
                self.db, [{"role": "user", "content": prompt}],
                preferred_config_id=self.llm_config_id
            )
            content = (response.content if hasattr(response, 'content') else str(response)).strip().lower()
            for intent in ("data_query", "action", "knowledge", "chat"):
                if intent in content:
                    return intent
        except Exception as e:
            logger.warning(f"意图分类失败，默认 chat: {e}")
        return "chat"

    # ---------- 主对话流程 ----------

    async def chat(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
        use_knowledge: bool = True,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        对话（流式输出，Function Calling 多轮工具调用）

        Yields:
            事件字典: progress / tool_call / tool_result / knowledge / content / done / error
        """
        history = history or []
        start_time = time.time()

        try:
            from app.agents.progress import ProgressManager

            # 1. 意图分类
            intent = await self._classify_intent(message)
            logger.info(f"用户意图分类: {intent} | 问题: {message[:50]}")

            # 2. Skill 匹配
            skill = None
            skill_name = None
            try:
                from app.agents.skill_engine import skill_engine
                skill = await skill_engine.match_llm(message, self.project_id, self.db)
                if skill:
                    skill_engine._register_skill_scripts(skill)
                    skill_name = skill.title
            except (ImportError, Exception) as e:
                logger.warning(f"Skill 匹配异常: {e}")

            # 3. 初始化动态进度计划
            pm = ProgressManager()
            yield pm.init_plan(intent, use_knowledge=use_knowledge and bool(self.project_id), skill_name=skill_name)

            # 4. 意图解析完成
            yield pm.start("intent")
            yield pm.done("intent")

            # 5. 知识库检索
            knowledge_results = []
            if use_knowledge and self.project_id:
                if "knowledge" in pm._step_index:
                    yield pm.start("knowledge")
                knowledge_results = await self.search_knowledge(message)
                if knowledge_results:
                    yield {
                        "type": "knowledge",
                        "results": [
                            {"title": r.get("title", ""), "content": r.get("content", "")[:300],
                             "doc_id": r.get("doc_id"), "similarity": round(r.get("similarity", 0), 4)}
                            for r in knowledge_results[:5]
                        ],
                    }
                if "knowledge" in pm._step_index:
                    yield pm.done("knowledge")

            # 6. 确定查询数据源 / 校验参数（仅 data_query/action 意图）
            if "tool_plan" in pm._step_index:
                yield pm.start("tool_plan")
                yield pm.done("tool_plan")
            if "validate" in pm._step_index:
                yield pm.start("validate")
                yield pm.done("validate")

            # 7. 执行工具调用 + 生成回答
            if self._supports_function_calling():
                async for event in self._chat_with_tools(message, history, knowledge_results, skill, pm):
                    yield event
            else:
                async for event in self._chat_legacy(message, history, knowledge_results, pm):
                    yield event

            yield pm.snapshot()
            yield {"type": "done"}

        except Exception as e:
            logger.error(f"Chat 对话失败: {e}", exc_info=True)
            yield {"type": "error", "message": str(e)}
        finally:
            # 清理本次对话注册的 Skill 脚本工具
            try:
                from app.agents.skill_engine import skill_engine
                skill_engine.cleanup()
            except Exception:
                pass

    # ---------- Function Calling 流程 ----------

    async def _chat_with_tools(
        self,
        message: str,
        history: List[Dict[str, str]],
        knowledge_results: List[Dict[str, Any]],
        skill=None,
        pm=None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """使用原生 bind_tools 的对话流程"""
        knowledge_context = self._build_knowledge_context(knowledge_results)
        system_content = SYSTEM_PROMPT.format(knowledge_context=knowledge_context)

        # 如果命中 Skill，使用 Skill 的 System Prompt
        if skill and skill.skill_config:
            skill_system = skill.skill_config.get("system_prompt", "")
            if skill_system:
                system_content = skill_system + "\n\n" + knowledge_context

        messages: List = [SystemMessage(content=system_content)]
        for h in self._prepare_history(history):
            if h.get("role") == "user":
                messages.append(HumanMessage(content=h.get("content", "")))
            elif h.get("role") == "assistant":
                messages.append(AIMessage(content=h.get("content", "")))
            elif h.get("role") == "system":
                messages.append(SystemMessage(content=h.get("content", "")))
        messages.append(HumanMessage(content=message))

        # 获取 LLM 和工具
        llm, _ = llm_factory.get_llm_with_fallback(self.db, preferred_config_id=self.llm_config_id)

        # 安全措施：如果工具未注册（startup 事件未触发），自动注册
        if len(tool_registry.list_tools()) == 0:
            try:
                from app.agents.tools.builtin import register_builtin_tools
                register_builtin_tools()
                logger.info("工具未注册，已自动注册内置工具")
            except Exception as e:
                logger.warning(f"自动注册工具失败: {e}")

        # 限定工具集（Skill 模式下用白名单）
        if skill and skill.skill_config and skill.skill_config.get("allowed_tools"):
            allowed = skill.skill_config["allowed_tools"]
            tool_schemas = [t.to_function_schema() for t in tool_registry.list_tools() if t.name in allowed]
        else:
            # 发送全部工具，确保模型知道所有可用能力
            tool_schemas = tool_registry.get_function_schemas(self.project_id)

        max_rounds = 10
        if skill and skill.skill_config:
            max_rounds = skill.skill_config.get("max_tool_calls", 10)

        for round_idx in range(max_rounds):
            # 思考中
            yield progress(ProgressNode.THINKING, "思考中...", "running")

            try:
                # 使用 tool_choice="auto" 让模型自主决定是否调用工具
                llm_with_tools = llm.bind_tools(tool_schemas, tool_choice="auto") if tool_schemas else llm
                response = await llm_with_tools.ainvoke(messages)
            except Exception as e:
                logger.warning(f"bind_tools 调用失败，尝试不带 tool_choice: {e}")
                try:
                    llm_with_tools = llm.bind_tools(tool_schemas) if tool_schemas else llm
                    response = await llm_with_tools.ainvoke(messages)
                except Exception as e2:
                    logger.warning(f"bind_tools 完全失败，降级为普通对话: {e2}")
                    yield progress(ProgressNode.THINKING, "思考中...", "done")
                    async for chunk in self._stream_final(llm, messages):
                        yield chunk
                    return

            yield progress(ProgressNode.THINKING, "思考中...", "done")
            messages.append(response)

            # 兼容提取工具调用（不同 provider 字段位置不同）
            tool_calls = self._extract_tool_calls(response)

            # 兜底：模型未输出结构化 tool_calls，但文本中提到了工具名
            # 部分模型/服务不支持原生 FC，会输出代码或自然语言描述工具调用
            if not tool_calls and response.content and round_idx < max_rounds - 1:
                # 搜索全部已注册工具，不限于本次发送的 schemas
                all_tool_names = [t.name for t in tool_registry.list_tools(self.project_id)]
                fallback_tc = self._try_extract_tool_from_text(str(response.content), all_tool_names)
                if fallback_tc:
                    logger.info(f"文本兜底提取到工具调用: {fallback_tc['name']}")
                    tool_calls = [fallback_tc]
                    # 从 content 中移除工具调用部分，避免重复输出
                    response.content = ""

            # 没有工具调用
            if not tool_calls:
                # 空内容兜底：模型可能返回空 content，追加引导提示后继续
                if not response.content or not str(response.content).strip():
                    if round_idx < max_rounds - 1:
                        logger.info(f"第 {round_idx+1} 轮返回空内容，追加引导提示继续")
                        messages.append(HumanMessage(content="请根据以上工具返回的结果，用中文回答用户的问题。如果没有相关数据，请如实说明。"))
                        continue
                if pm:
                    if "organize" in pm._step_index:
                        yield pm.start("organize")
                        yield pm.done("organize")
                    yield pm.start("answer")
                else:
                    yield progress(ProgressNode.GENERATING, "生成回答中...", "running")
                if response.content:
                    yield {"type": "content", "content": response.content}
                else:
                    # 最终输出使用绑定 tools 的 LLM（消息中含 ToolMessage）
                    async for chunk in self._stream_final(llm_with_tools, messages):
                        yield chunk
                if pm:
                    yield pm.done("answer")
                else:
                    yield progress(ProgressNode.GENERATING, "生成回答中...", "done")
                return

            # 有工具调用 → 逐个执行
            for tc in tool_calls:
                tool_name = tc["name"]
                tool_args = tc.get("args", {})
                tool_call_id = tc.get("id") or f"call_{round_idx}_{tool_name}_{int(time.time())}"

                # 动态进度：追加工具步骤
                tool_node_id = None
                if pm:
                    tool_node_id = pm.add_tool_step(tool_name, tool_args)
                    yield pm.snapshot()

                yield {"type": "tool_call", "tool_call": {"name": tool_name, "args": tool_args, "status": "running"}}

                tool_start = time.time()
                result = await tool_registry.execute(tool_name, tool_args, self.db, self.project_id, self.user_id)
                duration = round(time.time() - tool_start, 2)

                success = result.get("success", False)
                if pm and tool_node_id:
                    pm.done_tool_step(tool_node_id)
                    yield pm.snapshot()
                yield {
                    "type": "tool_result",
                    "tool_call": {
                        "name": tool_name, "args": tool_args,
                        "status": "success" if success else "failed",
                        "result": result.get("result") if success else result.get("error"),
                        "duration": duration,
                    },
                }

                # 将工具结果加入消息
                tool_content = json.dumps(result.get("result") if success else {"error": result.get("error")}, ensure_ascii=False)
                messages.append(ToolMessage(content=tool_content, tool_call_id=tool_call_id))

        # 整理结果 + 生成回答
        if pm:
            if "organize" in pm._step_index:
                yield pm.start("organize")
                yield pm.done("organize")
            if "verify" in pm._step_index:
                yield pm.start("verify")
                yield pm.done("verify")
            yield pm.start("answer")
        else:
            yield progress(ProgressNode.GENERATING, "生成回答中...", "running")
        llm_with_tools = llm.bind_tools(tool_schemas) if tool_schemas else llm
        async for chunk in self._stream_final(llm_with_tools, messages):
            yield chunk
        if pm:
            yield pm.done("answer")
        else:
            yield progress(ProgressNode.GENERATING, "生成回答中...", "done")

    async def _stream_final(self, llm, messages: List) -> AsyncGenerator[Dict[str, Any], None]:
        """流式输出最终回答"""
        try:
            if hasattr(llm, 'astream'):
                async for chunk in llm.astream(messages):
                    content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    if content:
                        yield {"type": "content", "content": content}
            else:
                response = await llm.ainvoke(messages)
                content = response.content if hasattr(response, 'content') else str(response)
                yield {"type": "content", "content": content}
        except Exception as e:
            logger.error(f"流式输出失败: {e}", exc_info=True)
            yield {"type": "content", "content": f"\n\n抱歉，回答生成时出现错误：{str(e)}"}

    # ---------- 降级流程（两步式） ----------

    async def _chat_legacy(
        self,
        message: str,
        history: List[Dict[str, str]],
        knowledge_results: List[Dict[str, Any]],
        pm=None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """不支持 Function Calling 时的降级流程（两步式）"""
        # 工具决策
        need_tool, tool_name, tool_args = await self._decide_tool_legacy(message)

        tool_result = None
        if need_tool and tool_name:
            # 动态进度：追加工具步骤
            tool_node_id = None
            if pm:
                tool_node_id = pm.add_tool_step(tool_name, tool_args)
                yield pm.snapshot()
            yield {"type": "tool_call", "tool_call": {"name": tool_name, "args": tool_args, "status": "running"}}
            tool_result = await tool_registry.execute(tool_name, tool_args, self.db, self.project_id, self.user_id)
            if pm and tool_node_id:
                pm.done_tool_step(tool_node_id)
                yield pm.snapshot()
            yield {
                "type": "tool_result",
                "tool_call": {
                    "name": tool_name, "args": tool_args,
                    "status": "success" if tool_result.get("success") else "failed",
                    "result": tool_result.get("result") if tool_result.get("success") else tool_result.get("error"),
                },
            }

        # 构建最终回答
        knowledge_context = self._build_knowledge_context(knowledge_results)
        tool_context = ""
        if tool_result:
            tool_context = f"\n【工具调用结果】\n工具: {tool_name}\n返回数据:\n{json.dumps(tool_result, ensure_ascii=False, indent=2)[:2000]}\n"

        system_msg = SYSTEM_PROMPT.format(knowledge_context=knowledge_context) + tool_context
        messages = [{"role": "system", "content": system_msg}]
        for h in self._prepare_history(history):
            if h.get("role") in ("user", "assistant", "system"):
                messages.append({"role": h["role"], "content": h.get("content", "")})
        messages.append({"role": "user", "content": message})

        if pm:
            if "organize" in pm._step_index:
                yield pm.start("organize")
                yield pm.done("organize")
            yield pm.start("answer")
        else:
            yield progress(ProgressNode.GENERATING, "生成回答中...", "running")
        llm, _ = llm_factory.get_llm_with_fallback(self.db, preferred_config_id=self.llm_config_id)
        async for chunk in self._stream_final(llm, messages):
            yield chunk
        if pm:
            yield pm.done("answer")
        else:
            yield progress(ProgressNode.GENERATING, "生成回答中...", "done")

    async def _decide_tool_legacy(self, message: str):
        """两步式工具决策"""
        from app.agents.utils import extract_json
        tools_desc = "\n".join([f"【{t.name}】{t.description}" for t in tool_registry.list_tools(self.project_id)])
        prompt = f"""判断是否需要调用工具。可用工具：
{tools_desc}

需要则输出 JSON：{{"need_tool": true, "tool_name": "工具名", "tool_args": {{}}}}
不需要则输出：{{"need_tool": false}}

用户问题：{message}"""
        try:
            response = await llm_factory.acall_with_fallback(self.db, [{"role": "user", "content": prompt}], preferred_config_id=self.llm_config_id)
            content = response.content if hasattr(response, 'content') else str(response)
            result = extract_json(content.strip())
            if result:
                return result.get("need_tool", False), result.get("tool_name", ""), result.get("tool_args", {})
        except Exception as e:
            logger.warning(f"工具决策失败: {e}")
        return False, "", {}

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
        knowledge_results = await self.search_knowledge(message) if use_knowledge and self.project_id else []
        return {"content": full_content, "knowledge_results": knowledge_results[:5], "tool_calls": tool_calls}
