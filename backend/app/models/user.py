from datetime import datetime
from app.core.timezone import china_now_naive
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from app.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"comment": "用户表"}

    id = Column(Integer, primary_key=True, index=True, comment="自增主键")
    username = Column(String(50), unique=True, index=True, nullable=False, comment="用户名")
    email = Column(String(100), unique=True, index=True, nullable=False, comment="邮箱")
    hashed_password = Column(String(255), nullable=False, comment="加密后的密码")
    full_name = Column(String(100), default="", comment="用户全名")
    is_active = Column(Boolean, default=True, comment="是否启用：0-禁用，1-启用")
    is_admin = Column(Boolean, default=False, comment="是否管理员：0-普通用户，1-管理员")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")
