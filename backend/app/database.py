from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

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


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
