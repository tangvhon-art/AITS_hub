"""
测试用例集（Test Case Suite）模型

用例集是项目内测试用例的集合化组织容器：
- 一个用例集可包含多个模块、多条用例（多对多）；
- 一条用例可同时属于多个用例集；
- 用例集本身不含用例内容，删除用例集仅移除关联关系，不影响用例。
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint, Index

from app.database import Base, SoftDeleteMixin, TimestampMixin
from app.core.timezone import china_now_naive


class TestCaseSuite(SoftDeleteMixin, TimestampMixin, Base):
    """测试用例集表"""
    __tablename__ = "test_case_suites"
    __table_args__ = {"comment": "测试用例集表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=False, index=True, comment="所属项目ID")
    name = Column(String(200), nullable=False, comment="用例集名称")
    description = Column(Text, default="", comment="用例集描述")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建人ID")


class TestCaseSuiteCase(Base):
    """用例集-用例关联表（多对多）"""
    __tablename__ = "test_case_suite_cases"
    __table_args__ = (
        UniqueConstraint("suite_id", "case_id", name="uk_suite_case"),
        {"comment": "用例集-用例关联表"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    suite_id = Column(Integer, ForeignKey("test_case_suites.id"), nullable=False, index=True, comment="用例集ID")
    case_id = Column(Integer, ForeignKey("test_cases.id"), nullable=False, index=True, comment="用例ID")
    created_at = Column(DateTime, default=china_now_naive, comment="加入时间")


class CaseSuiteCaseExecStatus(SoftDeleteMixin, TimestampMixin, Base):
    """用例集内用例的执行状态表

    执行状态是「用例集 + 用例」维度的独立状态，与用例管理状态（draft/active/archived）区分：
    - 表中无记录 = 默认待执行（pending）；
    - 执行后写入本表（upsert），记录执行状态、执行时间与执行人。
    """
    __tablename__ = "case_suite_case_exec_status"
    __table_args__ = (
        UniqueConstraint("suite_id", "case_id", name="uk_suite_case_exec"),
        {"comment": "用例集内用例执行状态表"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=False, index=True, comment="所属项目ID")
    suite_id = Column(Integer, ForeignKey("test_case_suites.id"), nullable=False, index=True, comment="用例集ID")
    case_id = Column(Integer, ForeignKey("test_cases.id"), nullable=False, index=True, comment="用例ID")
    exec_status = Column(String(20), default="pending", comment="执行状态：pending-待执行，passed-通过，failed-失败，blocked-阻塞，skipped-跳过")
    executed_at = Column(DateTime, nullable=True, comment="执行时间")
    executed_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment="执行人ID")
