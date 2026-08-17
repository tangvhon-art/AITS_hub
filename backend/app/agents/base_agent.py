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
        """调用 LLM，通过 ModelRouter 路由模型，带降级和 Token 统计"""
        if not hasattr(self, '_llm_initialized'):
            self._init_routed_llm(
                agent_type=self.agent_name,
                preferred_config_id=self.llm_config_id,
            )
            self._llm_initialized = True

        response = self.llm.invoke(messages, **kwargs)

        # 统计 Token
        usage = getattr(response, "usage_metadata", None)
        if usage:
            self.token_usage["prompt_tokens"] += usage.get("input_tokens", 0)
            self.token_usage["completion_tokens"] += usage.get("output_tokens", 0)
            self.token_usage["total_tokens"] += (
                usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
            )

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
            results = knowledge_base_service.search(pid, query, top_k=top_k)
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
