# -*- coding: utf-8 -*-
"""3.2：语义缓存要用稳定 key、一次 MGET 命中，并清理过期索引。"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.infrastructure.cache.redis_cache import (
    _SEMANTIC_ENTRY_PREFIX,
    _SEMANTIC_INDEX_KEY,
    RedisCache,
)


class FakeClient:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.get_calls = 0
        self.mget_calls = 0

    async def get(self, key: str) -> str | None:
        self.get_calls += 1
        return self.data.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.data[key] = value

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.data[key] = value

    async def mget(self, keys: list[str]) -> list[str | None]:
        self.mget_calls += 1
        return [self.data.get(k) for k in keys]


def make_cache() -> RedisCache:
    cache = RedisCache("redis://localhost:1/0")
    cache._client = FakeClient()  # type: ignore[assignment]
    return cache


@pytest.mark.asyncio
async def test_same_query_uses_stable_key_and_mget() -> None:
    cache = make_cache()
    await cache.semantic_set("向量检索怎么做", "答案A", ttl=60)
    await cache.semantic_set("向量检索怎么做", "答案A", ttl=60)

    index = json.loads(cache._client.data[_SEMANTIC_INDEX_KEY])  # type: ignore[attr-defined]
    assert len(index) == 1, "相同 query 不应产生重复条目"

    client: Any = cache._client
    client.get_calls = 0
    client.mget_calls = 0

    assert await cache.semantic_get("向量检索怎么做") == "答案A"
    assert client.get_calls == 1, "只允许一次索引 GET"
    assert client.mget_calls == 1, "命中路径必须用 MGET"


@pytest.mark.asyncio
async def test_expired_entries_are_pruned_from_index() -> None:
    cache = make_cache()
    await cache.semantic_set("查询一", "1")
    await cache.semantic_set("查询二", "2")

    index = json.loads(cache._client.data[_SEMANTIC_INDEX_KEY])  # type: ignore[attr-defined]
    dead_key = _SEMANTIC_ENTRY_PREFIX + index[0]
    del cache._client.data[dead_key]  # type: ignore[attr-defined]

    await cache.semantic_get("查询二")

    remaining = json.loads(cache._client.data[_SEMANTIC_INDEX_KEY])  # type: ignore[attr-defined]
    assert len(remaining) == 1
    assert len(remaining) < len(index)
