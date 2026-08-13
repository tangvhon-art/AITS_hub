from datetime import datetime
from app.core.timezone import china_now_naive
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from app.database import Base, SoftDeleteMixin


class KnowledgeDoc(SoftDeleteMixin, Base):
    __tablename__ = "knowledge_docs"
    __table_args__ = {"comment": "知识库文档表"}

    id = Column(Integer, primary_key=True, index=True, comment="自增主键")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=False, index=True, comment="所属项目ID")
    title = Column(String(200), nullable=False, comment="文档标题")
    content = Column(Text, default="", comment="文档内容")
    file_path = Column(String(500), default="", comment="原始文件路径")
    file_type = Column(String(50), default="text", comment="文件类型：text/markdown/docx/pdf")
    chunk_count = Column(Integer, default=0, comment="切分后的块数量")
    status = Column(String(20), default="pending", comment="状态：pending-待处理，processing-处理中，ready-就绪，failed-失败")
    error_message = Column(Text, default="", comment="处理错误信息")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建人ID")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")
