"""
中国时区时间工具
统一使用 Asia/Shanghai (UTC+8) 时间
"""
from datetime import datetime, timedelta, timezone

# 中国时区 UTC+8
CHINA_TZ = timezone(timedelta(hours=8))


def china_now() -> datetime:
    """获取中国当前时间（带时区信息）"""
    return datetime.now(CHINA_TZ)


def china_now_naive() -> datetime:
    """获取中国当前时间（无时区信息，用于数据库存储）"""
    return datetime.now(CHINA_TZ).replace(tzinfo=None)


def to_china_time(dt: datetime) -> datetime:
    """将任意时间转换为中国时间"""
    if dt.tzinfo is None:
        # 假设是 UTC 时间
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(CHINA_TZ)


def format_china_time(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """格式化为中国时间字符串"""
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(CHINA_TZ).strftime(fmt)
