from datetime import datetime
from app.core.timezone import china_now_naive
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean
from app.database import Base, SoftDeleteMixin


class TestRequirement(SoftDeleteMixin, Base):
    __tablename__ = "test_requirements"
    __table_args__ = {"comment": "测试需求表"}

    id = Column(Integer, primary_key=True, index=True, comment="自增主键")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=False, index=True, comment="所属项目ID")
    version_id = Column(Integer, ForeignKey("project_versions.id"), nullable=True, index=True, comment="所属版本ID")
    title = Column(String(200), nullable=False, comment="需求标题")
    content = Column(Text, default="", comment="需求内容")
    source = Column(String(50), default="manual", comment="需求来源：manual-手动输入，upload-文档上传，feishu-飞书")
    source_url = Column(String(500), default="", comment="来源链接")
    status = Column(String(20), default="pending", comment="状态：pending-待生成，generated-已生成，reviewed-已评审")
    feature_split_status = Column(String(20), default="pending", comment="功能点拆分状态：pending-待拆分，splitting-拆分中，split-已拆分，failed-拆分失败")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建人ID")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")


class RequirementFeature(SoftDeleteMixin, Base):
    """需求功能点表"""
    __tablename__ = "requirement_features"
    __table_args__ = {"comment": "需求功能点表"}

    id = Column(Integer, primary_key=True, index=True, comment="自增主键")
    requirement_id = Column(Integer, ForeignKey("test_requirements.id"), nullable=False, index=True, comment="所属需求ID")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=False, index=True, comment="所属项目ID")
    module_name = Column(String(200), nullable=False, comment="模块名称")
    module_desc = Column(String(500), default="", comment="模块描述")
    name = Column(String(200), nullable=False, comment="功能点名称")
    description = Column(Text, default="", comment="功能点描述（含业务规则、约束）")
    priority = Column(String(10), default="P1", comment="建议优先级：P0/P1/P2/P3")
    design_methods = Column(Text, default="[]", comment="建议用例设计方法列表JSON")
    preconditions = Column(Text, default="", comment="前置条件")
    sort_order = Column(Integer, default=0, comment="排序序号")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")
