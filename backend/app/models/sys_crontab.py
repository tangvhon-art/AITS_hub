"""
系统定时任务配置数据模型

sys_crontab 表是动态 Celery Beat 的数据源：
Beat 进程的自定义 DatabaseScheduler 定期轮询本表生成调度计划，
新增/修改/删除/启停任务无需重启 beat。
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON

from app.database import Base, BaseModelMixin


class SysCrontab(BaseModelMixin, Base):
    """系统定时任务配置表"""
    __tablename__ = "sys_crontab"
    __table_args__ = {"comment": "系统定时任务配置表（动态Celery Beat数据源）"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    name = Column(String(200), nullable=False, comment="任务名称")
    task_key = Column(String(100), nullable=True, index=True, comment="任务唯一标识（不可重复）")
    task = Column(String(255), nullable=False, index=True, comment="Celery任务名（全限定名）")
    args = Column(JSON, nullable=True, comment="任务位置参数列表")
    kwargs = Column(JSON, nullable=True, comment="任务关键字参数字典")
    queue = Column(String(50), default="default", comment="目标队列：default/ai/execution")
    schedule_type = Column(String(20), default="interval", comment="调度类型：interval-间隔秒数/cron-cron表达式")
    every_seconds = Column(Integer, nullable=True, comment="间隔秒数（schedule_type=interval时有效）")
    minute = Column(String(100), default="*", comment="cron-分钟（0-59，支持*/,-）")
    hour = Column(String(100), default="*", comment="cron-小时（0-23）")
    day_of_week = Column(String(100), default="*", comment="cron-星期（0-6，0=周一）")
    day_of_month = Column(String(100), default="*", comment="cron-日（1-31）")
    month_of_year = Column(String(100), default="*", comment="cron-月（1-12）")
    enabled = Column(Boolean, nullable=False, default=True, server_default="1", index=True, comment="是否启用：0-禁用，1-启用")
    last_run_at = Column(DateTime, nullable=True, comment="最近执行时间")
    total_run_count = Column(Integer, nullable=False, default=0, server_default="0", comment="累计执行次数")
    description = Column(String(500), nullable=True, comment="任务描述")
