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

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    project_id = Column(Integer, ForeignKey("test_projects.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False, default="member")  # owner / admin / member
    joined_at = Column(DateTime, default=china_now_naive)
    created_at = Column(DateTime, default=china_now_naive)
    updated_at = Column(DateTime, onupdate=china_now_naive)

    project = relationship("Project", backref="members")
    user = relationship("User", backref="project_memberships")
