"""
项目版本数据模型
"""
from datetime import datetime
from app.core.timezone import china_now_naive
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from app.database import Base, SoftDeleteMixin


class ProjectVersion(SoftDeleteMixin, Base):
    """项目版本表"""
    __tablename__ = "project_versions"
    __table_args__ = {"comment": "项目版本表"}

    id = Column(Integer, primary_key=True, index=True, comment="自增主键")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=False, index=True, comment="所属项目ID")
    name = Column(String(100), nullable=False, comment="版本名称")
    description = Column(Text, default="", comment="版本描述")
    status = Column(String(20), default="draft", index=True, comment="状态：draft-草稿，active-进行中，released-已发布，archived-已归档")
    start_date = Column(DateTime, nullable=True, comment="计划开始时间")
    end_date = Column(DateTime, nullable=True, comment="计划结束时间")
    released_at = Column(DateTime, nullable=True, comment="实际发布时间")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建人ID")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")
