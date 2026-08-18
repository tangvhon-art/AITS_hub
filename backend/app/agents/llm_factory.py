"""
统一大模型抽象层 LLMFactory

支持四种接入模式：
1. openai_compatible - OpenAI 兼容协议（DeepSeek、自部署 vLLM/TGI 等）
2. anthropic - Claude（Anthropic 官方 API）
3. ollama - 本地 Ollama 模型

特性：
- 统一 LangChain BaseChatModel 接口
- 从数据库 llm_configs 表加载配置，支持热更新
- 调用失败自动按优先级降级到备用模型
- Token 消耗统计
- API Key 加密存储
"""
import base64
import json
import logging
from typing import Optional, List, Dict, Any
from cryptography.fernet import Fernet
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from app.config import settings

logger = logging.getLogger(__name__)

# 加密密钥（生产环境应从环境变量读取）
_fernet = Fernet(base64.urlsafe_b64encode(settings.SECRET_KEY[:32].encode().ljust(32, b'0')))


def encrypt_api_key(api_key: str) -> str:
    """加密 API Key"""
    if not api_key:
        return ""
    return _fernet.encrypt(api_key.encode()).decode()


def decrypt_api_key(encrypted_key: str) -> str:
    """解密 API Key"""
    if not encrypted_key:
        return ""
    try:
        return _fernet.decrypt(encrypted_key.encode()).decode()
    except Exception:
        return encrypted_key


class LLMFactory:
    """大模型工厂类，统一创建和管理 LLM 实例"""

    _instance = None
    _configs_cache: Dict[int, Dict[str, Any]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def create_llm(
        self,
        provider: str,
        model_name: str,
        base_url: str = "",
        api_key: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        streaming: bool = False,
        **kwargs
    ) -> BaseChatModel:
        """
        根据 provider 类型创建对应的 LangChain ChatModel 实例
        """
        provider = provider.lower().strip()

        if provider in ("openai_compatible", "openai", "deepseek", "vllm", "tgi"):
            return self._create_openai_compatible(
                model_name=model_name,
                base_url=base_url,
                api_key=api_key,
                max_tokens=max_tokens,
                temperature=temperature,
                streaming=streaming,
                **kwargs
            )
        elif provider in ("anthropic", "claude"):
            return self._create_anthropic(
                model_name=model_name,
                api_key=api_key,
                max_tokens=max_tokens,
                temperature=temperature,
                streaming=streaming,
                **kwargs
            )
        elif provider == "ollama":
            return self._create_ollama(
                model_name=model_name,
                base_url=base_url or "http://localhost:11434",
                temperature=temperature,
                **kwargs
            )
        else:
            raise ValueError(f"不支持的模型提供商: {provider}")

    def _create_openai_compatible(
        self, model_name, base_url, api_key, max_tokens, temperature, streaming=False, **kwargs
    ) -> BaseChatModel:
        """创建 OpenAI 兼容协议的 LLM（DeepSeek / vLLM / TGI / SiliconFlow 等）

        支持两种 API 格式：
        - chat_completions: /v1/chat/completions（LangChain ChatOpenAI，默认）
        - responses: /v1/responses（自定义 ResponsesChat）
        """
        api_format = kwargs.get("api_format", "chat_completions")

        # 规范化 base_url：确保以 /v1 结尾（OpenAI 兼容接口标准路径）
        if base_url:
            base_url = base_url.rstrip("/")
            if not base_url.endswith("/v1") and not base_url.endswith("/v1/"):
                # 检查是否已经包含版本路径
                if "/v" not in base_url.split("/")[-1]:
                    base_url = base_url + "/v1"

        if api_format == "responses":
            from app.agents.responses_chat import ResponsesChat
            return ResponsesChat(
                model=model_name,
                api_key=api_key or "not-needed",
                base_url=base_url or "https://api.openai.com/v1",
                max_tokens=max_tokens,
                temperature=temperature,
            )

        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            model=model_name,
            api_key=api_key or "not-needed",
            base_url=base_url or None,
            max_tokens=max_tokens,
            temperature=temperature,
            streaming=streaming,
        )
        return llm

    def _create_anthropic(
        self, model_name, api_key, max_tokens, temperature, streaming=False, **kwargs
    ) -> BaseChatModel:
        """创建 Anthropic Claude LLM"""
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model_name,
            api_key=api_key,
            max_tokens=max_tokens,
            temperature=temperature,
            streaming=streaming,
        )

    def _create_ollama(
        self, model_name, base_url, temperature, **kwargs
    ) -> BaseChatModel:
        """创建本地 Ollama LLM"""
        from langchain_community.chat_models import ChatOllama

        return ChatOllama(
            model=model_name,
            base_url=base_url,
            temperature=temperature,
        )

    def get_llm_from_config(self, config: Dict[str, Any]) -> BaseChatModel:
        """从配置字典创建 LLM 实例"""
        return self.create_llm(
            provider=config.get("provider", "openai_compatible"),
            model_name=config.get("model_name", ""),
            base_url=config.get("base_url", ""),
            api_key=decrypt_api_key(config.get("api_key", "")),
            max_tokens=config.get("max_tokens", 4096),
            temperature=config.get("temperature", 0.7),
            streaming=config.get("streaming", False),
            api_format=config.get("api_format", "chat_completions"),
        )

    def get_default_llm(self, db_session=None) -> BaseChatModel:
        """
        获取默认 LLM。
        优先从数据库读取 is_default 的配置，否则使用环境变量默认配置。
        """
        if db_session:
            from app.models.llm_config import LLMConfig
            default_config = db_session.query(LLMConfig).filter(
                LLMConfig.is_default == True,
                LLMConfig.status == "active"
            ).first()
            if default_config:
                return self.get_llm_from_config({
                    "provider": default_config.provider,
                    "model_name": default_config.model_name,
                    "base_url": default_config.base_url,
                    "api_key": default_config.api_key,
                    "max_tokens": default_config.max_tokens,
                    "temperature": default_config.temperature,
                    "streaming": default_config.streaming,
                    "api_format": default_config.api_format,
                })

        # 回退到环境变量默认配置
        return self.create_llm(
            provider=settings.DEFAULT_LLM_PROVIDER,
            model_name=settings.DEFAULT_LLM_MODEL,
            base_url=settings.DEFAULT_LLM_BASE_URL,
            api_key=settings.DEFAULT_LLM_API_KEY,
        )

    def get_llm_with_fallback(
        self,
        db_session,
        preferred_config_id: Optional[int] = None,
    ) -> tuple[BaseChatModel, Optional[int]]:
        """
        获取 LLM 实例，支持失败降级。
        返回 (llm_instance, config_id)
        """
        from app.models.llm_config import LLMConfig

        configs = db_session.query(LLMConfig).filter(
            LLMConfig.status == "active"
        ).order_by(LLMConfig.priority.asc()).all()

        if not configs:
            # 没有数据库配置，使用默认环境变量
            return self.get_default_llm(), None

        # 如果指定了优先配置，把它放到最前面
        if preferred_config_id:
            preferred = next((c for c in configs if c.id == preferred_config_id), None)
            if preferred:
                configs.remove(preferred)
                configs.insert(0, preferred)

        # 返回第一个可用的配置（调用时再做降级处理）
        first = configs[0]
        return self.get_llm_from_config({
            "provider": first.provider,
            "model_name": first.model_name,
            "base_url": first.base_url,
            "api_key": first.api_key,
            "max_tokens": first.max_tokens,
            "temperature": first.temperature,
            "streaming": first.streaming,
            "api_format": first.api_format,
        }), first.id

    def call_with_fallback(
        self,
        db_session,
        messages: List[BaseMessage],
        preferred_config_id: Optional[int] = None,
        max_retries: int = 2,
    ) -> tuple[Any, Dict[str, int], Optional[int]]:
        """
        带降级和重试的 LLM 调用。
        返回 (response, token_usage, used_config_id)
        """
        from app.models.llm_config import LLMConfig

        configs = db_session.query(LLMConfig).filter(
            LLMConfig.status == "active"
        ).order_by(LLMConfig.priority.asc()).all()

        if preferred_config_id:
            preferred = next((c for c in configs if c.id == preferred_config_id), None)
            if preferred:
                configs.remove(preferred)
                configs.insert(0, preferred)

        if not configs:
            # 使用默认配置
            llm = self.get_default_llm()
            response = llm.invoke(messages)
            usage = self._extract_token_usage(response)
            return response, usage, None

        last_error = None
        for config in configs:
            for attempt in range(max_retries):
                try:
                    llm = self.get_llm_from_config({
                        "provider": config.provider,
                        "model_name": config.model_name,
                        "base_url": config.base_url,
                        "api_key": config.api_key,
                        "max_tokens": config.max_tokens,
                        "temperature": config.temperature,
                        "streaming": config.streaming,
                    })
                    response = llm.invoke(messages)
                    usage = self._extract_token_usage(response)
                    logger.info(f"LLM 调用成功: config={config.name}, model={config.model_name}")
                    return response, usage, config.id
                except Exception as e:
                    last_error = e
                    logger.warning(
                        f"LLM 调用失败 (config={config.name}, attempt={attempt+1}): {e}"
                    )
                    continue

        raise RuntimeError(f"所有 LLM 配置均调用失败: {last_error}")

    async def acall_with_fallback(
        self,
        db_session,
        messages: List[BaseMessage],
        preferred_config_id: Optional[int] = None,
        max_retries: int = 2,
    ) -> tuple[Any, Dict[str, int], Optional[int]]:
        """
        带降级和重试的 LLM 异步调用（不阻塞事件循环）。
        返回 (response, token_usage, used_config_id)
        """
        import asyncio
        from app.models.llm_config import LLMConfig

        configs = db_session.query(LLMConfig).filter(
            LLMConfig.status == "active"
        ).order_by(LLMConfig.priority.asc()).all()

        if preferred_config_id:
            preferred = next((c for c in configs if c.id == preferred_config_id), None)
            if preferred:
                configs.remove(preferred)
                configs.insert(0, preferred)

        if not configs:
            # 使用默认配置
            llm = self.get_default_llm()
            response = await llm.ainvoke(messages)
            usage = self._extract_token_usage(response)
            return response, usage, None

        last_error = None
        for config in configs:
            for attempt in range(max_retries):
                try:
                    llm = self.get_llm_from_config({
                        "provider": config.provider,
                        "model_name": config.model_name,
                        "base_url": config.base_url,
                        "api_key": config.api_key,
                        "max_tokens": config.max_tokens,
                        "temperature": config.temperature,
                        "streaming": config.streaming,
                    })
                    response = await llm.ainvoke(messages)
                    usage = self._extract_token_usage(response)
                    logger.info(f"LLM 异步调用成功: config={config.name}, model={config.model_name}")
                    return response, usage, config.id
                except Exception as e:
                    last_error = e
                    logger.warning(
                        f"LLM 异步调用失败 (config={config.name}, attempt={attempt+1}): {e}"
                    )
                    await asyncio.sleep(1)  # 异步等待，不阻塞事件循环
                    continue

        raise RuntimeError(f"所有 LLM 配置均调用失败: {last_error}")

    @staticmethod
    def _extract_token_usage(response) -> Dict[str, int]:
        """从 LLM 响应中提取 Token 使用量"""
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        try:
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                usage["prompt_tokens"] = response.usage_metadata.get("input_tokens", 0)
                usage["completion_tokens"] = response.usage_metadata.get("output_tokens", 0)
                usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
        except Exception:
            pass
        return usage


# 全局单例
llm_factory = LLMFactory()
