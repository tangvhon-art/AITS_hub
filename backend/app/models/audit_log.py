"""
审计日志数据模型
"""
from datetime import datetime
from app.core.timezone import china_now_naive
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON
from app.database import Base


class AuditLog(Base):
    """审计日志表"""
    __tablename__ = "audit_logs"
    __table_args__ = {"comment": "审计日志表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    user_id = Column(Integer, nullable=True, index=True, comment="操作用户ID")
    username = Column(String(100), nullable=True, comment="操作用户名")
    action = Column(String(50), nullable=False, index=True, comment="操作类型：create/update/delete/login/logout/export/import")
    resource_type = Column(String(50), nullable=False, index=True, comment="资源类型：project/requirement/case/run/defect/report/plan/environment/user")
    resource_id = Column(Integer, nullable=True, comment="资源ID")
    resource_name = Column(String(500), nullable=True, comment="资源名称")
    detail = Column(JSON, default=dict, comment="操作详情（变更前后对比）")
    ip_address = Column(String(50), nullable=True, comment="IP地址")
    user_agent = Column(String(500), nullable=True, comment="用户代理")
    status = Column(String(20), default="success", comment="操作状态：success/failed")
    error_message = Column(Text, nullable=True, comment="错误信息")
    created_at = Column(DateTime, default=china_now_naive, index=True, comment="操作时间")
