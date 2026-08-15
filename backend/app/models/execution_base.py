"""
执行结果模型公共基类

统一各执行记录表（TestRun / ApiExecution / TestPlanExecution / AutomationSuiteRun）
的公共字段，减少重复定义。

公共字段：
- status: 执行状态（pending/running/passed/failed/error/cancelled）
- started_at / completed_at: 起止时间
- error_message: 错误信息
- executed_by: 执行人
- trigger_type: 触发方式（manual/scheduled/api）
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey


class ExecutionMixin:
    """执行记录公共字段混入"""

    status = Column(String(20), default="pending", index=True,
                    comment="状态：pending-等待，running-执行中，passed-通过，failed-失败，error-错误，cancelled-已取消")
    started_at = Column(DateTime, nullable=True, comment="开始执行时间")
    completed_at = Column(DateTime, nullable=True, comment="执行完成时间")
    error_message = Column(Text, default="", comment="错误信息")
    executed_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment="执行人ID")
    trigger_type = Column(String(20), default="manual", comment="触发方式：manual-手动，scheduled-定时，api-接口触发")

    def mark_running(self):
        """标记为执行中"""
        from app.core.timezone import china_now_naive
        self.status = "running"
        self.started_at = china_now_naive()

    def mark_completed(self, status: str = "passed"):
        """标记为执行完成"""
        from app.core.timezone import china_now_naive
        self.status = status
        self.completed_at = china_now_naive()

    def mark_failed(self, error: str = ""):
        """标记为执行失败"""
        from app.core.timezone import china_now_naive
        self.status = "failed"
        self.error_message = error[:2000] if error else ""
        self.completed_at = china_now_naive()

    @property
    def duration_seconds(self) -> float:
        """计算执行耗时（秒）"""
        if self.started_at and self.completed_at:
            return round((self.completed_at - self.started_at).total_seconds(), 2)
        return 0.0
