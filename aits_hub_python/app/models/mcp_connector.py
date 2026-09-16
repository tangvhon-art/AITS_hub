"""MCP 连接器模型"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON
from app.database import Base
from app.core.timezone import china_now_naive


class MCPConnector(Base):
    """MCP 连接器配置"""
    __tablename__ = "mcp_connectors"
    __table_args__ = {"comment": "MCP连接器配置表（外部MCP Server连接管理，全局公共）"}

    id = Column(Integer, primary_key=True, comment="主键ID")
    name = Column(String(100), nullable=False, comment="连接器名称")
    description = Column(String(500), comment="描述")
    transport = Column(String(20), default="sse", comment="传输方式: sse/stdio/http")
    url = Column(String(500), comment="SSE/HTTP 模式的服务地址")
    command = Column(String(500), comment="stdio 模式的启动命令")
    args = Column(JSON, comment="stdio 模式的命令参数数组")
    env_vars = Column(JSON, comment="环境变量字典")
    status = Column(String(20), default="disconnected", comment="连接状态: connected/disconnected/error")
    tools_count = Column(Integer, default=0, comment="已加载工具数量")
    tools_list = Column(JSON, comment="工具列表缓存 [{name, description}]")
    last_connected_at = Column(DateTime, comment="最后连接时间")
    error_message = Column(Text, comment="最后错误信息")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_by = Column(Integer, comment="创建人ID")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")
    is_deleted = Column(Boolean, default=False, comment="软删除标记")
    deleted_at = Column(DateTime, comment="删除时间")
