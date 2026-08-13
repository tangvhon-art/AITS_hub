"""
测试计划数据模型
"""
from datetime import datetime
from app.core.timezone import china_now_naive
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON, Boolean
from app.database import Base, SoftDeleteMixin


class TestPlan(SoftDeleteMixin, Base):
    """测试计划表"""
    __tablename__ = "test_plans"
    __table_args__ = {"comment": "测试计划表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=False, index=True, comment="所属项目ID")
    version_id = Column(Integer, ForeignKey("project_versions.id"), nullable=True, index=True, comment="所属版本ID")
    name = Column(String(200), nullable=False, comment="计划名称")
    description = Column(Text, default="", comment="计划描述")
    status = Column(String(20), default="draft", index=True, comment="状态：draft-草稿，scheduled-已排期，running-执行中，completed-已完成，archived-已归档")
    priority = Column(String(10), default="P2", comment="优先级：P0-P3")
    start_date = Column(DateTime, nullable=True, comment="计划开始时间")
    end_date = Column(DateTime, nullable=True, comment="计划结束时间")
    environment_id = Column(Integer, ForeignKey("test_environments.id"), nullable=True, comment="测试环境ID")
    config = Column(JSON, default=dict, comment="执行配置：headless/timeout/browser等")
    total_cases = Column(Integer, default=0, comment="关联用例总数")
    passed_cases = Column(Integer, default=0, comment="通过用例数")
    failed_cases = Column(Integer, default=0, comment="失败用例数")
    pass_rate = Column(Integer, default=0, comment="通过率（百分比）")
    schedule_type = Column(String(20), default="manual", comment="调度类型：manual-手动，cron-定时，once-一次性")
    schedule_cron = Column(String(100), nullable=True, comment="Cron 表达式")
    next_run_time = Column(DateTime, nullable=True, comment="下次执行时间")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建人ID")
    created_at = Column(DateTime, default=china_now_naive, index=True, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")


class TestPlanCase(SoftDeleteMixin, Base):
    """测试计划-用例关联表"""
    __tablename__ = "test_plan_cases"
    __table_args__ = {"comment": "测试计划-用例关联表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    plan_id = Column(Integer, ForeignKey("test_plans.id"), nullable=False, index=True, comment="计划ID")
    case_id = Column(Integer, ForeignKey("test_cases.id"), nullable=False, index=True, comment="用例ID")
    sort_order = Column(Integer, default=0, comment="执行顺序")
    status = Column(String(20), default="pending", comment="执行状态：pending-待执行，running-执行中，passed-通过，failed-失败，skipped-跳过")
    run_id = Column(Integer, ForeignKey("test_runs.id"), nullable=True, comment="关联的执行记录ID")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")


class TestEnvironment(SoftDeleteMixin, Base):
    """测试环境表"""
    __tablename__ = "test_environments"
    __table_args__ = {"comment": "测试环境表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=False, index=True, comment="所属项目ID")
    name = Column(String(100), nullable=False, comment="环境名称")
    base_url = Column(String(500), nullable=False, comment="环境基础URL")
    description = Column(Text, default="", comment="环境描述")
    config = Column(JSON, default=dict, comment="环境配置：账号/参数/变量等")
    is_default = Column(Boolean, default=False, comment="是否默认环境")
    status = Column(String(20), default="active", comment="状态：active-活跃，inactive-停用")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建人ID")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")
