from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base, SoftDeleteMixin
from app.core.timezone import china_now_naive


class ProjectMember(SoftDeleteMixin, Base):
    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uk_project_user"),
        {"comment": "项目成员关联表"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True, index=True, comment="自增主键")
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=False, index=True, comment="所属项目ID")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="成员用户ID")
    role = Column(String(20), nullable=False, default="member", comment="成员角色：owner-所有者，admin-管理员，member-普通成员")
    joined_at = Column(DateTime, default=china_now_naive, comment="加入项目时间")
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")

    project = relationship("Project", backref="members")
    user = relationship("User", backref="project_memberships")
