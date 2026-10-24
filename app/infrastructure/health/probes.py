"""依赖健康探测：API 与运维工具共用。"""

from __future__ import annotations

from sqlalchemy import text

from app.config import Settings
from app.infrastructure.cache.redis_cache import RedisCache
from app.infrastructure.database.session import init_engine
from app.infrastructure.vectordb.factory import create_milvus_manager


async def probe_postgres(settings: Settings) -> None:
    """探测 PostgreSQL；失败抛出异常。"""
    engine = init_engine(
        settings.database_url,
        connect_timeout=settings.database_connect_timeout,
        command_timeout=settings.database_command_timeout,
    )
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
    finally:
        await engine.dispose()


async def probe_redis(settings: Settings) -> None:
    """探测 Redis；失败抛出异常。"""
    cache = RedisCache(
        settings.redis_url,
        socket_timeout=settings.redis_socket_timeout,
        socket_connect_timeout=settings.redis_socket_connect_timeout,
        health_check_interval=settings.redis_health_check_interval,
    )
    try:
        if not await cache.ping():
            raise RuntimeError("Redis ping 返回 False")
    finally:
        await cache.aclose()


async def probe_milvus(settings: Settings) -> int:
    """探测 Milvus 集合并返回实体数；集合缺失时抛出异常。"""
    manager = create_milvus_manager(settings, alias="health")
    if not await manager.collection_exists(settings.rag_collection_name):
        raise RuntimeError("Milvus 集合不存在")
    return await manager.collection_count(settings.rag_collection_name)


__all__ = ["probe_milvus", "probe_postgres", "probe_redis"]
