from sqlalchemy import create_engine, event, Column, Boolean, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings
from app.core.timezone import china_now_naive

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=settings.DEBUG,
)


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


@event.listens_for(SessionLocal, "do_orm_execute")
def _apply_soft_delete_filter(orm_execute_state):
    """
    全局 ORM 查询钩子：自动为含 is_deleted 列的表过滤已删除记录。
    遍历语句涉及的所有 FROM 表，发现 is_deleted 列就追加过滤条件。
    """
    if not orm_execute_state.is_select:
        return
    stmt = orm_execute_state.statement
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
