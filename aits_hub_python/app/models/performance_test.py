from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Float, Boolean, JSON
from app.database import Base, SoftDeleteMixin
from app.core.timezone import china_now_naive


class PerformanceTest(SoftDeleteMixin, Base):
    """性能测试配置表"""
    __tablename__ = "performance_tests"
    __table_args__ = {"comment": "性能测试配置表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=False, index=True, comment="所属项目ID")
    name = Column(String(200), nullable=False, comment="测试名称")
    description = Column(Text, comment="测试描述")

    target_type = Column(String(20), default="api_case", comment="目标类型: api_definition/api_case/api_scenario")
    target_id = Column(Integer, comment="关联目标ID（单接口模式）")
    target_url = Column(String(500), comment="可覆盖目标URL")
    targets = Column(JSON, default=list, comment="多接口目标列表: [{target_type,target_id,method,path,name,weight}]")

    users = Column(Integer, default=10, comment="并发用户数")
    spawn_rate = Column(Integer, default=1, comment="每秒启动用户数")
    duration = Column(Integer, default=60, comment="持续时间（秒）")

    headers = Column(JSON, default=dict, comment="自定义请求头")
    body_template = Column(Text, comment="请求体模板")
    variable_config = Column(JSON, default=dict, comment="参数化变量配置")
    data_pool_id = Column(Integer, ForeignKey("test_data_pools.id"), comment="关联测试数据池ID")

    status = Column(String(20), default="draft", comment="状态: draft/running/completed/failed/stopped")
    environment_id = Column(Integer, ForeignKey("test_environments.id"), comment="测试环境ID")

    created_by = Column(Integer, ForeignKey("users.id"), comment="创建人ID")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")


class PerformanceTestRun(SoftDeleteMixin, Base):
    """性能测试执行记录表"""
    __tablename__ = "performance_test_runs"
    __table_args__ = {"comment": "性能测试执行记录表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    test_id = Column(Integer, ForeignKey("performance_tests.id"), nullable=False, index=True, comment="性能测试ID")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=False, index=True, comment="所属项目ID")

    config_snapshot = Column(JSON, default=dict, comment="执行时负载配置快照")

    status = Column(String(20), default="pending", comment="状态: pending/running/completed/failed/stopped")
    started_at = Column(DateTime, comment="开始时间")
    finished_at = Column(DateTime, comment="结束时间")

    total_requests = Column(Integer, default=0, comment="总请求数")
    total_failures = Column(Integer, default=0, comment="总失败数")
    avg_response_time = Column(Float, default=0.0, comment="平均响应时间(ms)")
    min_response_time = Column(Float, default=0.0, comment="最小响应时间(ms)")
    max_response_time = Column(Float, default=0.0, comment="最大响应时间(ms)")
    p50_response_time = Column(Float, default=0.0, comment="P50响应时间(ms)")
    p95_response_time = Column(Float, default=0.0, comment="P95响应时间(ms)")
    p99_response_time = Column(Float, default=0.0, comment="P99响应时间(ms)")
    requests_per_second = Column(Float, default=0.0, comment="每秒请求数(RPS)")
    failure_rate = Column(Float, default=0.0, comment="失败率(%)")

    stats_history = Column(JSON, default=list, comment="每秒统计快照列表")
    error_summary = Column(JSON, default=dict, comment="错误分类统计")
    endpoint_stats = Column(JSON, default=list, comment="各接口聚合统计（JMeter风格）")

    triggered_by = Column(Integer, ForeignKey("users.id"), comment="触发人ID")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
