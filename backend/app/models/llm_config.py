from datetime import datetime
from app.core.timezone import china_now_naive
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Float
from app.database import Base, SoftDeleteMixin


class LLMConfig(SoftDeleteMixin, Base):
    __tablename__ = "llm_configs"
    __table_args__ = {"comment": "大模型配置表"}

    id = Column(Integer, primary_key=True, index=True, comment="自增主键")
    name = Column(String(100), nullable=False, unique=True, comment="配置名称")
    provider = Column(String(50), nullable=False, comment="提供商：openai_compatible-OpenAI兼容，anthropic-Anthropic Claude，ollama-本地Ollama")
    base_url = Column(String(500), default="", comment="API基础地址")
    api_key = Column(String(500), default="", comment="API密钥（加密存储）")
    model_name = Column(String(100), nullable=False, comment="模型名称")
    max_tokens = Column(Integer, default=4096, comment="最大生成Token数")
    temperature = Column(Float, default=0.7, comment="温度参数（0-1）")
    streaming = Column(Boolean, default=False, comment="是否启用流式输出：0-否，1-是")
    is_default = Column(Boolean, default=False, comment="是否默认模型：0-否，1-是")
    status = Column(String(20), default="active", comment="状态：active-启用，inactive-停用")
    priority = Column(Integer, default=0, comment="降级优先级，数字越小优先级越高")
    description = Column(Text, default="", comment="配置描述")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")
