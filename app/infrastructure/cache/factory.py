"""Redis 缓存工厂：供 RAG 缓存等主链路复用。"""

from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.infrastructure.cache.redis_cache import RedisCache


@lru_cache(maxsize=1)
def get_redis_cache() -> RedisCache:
    """进程级 Redis 缓存单例。"""
    return RedisCache(get_settings().redis_url)


async def close_redis_cache() -> None:
    """应用关闭时释放连接。"""
    cache = get_redis_cache()
    await cache.aclose()
    get_redis_cache.cache_clear()


__all__ = ["close_redis_cache", "get_redis_cache"]
