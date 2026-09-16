"""
测试计划数据模型
"""
from datetime import datetime
from app.core.timezone import china_now_naive
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON, Boolean, Float
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
    execution_config = Column(JSON, default=dict, comment="执行配置（超时、重试、并发）")
    last_execution_id = Column(Integer, nullable=True, comment="最近一次执行ID")
    last_pass_rate = Column(Float, default=0, comment="最近一次通过率")
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
    """[已废弃] 测试计划-用例关联表（旧版，仅保留向后兼容）

    .. deprecated::
        请使用 :class:`TestPlanItem`，支持 case/scenario/script/suite 混合编排。
        新代码不应再写入此表，报告统计统一基于 TestPlanItem / TestPlanExecution。
    """
    __tablename__ = "test_plan_cases"
    __table_args__ = {"comment": "[已废弃] 测试计划-用例关联表（旧版）"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    plan_id = Column(Integer, ForeignKey("test_plans.id"), nullable=False, index=True, comment="计划ID")
    case_id = Column(Integer, ForeignKey("test_cases.id"), nullable=False, index=True, comment="用例ID")
    sort_order = Column(Integer, default=0, comment="执行顺序")
    status = Column(String(20), default="pending", comment="执行状态：pending-待执行，running-执行中，passed-通过，failed-失败，skipped-跳过")
    run_id = Column(Integer, ForeignKey("test_runs.id"), nullable=True, comment="关联的执行记录ID")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")


class TestPlanItem(SoftDeleteMixin, Base):
    """测试计划内容节点表（用例+场景混合编排）"""
    __tablename__ = "test_plan_items"
    __table_args__ = {"comment": "测试计划内容节点表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    plan_id = Column(Integer, ForeignKey("test_plans.id"), nullable=False, index=True, comment="关联测试计划ID")
    item_type = Column(String(20), nullable=False, index=True, comment="节点类型：case-接口用例，scenario-场景编排")
    ref_id = Column(Integer, nullable=False, index=True, comment="关联的用例ID或场景ID")
    item_name = Column(String(200), default="", comment="节点名称（冗余，便于展示）")
    sort_order = Column(Integer, default=0, comment="执行顺序")
    enabled = Column(Boolean, default=True, comment="是否启用")
    fail_strategy = Column(String(20), default="stop", comment="失败策略：stop-失败停止，continue-失败继续")
    timeout = Column(Integer, default=0, comment="超时时间（秒），0表示不限制")
    max_retries = Column(Integer, default=0, comment="最大重试次数")
    config = Column(JSON, default=dict, comment="节点级配置")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")


class TestPlanExecution(SoftDeleteMixin, Base):
    """测试计划执行记录表"""
    __tablename__ = "test_plan_executions"
    __table_args__ = {"comment": "测试计划执行记录表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    plan_id = Column(Integer, ForeignKey("test_plans.id"), nullable=False, index=True, comment="关联测试计划ID")
    plan_name = Column(String(200), default="", comment="计划名称（快照）")
    environment_id = Column(Integer, nullable=True, comment="执行环境ID")
    environment_name = Column(String(100), default="", comment="环境名称（快照）")
    status = Column(String(20), default="pending", index=True, comment="状态：pending-待执行，running-执行中，completed-已完成，failed-失败，cancelled-已取消")
    triggered_by = Column(Integer, ForeignKey("users.id"), comment="触发人ID")
    started_at = Column(DateTime, nullable=True, comment="开始时间")
    finished_at = Column(DateTime, nullable=True, comment="结束时间")
    total_items = Column(Integer, default=0, comment="总节点数")
    passed_count = Column(Integer, default=0, comment="通过数")
    failed_count = Column(Integer, default=0, comment="失败数")
    skipped_count = Column(Integer, default=0, comment="跳过数")
    pass_rate = Column(Float, default=0, comment="通过率")
    error_message = Column(Text, default="", comment="错误信息（整体失败时）")
    report_data = Column(JSON, default=dict, comment="报告数据（冗余存储）")
    created_at = Column(DateTime, default=china_now_naive, index=True, comment="创建时间")


class TestPlanExecutionResult(SoftDeleteMixin, Base):
    """测试计划执行结果明细表"""
    __tablename__ = "test_plan_execution_results"
    __table_args__ = {"comment": "测试计划执行结果明细表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    execution_id = Column(Integer, ForeignKey("test_plan_executions.id"), nullable=False, index=True, comment="关联执行记录ID")
    item_id = Column(Integer, nullable=True, index=True, comment="关联计划节点ID")
    item_type = Column(String(20), default="", comment="节点类型：case/scenario")
    ref_id = Column(Integer, nullable=True, comment="关联用例/场景ID")
    item_name = Column(String(200), default="", comment="节点名称（快照）")
    sort_order = Column(Integer, default=0, comment="执行顺序")
    status = Column(String(20), default="pending", comment="状态：passed-通过，failed-失败，skipped-跳过，error-错误")
    started_at = Column(DateTime, nullable=True, comment="开始时间")
    finished_at = Column(DateTime, nullable=True, comment="结束时间")
    duration_ms = Column(Integer, default=0, comment="耗时（毫秒）")
    request_data = Column(JSON, default=dict, comment="请求数据（method, url, headers, body）")
    response_data = Column(JSON, default=dict, comment="响应数据（status_code, body, headers, duration）")
    assertions = Column(JSON, default=list, comment="断言结果列表")
    extracted_vars = Column(JSON, default=dict, comment="提取的变量（场景节点）")
    error_message = Column(Text, default="", comment="错误信息")
    retry_count = Column(Integer, default=0, comment="实际重试次数")
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
