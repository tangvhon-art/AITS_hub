"""基于 Redis 的接口限流器"""
import logging
import time
from typing import Optional

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

_memory_store: dict[str, list[float]] = {}


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(
    request: Request,
    key_prefix: str = "",
    limit: int = 10,
    window: int = 60,
):
    """通用限流检查（Redis 优先，降级内存）

    Args:
        request: FastAPI Request 对象
        key_prefix: 限流 key 前缀（如 "login", "ai_generate"）
        limit: 窗口内允许的最大请求数
        window: 时间窗口（秒）
    """
    ip = _get_client_ip(request)
    redis_key = f"rate_limit:{key_prefix}:{ip}" if key_prefix else f"rate_limit:{ip}"

    try:
        from app.database import redis_client
        if redis_client:
            count = redis_client.incr(redis_key)
            if count == 1:
                redis_client.expire(redis_key, window)
            if count > limit:
                raise HTTPException(
                    status_code=429,
                    detail=f"请求过于频繁，请在 {window} 秒后重试（限制: {limit} 次/ {window}s）",
                )
            return
    except HTTPException:
        raise
    except Exception as e:
        logger.debug(f"Redis 限流降级到内存: {e}")

    now = time.time()
    if redis_key not in _memory_store:
        _memory_store[redis_key] = []
    _memory_store[redis_key] = [t for t in _memory_store[redis_key] if now - t < window]
    if len(_memory_store[redis_key]) >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"请求过于频繁，请在 {window} 秒后重试（限制: {limit} 次/ {window}s）",
        )
    _memory_store[redis_key].append(now)
