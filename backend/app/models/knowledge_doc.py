from datetime import datetime
from app.core.timezone import china_now_naive
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON, Float
from app.database import Base, SoftDeleteMixin


class KnowledgeDoc(SoftDeleteMixin, Base):
    __tablename__ = "knowledge_docs"
    __table_args__ = {"comment": "知识库文档表"}

    id = Column(Integer, primary_key=True, index=True, comment="自增主键")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=False, index=True, comment="所属项目ID")
    title = Column(String(200), nullable=False, comment="文档标题")
    content = Column(Text, default="", comment="文档完整内容")
    file_path = Column(String(500), default="", comment="原始文件路径")
    file_type = Column(String(50), default="text", comment="文件类型：text/markdown/docx/pdf")
    file_size = Column(Integer, default=0, comment="原始文件大小(字节)")
    source_type = Column(String(30), default="manual", comment="来源类型：manual-手动创建，upload-文件上传，requirement-需求同步")
    source_id = Column(Integer, nullable=True, index=True, comment="来源对象ID（如需求ID）")
    chunk_count = Column(Integer, default=0, comment="切分后的块数量")
    chunk_strategy = Column(String(20), default="fixed", comment="切片策略：fixed/sentence")
    chunk_size = Column(Integer, default=500, comment="切片大小(字符数)")
    overlap = Column(Integer, default=50, comment="切片重叠大小(字符数)")
    status = Column(String(20), default="pending", comment="状态：pending-待处理，processing-处理中，ready-就绪，failed-失败")
    error_message = Column(Text, default="", comment="处理错误信息")
    created_by = Column(Integer, ForeignKey("users.id"), comment="创建人ID")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")


class KnowledgeChunk(Base):
    """知识库文档切片表（与文档分离，用于 RAG 检索）"""
    __tablename__ = "knowledge_chunks"
    __table_args__ = {"comment": "知识库文档切片表"}

    id = Column(Integer, primary_key=True, index=True, comment="自增主键")
    doc_id = Column(Integer, ForeignKey("knowledge_docs.id"), nullable=False, index=True, comment="关联文档ID")
    project_id = Column(Integer, nullable=False, index=True, comment="所属项目ID（冗余，加速按项目检索）")
    chunk_index = Column(Integer, nullable=False, default=0, comment="文档内切片序号")
    content = Column(Text, nullable=False, comment="切片文本内容")
    token_count = Column(Integer, default=0, comment="切片 token 数")
    embedding = Column(JSON, nullable=True, comment="向量嵌入（JSON 数组存储）")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
