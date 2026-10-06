"""Redis 缓存工厂：供 RAG 缓存等主链路复用。"""

from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.infrastructure.cache.redis_cache import RedisCache


@lru_cache(maxsize=1)
def get_redis_cache() -> RedisCache:
    """进程级 Redis 缓存单例。"""
    settings = get_settings()
    return RedisCache(
        settings.redis_url,
        socket_timeout=settings.redis_socket_timeout,
        socket_connect_timeout=settings.redis_socket_connect_timeout,
        health_check_interval=settings.redis_health_check_interval,
    )


async def close_redis_cache() -> None:
    """应用关闭时释放连接。"""
    cache = get_redis_cache()
    await cache.aclose()
    get_redis_cache.cache_clear()


__all__ = ["close_redis_cache", "get_redis_cache"]
