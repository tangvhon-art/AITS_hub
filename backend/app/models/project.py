from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Project(Base):
    __tablename__ = "test_projects"
    __table_args__ = {"comment": "测试项目表"}

    id = Column(Integer, primary_key=True, index=True, comment="自增主键")
    name = Column(String(100), nullable=False, index=True, comment="项目名称")
    description = Column(Text, default="", comment="项目描述")
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="项目所有者ID")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    owner = relationship("User", backref="projects")
