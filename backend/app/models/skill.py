"""Skill 模型"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON
from app.database import Base
from app.core.timezone import china_now_naive


class Skill(Base):
    """Skill 编排配置"""
    __tablename__ = "skills"
    __table_args__ = {"comment": "Skill编排配置表（触发条件+SystemPrompt+工具白名单，全局公共）"}

    id = Column(Integer, primary_key=True, comment="主键ID")
    name = Column(String(100), unique=True, nullable=False, comment="Skill 标识名")
    title = Column(String(200), nullable=False, comment="显示名称")
    description = Column(Text, comment="描述")
    category = Column(String(50), comment="分类: testing/analysis/automation/other")
    version = Column(String(20), default="1.0.0", comment="版本号")
    author = Column(String(100), comment="作者/来源")
    source = Column(String(20), default="manual", comment="来源: builtin/manual/imported")
    trigger_config = Column(JSON, comment="触发配置 {type, keywords, intent, pattern}")
    skill_config = Column(JSON, comment="执行配置 {system_prompt, allowed_tools, max_tool_calls, ...}")
    prompts = Column(JSON, comment="附加提示词文件 {filename: content}")
    scripts = Column(JSON, comment="附加脚本 {filename: content}")
    icon_path = Column(String(500), comment="图标存储路径")
    raw_yaml = Column(Text, comment="原始 skill.yaml 内容")
    package_hash = Column(String(64), comment="zip 包 SHA256 哈希")
    is_active = Column(Boolean, default=True, comment="是否启用")
    is_builtin = Column(Boolean, default=False, comment="是否内置")
    sort_order = Column(Integer, default=0, comment="排序")
    created_by = Column(Integer, comment="创建人ID")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")
    is_deleted = Column(Boolean, default=False, comment="软删除标记")
    deleted_at = Column(DateTime, comment="删除时间")
