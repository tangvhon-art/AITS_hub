from app.core.timezone import china_now_naive
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Float, Boolean
from app.database import Base, SoftDeleteMixin


class AutomationScript(SoftDeleteMixin, Base):
    __tablename__ = "automation_scripts"
    __table_args__ = {"comment": "UI自动化脚本表"}

    id = Column(Integer, primary_key=True, index=True, comment="自增主键")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=False, index=True, comment="所属项目ID")
    name = Column(String(200), nullable=False, comment="脚本名称")
    description = Column(Text, default="", comment="脚本描述")
    case_id = Column(Integer, ForeignKey("test_cases.id"), nullable=True, index=True, comment="关联测试用例ID")
    source_run_id = Column(Integer, ForeignKey("test_runs.id"), nullable=True, comment="来源执行记录ID")
    script_content = Column(Text, default="", comment="Playwright脚本内容")
    script_type = Column(String(20), default="ai_generated", comment="类型：ai_generated/manual")
    target_url = Column(String(500), default="", comment="目标URL")
    language = Column(String(20), default="python", comment="脚本语言")
    status = Column(String(20), default="active", comment="状态：draft/active/deprecated")
    version = Column(Integer, default=1, comment="版本号")
    tags = Column(String(500), default="", comment="标签（逗号分隔）")
    last_run_status = Column(String(20), nullable=True, comment="最近执行状态")
    last_run_at = Column(DateTime, nullable=True, comment="最近执行时间")
    total_runs = Column(Integer, default=0, comment="累计执行次数")
    pass_count = Column(Integer, default=0, comment="通过次数")
    fail_count = Column(Integer, default=0, comment="失败次数")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建人ID")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")
