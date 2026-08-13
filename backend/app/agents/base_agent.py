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

from app.agents.llm_factory import llm_factory

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Agent 基类"""

    agent_type: str = "base"

    def __init__(
        self,
        db_session: Session,
        llm_config_id: Optional[int] = None,
        task_id: Optional[int] = None,
    ):
        self.db = db_session
        self.llm_config_id = llm_config_id
        self.task_id = task_id
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
        """调用 LLM，带降级和 Token 统计"""
        llm, config_id = llm_factory.get_llm_with_fallback(
            self.db, preferred_config_id=self.llm_config_id
        )
        response = llm.invoke(messages, **kwargs)

        # 统计 Token
        usage = getattr(response, "usage_metadata", None)
        if usage:
            self.token_usage["prompt_tokens"] += usage.get("input_tokens", 0)
            self.token_usage["completion_tokens"] += usage.get("output_tokens", 0)
            self.token_usage["total_tokens"] += (
                usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
            )

        self.llm_config_id = config_id
        return response

    def get_execution_log(self) -> List[Dict[str, Any]]:
        """获取执行日志"""
        return self.execution_log

    def get_token_usage(self) -> Dict[str, int]:
        """获取 Token 消耗"""
        return self.token_usage

    @abstractmethod
    def run(self, **kwargs) -> Dict[str, Any]:
        """执行 Agent 主逻辑，子类必须实现"""
        pass
