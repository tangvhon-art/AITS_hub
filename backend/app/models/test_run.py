from datetime import datetime
from app.core.timezone import china_now_naive
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Float
from app.database import Base


class TestRun(Base):
    __tablename__ = "test_runs"
    __table_args__ = {"comment": "测试执行记录表"}

    id = Column(Integer, primary_key=True, index=True, comment="自增主键")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=False, index=True, comment="所属项目ID")
    case_id = Column(Integer, ForeignKey("test_cases.id"), nullable=True, index=True, comment="关联用例ID")
    plan_id = Column(Integer, nullable=True, comment="关联测试计划ID（MVP-3引入）")
    status = Column(String(20), default="pending", comment="状态：pending-等待，running-执行中，passed-通过，failed-失败，error-错误")
    actual_result = Column(Text, default="", comment="实际执行结果")
    execution_log = Column(Text, default="", comment="执行日志（JSON数组存储操作步骤）")
    screenshot_url = Column(String(500), default="", comment="截图文件路径")
    video_url = Column(String(500), default="", comment="录屏文件路径")
    error_message = Column(Text, default="", comment="错误信息")
    duration = Column(Float, default=0.0, comment="执行耗时（秒）")
    executed_by = Column(Integer, ForeignKey("users.id"), comment="执行人ID")
    started_at = Column(DateTime, nullable=True, comment="开始执行时间")
    completed_at = Column(DateTime, nullable=True, comment="执行完成时间")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
