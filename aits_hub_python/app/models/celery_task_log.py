"""
Celery 任务执行日志数据模型

由 worker 进程通过 celery signals（task_prerun/task_postrun/task_failure）
自动写入，供任务调度管理页面的执行日志查询使用。
"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text

from app.database import Base, SoftDeleteMixin
from app.core.timezone import china_now_naive


class CeleryTaskLog(SoftDeleteMixin, Base):
    """Celery 任务执行日志表"""
    __tablename__ = "sys_celery_task_log"
    __table_args__ = {"comment": "Celery任务执行日志表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    task_name = Column(String(255), nullable=False, index=True, comment="Celery任务名（全限定名）")
    task_key = Column(String(100), nullable=True, comment="关联定时任务唯一标识")
    task_id = Column(String(100), nullable=False, index=True, comment="Celery任务ID")
    args = Column(JSON, nullable=True, comment="任务位置参数")
    kwargs = Column(JSON, nullable=True, comment="任务关键字参数")
    queue = Column(String(50), default="default", comment="执行队列：default/ai/execution")
    state = Column(String(20), default="RUNNING", index=True, comment="执行状态：RUNNING/SUCCESS/FAILURE/TIMEOUT")
    started_at = Column(DateTime, default=china_now_naive, comment="开始时间")
    finished_at = Column(DateTime, nullable=True, comment="结束时间")
    duration_ms = Column(Integer, nullable=True, comment="执行耗时（毫秒）")
    exception = Column(Text, nullable=True, comment="异常摘要")
    traceback = Column(Text, nullable=True, comment="错误堆栈")
    created_at = Column(DateTime, default=china_now_naive, index=True, comment="创建时间")
