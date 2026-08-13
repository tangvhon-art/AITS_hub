from app.core.timezone import china_now_naive
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Float, Boolean, JSON
from app.database import Base, SoftDeleteMixin


class AutomationSuite(SoftDeleteMixin, Base):
    """自动化编排套件表"""
    __tablename__ = "automation_suites"
    __table_args__ = {"comment": "自动化编排套件表"}

    id = Column(Integer, primary_key=True, index=True, comment="自增主键")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=False, index=True, comment="所属项目ID")
    name = Column(String(200), nullable=False, comment="套件名称")
    description = Column(Text, default="", comment="套件描述")
    plan_id = Column(Integer, nullable=True, index=True, comment="关联测试计划ID")
    environment_id = Column(Integer, ForeignKey("test_environments.id"), nullable=True, comment="执行环境ID")
    status = Column(String(20), default="active", comment="状态：draft/active/archived")
    total_steps = Column(Integer, default=0, comment="步骤总数")
    schedule_type = Column(String(20), default="manual", comment="调度类型：manual/once/cron")
    schedule_cron = Column(String(100), default="", comment="Cron表达式")
    next_run_time = Column(DateTime, nullable=True, comment="下次执行时间")
    last_run_status = Column(String(20), nullable=True, comment="最近执行状态")
    last_run_at = Column(DateTime, nullable=True, comment="最近执行时间")
    config = Column(JSON, default=dict, comment="执行配置（JSON）")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建人ID")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")


class AutomationSuiteStep(SoftDeleteMixin, Base):
    """编排步骤表"""
    __tablename__ = "automation_suite_steps"
    __table_args__ = {"comment": "编排步骤表"}

    id = Column(Integer, primary_key=True, index=True, comment="自增主键")
    suite_id = Column(Integer, ForeignKey("automation_suites.id"), nullable=False, index=True, comment="所属套件ID")
    script_id = Column(Integer, ForeignKey("automation_scripts.id"), nullable=True, comment="关联脚本ID")
    case_id = Column(Integer, ForeignKey("test_cases.id"), nullable=True, comment="关联用例ID")
    step_name = Column(String(200), nullable=False, comment="步骤名称")
    sort_order = Column(Integer, default=0, comment="执行顺序")
    step_type = Column(String(20), default="script", comment="类型：script/case/wait")
    params = Column(JSON, default=dict, comment="步骤参数（JSON）")
    continue_on_failure = Column(Boolean, default=False, comment="失败后是否继续")
    max_retries = Column(Integer, default=0, comment="最大重试次数")
    timeout = Column(Integer, default=300, comment="单步超时时间（秒）")
    status = Column(String(20), default="pending", comment="状态：pending/running/passed/failed/skipped")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")


class AutomationSuiteRun(SoftDeleteMixin, Base):
    """编排执行记录表"""
    __tablename__ = "automation_suite_runs"
    __table_args__ = {"comment": "编排执行记录表"}

    id = Column(Integer, primary_key=True, index=True, comment="自增主键")
    suite_id = Column(Integer, ForeignKey("automation_suites.id"), nullable=False, index=True, comment="所属套件ID")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=False, index=True, comment="所属项目ID")
    plan_id = Column(Integer, nullable=True, comment="关联测试计划ID")
    status = Column(String(20), default="pending", comment="状态：pending/running/passed/failed/partial")
    total_steps = Column(Integer, default=0, comment="总步骤数")
    passed_steps = Column(Integer, default=0, comment="通过步骤数")
    failed_steps = Column(Integer, default=0, comment="失败步骤数")
    skipped_steps = Column(Integer, default=0, comment="跳过步骤数")
    pass_rate = Column(Float, default=0.0, comment="通过率")
    total_duration = Column(Float, default=0.0, comment="总耗时（秒）")
    trigger_type = Column(String(20), default="manual", comment="触发方式：manual/schedule/api")
    executed_by = Column(Integer, ForeignKey("users.id"), comment="执行人ID")
    started_at = Column(DateTime, nullable=True, comment="开始时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
    error_message = Column(Text, default="", comment="错误信息")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")


class AutomationSuiteRunResult(SoftDeleteMixin, Base):
    """编排单步执行结果表"""
    __tablename__ = "automation_suite_run_results"
    __table_args__ = {"comment": "编排单步执行结果表"}

    id = Column(Integer, primary_key=True, index=True, comment="自增主键")
    suite_run_id = Column(Integer, ForeignKey("automation_suite_runs.id"), nullable=False, index=True, comment="所属执行记录ID")
    step_id = Column(Integer, ForeignKey("automation_suite_steps.id"), nullable=True, comment="对应步骤ID")
    script_id = Column(Integer, nullable=True, comment="执行的脚本ID")
    case_id = Column(Integer, nullable=True, comment="执行的用例ID")
    run_id = Column(Integer, ForeignKey("test_runs.id"), nullable=True, comment="关联test_runs记录ID")
    step_name = Column(String(200), default="", comment="步骤名称（冗余）")
    sort_order = Column(Integer, default=0, comment="执行顺序（冗余）")
    status = Column(String(20), default="pending", comment="状态：pending/running/passed/failed/skipped")
    duration = Column(Float, default=0.0, comment="耗时（秒）")
    retry_count = Column(Integer, default=0, comment="重试次数")
    error_message = Column(Text, default="", comment="错误信息")
    screenshot_url = Column(String(500), default="", comment="截图路径")
    execution_log = Column(Text, default="", comment="执行日志（JSON）")
    started_at = Column(DateTime, nullable=True, comment="开始时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")
