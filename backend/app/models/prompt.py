"""
Prompt 管理数据模型（全局公用）
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, JSON
from app.database import Base, SoftDeleteMixin
from app.core.timezone import china_now_naive


class Prompt(SoftDeleteMixin, Base):
    """Prompt 模板表（全局公用，不绑定项目）"""
    __tablename__ = "prompts"
    __table_args__ = {"comment": "Prompt 模板表（全局公用）"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    name = Column(String(200), nullable=False, comment="Prompt 名称")
    description = Column(Text, default="", comment="描述说明")
    category = Column(String(50), default="case_generation", comment="分类：case_generation-用例生成, case_review-用例评审, api_test-api测试, requirement_generation-需求生成, report_generation-报告生成, script_generation-脚本生成, other-其他")
    system_prompt = Column(Text, nullable=False, comment="System 提示词")
    user_prompt_template = Column(Text, default="", comment="User 提示词模板，支持变量占位符")
    variables = Column(JSON, default=list, comment="模板变量列表")
    is_default = Column(Boolean, default=False, comment="是否默认 Prompt")
    status = Column(String(20), default="active", comment="状态：active-启用，inactive-停用")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建人ID")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")
