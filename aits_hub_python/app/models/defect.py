from datetime import datetime
from app.core.timezone import china_now_naive
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON
from app.database import Base, SoftDeleteMixin


class Defect(SoftDeleteMixin, Base):
    __tablename__ = "defects"
    __table_args__ = {"comment": "缺陷表"}

    id = Column(Integer, primary_key=True, index=True, comment="自增主键")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=False, index=True, comment="所属项目ID")
    version_id = Column(Integer, ForeignKey("project_versions.id"), nullable=True, index=True, comment="所属版本ID")
    run_id = Column(Integer, ForeignKey("test_runs.id"), nullable=True, index=True, comment="关联执行记录ID")
    case_id = Column(Integer, ForeignKey("test_cases.id"), nullable=True, index=True, comment="关联用例ID")
    title = Column(String(200), nullable=False, comment="缺陷标题")
    description = Column(Text, default="", comment="缺陷描述")
    severity = Column(String(20), default="medium", comment="严重程度：blocker-致命，critical-严重，major-主要，minor-次要，trivial-轻微")
    priority = Column(String(10), default="P2", comment="优先级：P0/P1/P2/P3")
    status = Column(String(20), default="open", comment="状态：open-新建，confirmed-已确认，resolved-已解决，closed-已关闭，reopened-重新打开")
    root_cause = Column(Text, default="", comment="根因分析")
    root_cause_category = Column(String(50), default="", comment="根因分类：frontend-前端，backend-后端，data-数据，environment-环境，requirement-需求，other-其他")
    reproduce_steps = Column(Text, default="", comment="复现步骤")
    expected_result = Column(Text, default="", comment="预期结果")
    actual_result = Column(Text, default="", comment="实际结果")
    screenshot_url = Column(String(500), default="", comment="截图路径")
    error_log = Column(Text, default="", comment="错误日志")
    assignee_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="指派给")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建人ID")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")
