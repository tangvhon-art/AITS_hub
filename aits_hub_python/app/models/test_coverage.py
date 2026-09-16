from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Float, Boolean, JSON
from app.database import Base, SoftDeleteMixin
from app.core.timezone import china_now_naive


class CoverageConfig(SoftDeleteMixin, Base):
    """覆盖率配置表"""
    __tablename__ = "coverage_configs"
    __table_args__ = {"comment": "覆盖率配置表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=False, index=True, comment="所属项目ID")
    version_id = Column(Integer, ForeignKey("project_versions.id"), comment="版本ID")

    excluded_paths = Column(JSON, default=list, comment="排除的路径模式列表")
    excluded_methods = Column(JSON, default=list, comment="排除的HTTP方法列表")
    critical_scenario_ids = Column(JSON, default=list, comment="核心路径场景ID列表")

    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")


class CoverageSnapshot(Base):
    """覆盖率快照表"""
    __tablename__ = "coverage_snapshots"
    __table_args__ = {"comment": "覆盖率快照表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=False, index=True, comment="所属项目ID")
    version_id = Column(Integer, ForeignKey("project_versions.id"), comment="版本ID")

    total_apis = Column(Integer, default=0, comment="API总数")
    covered_apis = Column(Integer, default=0, comment="已覆盖API数")
    api_coverage_rate = Column(Float, default=0.0, comment="接口覆盖率(%)")
    uncovered_apis = Column(JSON, default=list, comment="未覆盖API列表")

    total_scenarios = Column(Integer, default=0, comment="场景总数")
    covered_scenarios = Column(Integer, default=0, comment="已覆盖场景数")
    scenario_coverage_rate = Column(Float, default=0.0, comment="场景覆盖率(%)")

    total_cases = Column(Integer, default=0, comment="用例总数")
    cases_with_api = Column(Integer, default=0, comment="关联API的用例数")

    coverage_matrix = Column(JSON, default=dict, comment="覆盖率矩阵: {api_id: {covered, case_ids, scenario_ids}}")

    calculated_at = Column(DateTime, default=china_now_naive, comment="计算时间")
