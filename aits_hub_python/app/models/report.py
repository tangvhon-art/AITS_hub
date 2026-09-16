from datetime import datetime
from app.core.timezone import china_now_naive
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON, Float
from app.database import Base, SoftDeleteMixin


class TestReport(SoftDeleteMixin, Base):
    __tablename__ = "test_reports"
    __table_args__ = {"comment": "测试报告表"}

    id = Column(Integer, primary_key=True, index=True, comment="自增主键")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=False, index=True, comment="所属项目ID")
    version_id = Column(Integer, ForeignKey("project_versions.id"), nullable=True, index=True, comment="所属版本ID")
    title = Column(String(200), nullable=False, comment="报告标题")
    report_type = Column(String(50), default="summary", comment="报告类型：summary-汇总，execution-执行，defect-缺陷，full-完整，performance-性能")
    status = Column(String(20), default="generating", comment="状态：generating-生成中，completed-已完成，failed-生成失败")
    content = Column(Text, default="", comment="报告内容（Markdown/HTML）")
    summary = Column(JSON, default=dict, comment="报告摘要数据（JSON）")
    total_cases = Column(Integer, default=0, comment="用例总数")
    passed_cases = Column(Integer, default=0, comment="通过用例数")
    failed_cases = Column(Integer, default=0, comment="失败用例数")
    pass_rate = Column(Float, default=0.0, comment="通过率（百分比）")
    total_defects = Column(Integer, default=0, comment="缺陷总数")
    open_defects = Column(Integer, default=0, comment="未解决缺陷数")
    total_runs = Column(Integer, default=0, comment="执行次数")
    avg_duration = Column(Float, default=0.0, comment="平均执行耗时（秒）")
    file_url = Column(String(500), default="", comment="报告文件路径")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建人ID")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")
