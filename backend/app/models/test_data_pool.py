from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Float, Boolean, JSON
from app.database import Base, SoftDeleteMixin
from app.core.timezone import china_now_naive


class TestDataPool(SoftDeleteMixin, Base):
    """测试数据池表"""
    __tablename__ = "test_data_pools"
    __table_args__ = {"comment": "测试数据池表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=False, index=True, comment="所属项目ID")
    name = Column(String(200), nullable=False, comment="数据池名称")
    description = Column(Text, comment="数据池描述")

    data_type = Column(String(20), default="static", comment="数据类型: static/dynamic/generated")
    schema = Column(JSON, default=list, comment="数据字段定义: [{name, type, generator, default_value}]")
    data = Column(JSON, default=list, comment="静态数据行列表")
    generator_config = Column(JSON, default=dict, comment="动态生成配置: {generator, count, ...}")

    environment_id = Column(Integer, ForeignKey("test_environments.id"), comment="关联环境ID")

    created_by = Column(Integer, ForeignKey("users.id"), comment="创建人ID")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")


class EnvironmentVariableOverride(Base):
    """环境变量覆盖表"""
    __tablename__ = "env_variable_overrides"
    __table_args__ = {"comment": "环境变量覆盖表"}

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=False, index=True, comment="所属项目ID")
    environment_id = Column(Integer, ForeignKey("test_environments.id"), nullable=False, index=True, comment="环境ID")

    key = Column(String(200), nullable=False, comment="变量键名")
    value = Column(Text, comment="变量值")
    description = Column(String(500), comment="变量描述")
    is_sensitive = Column(Boolean, default=False, comment="是否敏感变量")

    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")
