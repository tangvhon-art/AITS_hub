from datetime import datetime
from app.core.timezone import china_now_naive
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean
from app.database import Base, SoftDeleteMixin


class TestCase(SoftDeleteMixin, Base):
    __tablename__ = "test_cases"
    __table_args__ = {"comment": "测试用例表"}

    id = Column(Integer, primary_key=True, index=True, comment="自增主键")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=False, index=True, comment="所属项目ID")
    req_id = Column(Integer, ForeignKey("test_requirements.id"), nullable=True, index=True, comment="关联需求ID")
    title = Column(String(200), nullable=False, comment="用例名称")
    module = Column(String(100), default="", comment="所属模块")
    priority = Column(String(10), default="P1", comment="优先级：P0/P1/P2/P3")
    case_type = Column(String(20), default="functional", comment="用例类型：functional-功能，performance-性能，security-安全")
    preconditions = Column(Text, default="", comment="前置条件")
    steps = Column(Text, default="", comment="测试步骤（JSON数组格式存储）")
    expected_result = Column(Text, default="", comment="预期结果")
    status = Column(String(20), default="draft", comment="状态：draft-草稿，active-生效，archived-归档")
    needs_update = Column(Boolean, default=False, comment="需求变更后标记用例待更新")
    bdd_content = Column(Text, default="", comment="BDD Gherkin格式内容")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建人ID")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")
