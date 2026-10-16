"""Redis 缓存：RAG 结果使用的精确 KV 缓存。"""

from __future__ import annotations

from typing import Any

from loguru import logger

aioredis: Any | None = None

try:
    import redis.asyncio as aioredis
except ImportError:  # pragma: no cover
    aioredis = None



class RedisCache:
    """Redis 缓存管理器：支持 TTL 与健康检查。"""

    def __init__(
        self,
        url: str = "redis://localhost:6379/0",
        *,
        socket_timeout: float = 5.0,
        socket_connect_timeout: float = 5.0,
        health_check_interval: int = 30,
    ) -> None:
        if aioredis is None:
            raise RuntimeError("未安装 redis 包，请安装 redis>=5")
        self._url = url
        self._client: Any = aioredis.from_url(
            url,
            decode_responses=True,
            socket_timeout=socket_timeout,
            socket_connect_timeout=socket_connect_timeout,
            health_check_interval=health_check_interval,
        )

    async def ping(self) -> bool:
        """检查 Redis 连接。"""
        return bool(await self._client.ping())

    async def get(self, key: str) -> str | None:
        """按键获取字符串值。"""
        try:
            value = await self._client.get(key)
            return None if value is None else str(value)
        except Exception as exc:
            logger.exception("Redis GET 失败 key={}: {}", key, exc)
            raise

    async def set(self, key: str, value: str, ttl: int = 3600) -> None:
        """设置字符串值与 TTL（秒）。"""
        try:
            if ttl > 0:
                await self._client.setex(key, ttl, value)
            else:
                await self._client.set(key, value)
        except Exception as exc:
            logger.exception("Redis SET 失败 key={}: {}", key, exc)
            raise

    async def aclose(self) -> None:
        """关闭连接。"""
        try:
            await self._client.aclose()
        except Exception as exc:
            logger.warning("关闭 Redis 连接时异常: {}", exc)
