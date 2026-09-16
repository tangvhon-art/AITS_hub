from sqlalchemy import create_engine, event, Column, Boolean, DateTime, Integer, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings
from app.core.timezone import china_now_naive

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=settings.DEBUG,
)

redis_client = None
try:
    import redis as redis_lib
    redis_client = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
    redis_client.ping()
except Exception:
    redis_client = None


@event.listens_for(engine, "connect")
def set_mysql_timezone(dbapi_connection, connection_record):
    """设置数据库连接时区为中国时间 UTC+8"""
    cursor = dbapi_connection.cursor()
    cursor.execute("SET time_zone = '+08:00'")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class SoftDeleteMixin:
    """软删混入类，给业务表提供 is_deleted / deleted_at 字段"""
    is_deleted = Column(Boolean, default=False, index=True, comment="是否已删除：0-未删除，1-已删除")
    deleted_at = Column(DateTime, nullable=True, comment="删除时间")

    def soft_delete(self):
        """标记为已删除"""
        self.is_deleted = True
        self.deleted_at = china_now_naive()

    def restore(self):
        """恢复已删除记录"""
        self.is_deleted = False
        self.deleted_at = None


class TimestampMixin:
    """时间戳混入类，统一提供 created_at / updated_at 字段"""
    created_at = Column(DateTime, default=china_now_naive, comment="创建时间")
    updated_at = Column(DateTime, default=china_now_naive, onupdate=china_now_naive, comment="更新时间")


class ProjectScopedMixin:
    """项目级数据混入，统一提供 project_id 字段

    适用于所有绑定到项目的业务模型。新模型可直接继承此 Mixin，
    避免每个模型重复定义 project_id 列。
    """
    project_id = Column(
        Integer,
        ForeignKey("test_projects.id"),
        nullable=False,
        index=True,
        comment="所属项目ID",
    )


class CreatedByMixin:
    """创建人混入，统一提供 created_by 字段"""
    created_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        comment="创建人ID",
    )


class BaseModelMixin(SoftDeleteMixin, TimestampMixin, CreatedByMixin):
    """基础模型混入：软删除 + 时间戳 + 创建人

    新模型推荐继承此 Mixin 以获得统一的公共字段。
    如需项目级隔离，可同时继承 ProjectScopedMixin。

    用法::

        class MyModel(BaseModelMixin, ProjectScopedMixin, Base):
            __tablename__ = "my_table"
            id = Column(Integer, primary_key=True)
            name = Column(String(100))
    """
    pass


@event.listens_for(SessionLocal, "do_orm_execute")
def _apply_soft_delete_filter(orm_execute_state):
    """
    全局 ORM 查询钩子：自动为含 is_deleted 列的表过滤已删除记录。
    遍历语句涉及的所有 FROM 表，发现 is_deleted 列就追加过滤条件。
    查询可通过 execution_options(skip_soft_delete=True) 跳过该过滤（用于展示/恢复已删除记录）。
    """
    if not orm_execute_state.is_select:
        return
    stmt = orm_execute_state.statement
    if stmt.get_execution_options().get("skip_soft_delete"):
        return
    try:
        froms = stmt.get_final_froms()
    except Exception:
        return
    modified = False
    for frm in froms:
        cols = getattr(frm, "columns", None)
        if cols is not None and "is_deleted" in cols:
            stmt = stmt.filter(cols.is_deleted == False)
            modified = True
    if modified:
        orm_execute_state.statement = stmt


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
