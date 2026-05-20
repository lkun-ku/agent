"""Redis 语义缓存基线：命中一次要多少次 GET、过期条目如何占用扫描窗口。

用法：
    docker compose up -d redis
    .\\.venv\\Scripts\\python.exe scripts\\bench_cache.py --entries 200

说明：
- 用独立 DB 15，避免影响其它数据；
- 不依赖嵌入模型（semantic_embedder=None 时走字符 bigram 哈希，纯本地）；
- GET 次数从 Redis `INFO commandstats` 读取，是真实命令计数。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from loguru import logger  # noqa: E402

logger.remove()

from app.infrastructure.cache.redis_cache import (  # noqa: E402
    _SEMANTIC_ENTRY_PREFIX,
    _SEMANTIC_INDEX_KEY,
    RedisCache,
)

URL = "redis://localhost:6379/15"


async def get_calls(client) -> int:
    stats = await client.info("commandstats")
    item = stats.get("cmdstat_get") or {}
    return int(item.get("calls", 0)) if isinstance(item, dict) else 0


async def get_mget_calls(client) -> int:
    stats = await client.info("commandstats")
    item = stats.get("cmdstat_mget") or {}
    return int(item.get("calls", 0)) if isinstance(item, dict) else 0


async def populate(cache: RedisCache, n: int, ttl: int = 3600) -> list[str]:
    for i in range(n):
        await cache.semantic_set(f"查询{i}：向量检索的召回率怎么算", f"答案{i}", ttl=ttl)
    raw = await cache._client.get(_SEMANTIC_INDEX_KEY)
    return json.loads(raw) if raw else []


async def main_async(entries: int) -> None:
    cache = RedisCache(URL, semantic_embedder=None)
    client = cache._client
    await client.flushdb()

    print("=" * 78)
    print(f"Redis 语义缓存基线：{entries} 条缓存 / DB 15 / 无嵌入模型（bigram 回退）")
    print("=" * 78)

    ids = await populate(cache, entries)
    print(f"索引条目数={len(ids)}  DB key 数={await client.dbsize()}")

    # 1) 命中路径：GET / MGET 次数 + 耗时
    query = "查询0：向量检索的召回率怎么算"
    before_get = await get_calls(client)
    before_mget = await get_mget_calls(client)
    t0 = time.perf_counter()
    hit = await cache.semantic_get(query)
    hit_ms = (time.perf_counter() - t0) * 1000
    after_get = await get_calls(client)
    after_mget = await get_mget_calls(client)
    print(
        f"\n[命中] value={'命中' if hit else '未命中'} | 耗时={hit_ms:.1f} ms | "
        f"GET={after_get - before_get} | MGET={after_mget - before_mget}"
    )

    # 2) 等价批量读取：MGET 一次往返
    keys = [_SEMANTIC_ENTRY_PREFIX + eid for eid in ids]
    t0 = time.perf_counter()
    values = await client.mget(keys)
    mget_ms = (time.perf_counter() - t0) * 1000
    print(f"[对照] MGET {len(keys)} 条 | 耗时={mget_ms:.1f} ms | 返回={sum(v is not None for v in values)} 条")

    # 3) 过期条目：entry 过期但索引还在
    await client.flushdb()
    await populate(cache, 50, ttl=1)
    await asyncio.sleep(1.5)
    index_len = len(json.loads(await client.get(_SEMANTIC_INDEX_KEY) or "[]"))
    db_keys = await client.dbsize()
    before = await get_calls(client)
    t0 = time.perf_counter()
    expired_hit = await cache.semantic_get(query)
    expired_ms = (time.perf_counter() - t0) * 1000
    after = await get_calls(client)
    index_after = len(json.loads(await client.get(_SEMANTIC_INDEX_KEY) or "[]"))
    print(
        f"\n[过期] 调用前索引={index_len} 条 | 实际 key={db_keys} 个 | "
        f"命中={'是' if expired_hit else '否'} | 耗时={expired_ms:.1f} ms | GET={after - before}"
    )
    print(f"清理后索引={index_after} 条（存活条目数为 0 时应为 0）。")

    await cache.aclose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entries", type=int, default=200)
    args = parser.parse_args()
    asyncio.run(main_async(args.entries))


if __name__ == "__main__":
    main()
