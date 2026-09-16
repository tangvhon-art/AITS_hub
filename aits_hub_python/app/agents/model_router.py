"""
模型路由策略

支持按项目/Agent类型/数据敏感度配置默认模型，失败自动降级。
"""
import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.models.llm_config import LLMConfig
from app.agents.llm_factory import llm_factory

logger = logging.getLogger(__name__)


class ModelRouter:
    """模型路由器"""

    # Agent 类型到推荐模型的映射（可配置）
    AGENT_MODEL_PREFERENCE = {
        "case_generator": {"priority": "high", "sensitivity": "low"},
        "case_reviewer": {"priority": "high", "sensitivity": "low"},
        "ui_execution": {"priority": "medium", "sensitivity": "low"},
        "defect_analyzer": {"priority": "high", "sensitivity": "medium"},
        "report_generator": {"priority": "medium", "sensitivity": "low"},
        "notification": {"priority": "low", "sensitivity": "low"},
        "bdd_generator": {"priority": "medium", "sensitivity": "low"},
        "supervisor": {"priority": "high", "sensitivity": "medium"},
    }

    def __init__(self, db_session: Session):
        self.db = db_session

    def get_model_for_agent(
        self,
        agent_type: str,
        project_id: Optional[int] = None,
        data_sensitivity: str = "low",
        preferred_config_id: Optional[int] = None,
    ):
        """
        根据 Agent 类型和数据敏感度获取合适的模型

        Args:
            agent_type: Agent 类型
            project_id: 项目ID（预留项目级配置）
            data_sensitivity: 数据敏感度 low/medium/high
            preferred_config_id: 用户指定的模型配置ID

        Returns:
            (llm, config_id) 元组
        """
        # 如果用户指定了模型配置，优先使用
        if preferred_config_id:
            return llm_factory.get_llm_with_fallback(
                self.db, preferred_config_id=preferred_config_id
            )

        # 高敏感度数据强制使用自部署/本地模型
        if data_sensitivity == "high":
            local_configs = self.db.query(LLMConfig).filter(
                LLMConfig.status == "active",
                LLMConfig.provider.in_(["ollama", "openai_compatible"]),
            ).order_by(LLMConfig.priority.asc()).all()

            for config in local_configs:
                # 排除纯云端 API（如 DeepSeek、Claude）
                if "deepseek" in config.base_url.lower() or "anthropic" in config.base_url.lower():
                    continue
                try:
                    llm = llm_factory.create_llm(
                        provider=config.provider,
                        base_url=config.base_url,
                        api_key=llm_factory.decrypt_api_key(config.api_key) if config.api_key else "",
                        model_name=config.model_name,
                        max_tokens=config.max_tokens,
                        temperature=config.temperature,
                        streaming=config.streaming,
                    )
                    return llm, config.id
                except Exception as e:
                    logger.warning(f"高敏感度模型 {config.name} 不可用: {e}")
                    continue

        # 默认按优先级降级
        return llm_factory.get_llm_with_fallback(self.db)

    def get_agent_preference(self, agent_type: str) -> Dict[str, str]:
        """获取 Agent 类型的模型偏好"""
        return self.AGENT_MODEL_PREFERENCE.get(agent_type, {"priority": "medium", "sensitivity": "low"})


# 全局单例
model_router = None


def get_model_router(db_session: Session) -> ModelRouter:
    """获取模型路由器实例"""
    return ModelRouter(db_session)
