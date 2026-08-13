from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from app.database import Base


class TestRequirement(Base):
    __tablename__ = "test_requirements"
    __table_args__ = {"comment": "测试需求表"}

    id = Column(Integer, primary_key=True, index=True, comment="自增主键")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=False, index=True, comment="所属项目ID")
    title = Column(String(200), nullable=False, comment="需求标题")
    content = Column(Text, default="", comment="需求内容")
    source = Column(String(50), default="manual", comment="需求来源：manual-手动输入，upload-文档上传，feishu-飞书")
    source_url = Column(String(500), default="", comment="来源链接")
    status = Column(String(20), default="pending", comment="状态：pending-待生成，generated-已生成，reviewed-已评审")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建人ID")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
