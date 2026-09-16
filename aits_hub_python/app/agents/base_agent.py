"""
Agent 基类抽象

所有 Agent 的统一基类，定义输入/输出/工具/日志规范。
"""
import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.timezone import china_now_naive
from app.agents.llm_factory import llm_factory
from app.agents.model_router import get_model_router

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Agent 基类"""

    agent_type: str = "base"

    def __init__(
        self,
        db_session: Session,
        llm_config_id: Optional[int] = None,
        task_id: Optional[int] = None,
        agent_name: Optional[str] = None,
        project_id: Optional[int] = None,
    ):
        self.db = db_session
        self.llm_config_id = llm_config_id
        self.task_id = task_id
        self.agent_name = agent_name or self.agent_type
        self.project_id = project_id
        self.execution_log: List[Dict[str, Any]] = []
        self.token_usage: Dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        self.start_time: float = 0

    def _log_step(self, action: str, params: Dict[str, Any], status: str, observation: str = ""):
        """记录执行步骤"""
        self.execution_log.append({
            "timestamp": china_now_naive().isoformat(),
            "action": action,
            "params": params,
            "status": status,
            "observation": observation[:500],
        })

    def _call_llm(self, messages: List[Any], **kwargs) -> Any:
        """调用 LLM，通过 ModelRouter 路由模型，带降级和 Token 统计

        kwargs 可选:
            max_tokens: 覆盖配置中的 max_tokens
            temperature: 覆盖配置中的 temperature
        """
        max_tokens_override = kwargs.pop("max_tokens", None)

        if not hasattr(self, '_llm_initialized'):
            self._init_routed_llm(
                agent_type=self.agent_name,
                preferred_config_id=self.llm_config_id,
            )
            self._llm_initialized = True
            logger.info(
                f"_call_llm 初始化完成: agent={self.agent_name}, "
                f"llm_config_id={self.llm_config_id}, "
                f"llm_type={type(self.llm).__name__}, "
                f"max_tokens_override={max_tokens_override}"
            )

        # 如果指定了 max_tokens，用 call_with_fallback 绕过 ModelRouter 缓存的实例
        if max_tokens_override is not None:
            from app.agents.llm_factory import LLMFactory, decrypt_api_key
            from app.models.llm_config import LLMConfig

            configs = self.db.query(LLMConfig).filter(
                LLMConfig.status == "active"
            ).order_by(LLMConfig.priority.asc()).all()

            # 优先使用当前 config_id，其次 is_default
            target_config = None
            if self.llm_config_id:
                target_config = next((c for c in configs if c.id == self.llm_config_id), None)
            if not target_config:
                target_config = next((c for c in configs if c.is_default), None)
            if not target_config and configs:
                target_config = configs[0]

            if target_config:
                factory = LLMFactory()
                self.llm = factory.create_llm(
                    provider=target_config.provider,
                    model_name=target_config.model_name,
                    base_url=target_config.base_url,
                    api_key=decrypt_api_key(target_config.api_key) if target_config.api_key else "",
                    max_tokens=max_tokens_override,
                    temperature=kwargs.get("temperature", target_config.temperature),
                    streaming=target_config.streaming,
                    api_format=target_config.api_format if hasattr(target_config, 'api_format') else "chat_completions",
                )
                self.llm_config_id = target_config.id
                logger.info(f"_call_llm 重建 LLM: config_id={target_config.id}, model={target_config.model_name}, max_tokens={max_tokens_override}")

        # 从 kwargs 中提取 temperature 传给 invoke
        invoke_kwargs = {}
        if "temperature" in kwargs:
            invoke_kwargs["temperature"] = kwargs.pop("temperature")

        logger.info(f"_call_llm 调用 invoke: messages={len(messages)}条, kwargs={invoke_kwargs}")
        response = self.llm.invoke(messages, **invoke_kwargs)

        # 统计 Token
        usage = getattr(response, "usage_metadata", None)
        if usage:
            self.token_usage["prompt_tokens"] += usage.get("input_tokens", 0)
            self.token_usage["completion_tokens"] += usage.get("output_tokens", 0)
            self.token_usage["total_tokens"] += (
                usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
            )
            logger.info(f"_call_llm 响应: prompt_tokens={usage.get('input_tokens', 0)}, completion_tokens={usage.get('output_tokens', 0)}")
        else:
            # 尝试从 response 中获取其他形式的 usage
            content = response.content if hasattr(response, "content") else str(response)
            logger.warning(f"_call_llm 响应无 usage_metadata, content_len={len(content)}, content前200字: {content[:200]}")

        return response

    def _init_routed_llm(
        self,
        agent_type: str,
        data_sensitivity: str = "low",
        preferred_config_id: Optional[int] = None,
    ):
        """
        P2-1: 通过 ModelRouter 按 Agent 类型和数据敏感度路由模型。
        高敏感度数据优先使用自部署模型，失败自动降级。
        """
        router = get_model_router(self.db)
        self.llm, config_id = router.get_model_for_agent(
            agent_type=agent_type,
            project_id=getattr(self, 'project_id', None),
            data_sensitivity=data_sensitivity,
            preferred_config_id=preferred_config_id,
        )
        self.llm_config_id = config_id
        return self.llm

    def get_execution_log(self) -> List[Dict[str, Any]]:
        """获取执行日志"""
        return self.execution_log

    def get_token_usage(self) -> Dict[str, int]:
        """获取 Token 消耗"""
        return self.token_usage

    def search_knowledge(
        self,
        query: str,
        top_k: int = 5,
        project_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        P2-9: 知识库 RAG 检索。
        所有 Agent 可通过此方法检索项目知识库，获取相关文档片段用于增强生成。

        Args:
            query: 查询文本
            top_k: 返回的相关片段数量
            project_id: 项目ID，默认使用 self.project_id

        Returns:
            相关文档块列表，每项包含 content / metadata / score 等字段；
            检索失败时返回空列表，不影响主流程。
        """
        from app.services.knowledge_base import knowledge_base_service
        pid = project_id or getattr(self, 'project_id', None)
        if not pid:
            logger.warning("search_knowledge: 缺少 project_id，跳过检索")
            return []
        try:
            results = knowledge_base_service.search(db=self.db, project_id=pid, query=query, top_k=top_k)
            self._log_step("knowledge_search", {"query": query[:100], "results": len(results)}, "success")
            return results
        except Exception as e:
            logger.warning(f"知识库检索失败（不影响主流程）: {e}")
            return []

    def build_rag_context(self, query: str, top_k: int = 5) -> str:
        """
        P2-9: 检索知识库并拼接为可直接注入 System Prompt 的上下文文本。
        """
        docs = self.search_knowledge(query, top_k=top_k)
        if not docs:
            return ""
        parts = ["以下是从项目知识库中检索到的相关内容，请参考："]
        for i, doc in enumerate(docs, 1):
            content = doc.get("content", "") if isinstance(doc, dict) else str(doc)
            parts.append(f"[{i}] {content}")
        return "\n".join(parts)

    @abstractmethod
    def run(self, **kwargs) -> Dict[str, Any]:
        """执行 Agent 主逻辑，子类必须实现"""
        pass
