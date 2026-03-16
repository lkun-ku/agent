"""Redis 缓存：基础 KV 与基于向量相似度的语义缓存。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from typing import Any

import numpy as np
from loguru import logger

try:
    import redis.asyncio as aioredis
except ImportError:  # pragma: no cover
    aioredis = None  # type: ignore[assignment]

# 语义缓存条目在 Redis 中的命名空间
_SEMANTIC_INDEX_KEY = "semantic_cache:index"
_SEMANTIC_ENTRY_PREFIX = "semantic_cache:entry:"


def _normalize_text(text: str) -> str:
    """轻量归一化：用于辅助相似度与展示。"""
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def _token_jaccard(a: str, b: str) -> float:
    """无嵌入时的回退：基于分词的 Jaccard 相似度。"""
    sa = set(a.split()) if a else set()
    sb = set(b.split()) if b else set()
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def _entry_id(query: str) -> str:
    """稳定 key：跨进程/重启一致，避免多 worker 重复写。"""
    return hashlib.sha256(_normalize_text(query).encode("utf-8")).hexdigest()[:16]


class RedisCache:
    """Redis 缓存管理器：支持 TTL、语义缓存（嵌入 + 余弦相似度）。"""

    def __init__(
        self,
        url: str = "redis://localhost:6379/0",
        *,
        semantic_embedder: Any | None = None,
        max_semantic_scan: int = 200,
        semantic_index_ttl: int = 3600,
    ) -> None:
        """
        :param url: Redis 连接 URL
        :param semantic_embedder: 可选，具备 encode(texts)->np.ndarray 的编码器
            （如 SentenceTransformer）
        :param max_semantic_scan: 语义匹配时最多扫描的缓存条目数
        """
        if aioredis is None:
            raise RuntimeError("未安装 redis 包，请安装 redis>=5")
        self._url = url
        self._client: Any = aioredis.from_url(url, decode_responses=True)
        self._semantic_embedder = semantic_embedder
        self._max_semantic_scan = max(1, max_semantic_scan)
        self._semantic_index_ttl = max(60, semantic_index_ttl)
        self._embed_lock = asyncio.Lock()

    async def get(self, key: str) -> str | None:
        """按键获取字符串值。"""
        try:
            val = await self._client.get(key)
            return val
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

    async def _encode_query(self, query: str) -> np.ndarray:
        """将查询编码为向量；无编码器时使用词袋哈希近似向量。"""
        q = _normalize_text(query)
        if self._semantic_embedder is not None:

            def _run():
                emb = self._semantic_embedder.encode(
                    [q],
                    convert_to_numpy=True,
                    show_progress_bar=False,
                )
                v = np.asarray(emb[0], dtype=np.float64)
                n = np.linalg.norm(v)
                if n > 0:
                    v = v / n
                return v

            async with self._embed_lock:
                return await asyncio.get_event_loop().run_in_executor(None, _run)

        # 回退：简易字符 n-gram 频率哈希为固定维度（无需外部模型）
        dim = 256
        vec = np.zeros(dim, dtype=np.float64)
        for i in range(len(q) - 1):
            idx = (ord(q[i]) * 31 + ord(q[i + 1])) % dim
            vec[idx] += 1.0
        n = np.linalg.norm(vec)
        if n > 0:
            vec = vec / n
        return vec

    @staticmethod
    def _cosine(a: np.ndarray, b: np.ndarray) -> float:
        denom = float(np.linalg.norm(a) * np.linalg.norm(b))
        if denom <= 0:
            return 0.0
        return float(np.dot(a, b) / denom)

    async def semantic_get(self, query: str, threshold: float = 0.95) -> str | None:
        """语义缓存：一次索引 GET + 一次 MGET；顺带清理已过期的索引条目。"""
        try:
            q_vec = await self._encode_query(query)
            q_norm = _normalize_text(query)

            index_raw = await self._client.get(_SEMANTIC_INDEX_KEY)
            if not index_raw:
                return None

            try:
                entry_ids: list[str] = json.loads(index_raw)
            except json.JSONDecodeError:
                logger.warning("语义索引损坏，已忽略")
                return None

            scanned_ids = entry_ids[: self._max_semantic_scan]
            keys = [_SEMANTIC_ENTRY_PREFIX + eid for eid in scanned_ids]
            raws = await self._client.mget(keys) if keys else []

            best_sim = -1.0
            best_value: str | None = None
            # 超出扫描窗口的 id 原样保留，避免误删
            alive_ids: list[str] = list(entry_ids[self._max_semantic_scan :])

            for eid, raw in zip(scanned_ids, raws):
                if not raw:
                    continue
                alive_ids.append(eid)
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                stored_query = str(payload.get("query_text", ""))
                value = str(payload.get("value", ""))
                emb_list = payload.get("embedding")

                if emb_list is not None:
                    s_vec = np.asarray(emb_list, dtype=np.float64)
                    sim = self._cosine(q_vec, s_vec)
                else:
                    sim = _token_jaccard(q_norm, _normalize_text(stored_query))

                if sim > best_sim:
                    best_sim = sim
                    best_value = value

            # 过期条目的 id 不再占用扫描窗口
            if len(alive_ids) != len(entry_ids):
                await self._client.set(
                    _SEMANTIC_INDEX_KEY,
                    json.dumps(alive_ids),
                    ex=self._semantic_index_ttl,
                )

            if best_sim >= threshold and best_value is not None:
                logger.debug(
                    "语义缓存命中 similarity={:.4f} threshold={}",
                    best_sim,
                    threshold,
                )
                return best_value

            return None
        except Exception as exc:
            logger.exception("semantic_get 失败: {}", exc)
            raise

    async def semantic_set(
        self,
        query: str,
        value: str,
        ttl: int = 3600,
    ) -> None:
        """写入语义缓存条目（稳定 key + 索引上限 + 索引 TTL）。"""
        q_vec = await self._encode_query(query)
        eid = _entry_id(query)

        payload = {
            "query_text": query,
            "value": value,
            "embedding": q_vec.tolist(),
        }
        key = _SEMANTIC_ENTRY_PREFIX + eid
        try:
            raw = json.dumps(payload, ensure_ascii=False)
            if ttl > 0:
                await self._client.setex(key, ttl, raw)
            else:
                await self._client.set(key, raw)

            index_raw = await self._client.get(_SEMANTIC_INDEX_KEY)
            ids: list[str] = []
            if index_raw:
                try:
                    ids = json.loads(index_raw)
                except json.JSONDecodeError:
                    ids = []
            if eid not in ids:
                ids.append(eid)
            ids = ids[-self._max_semantic_scan :]
            await self._client.set(
                _SEMANTIC_INDEX_KEY,
                json.dumps(ids),
                ex=max(self._semantic_index_ttl, ttl),
            )
        except Exception as exc:
            logger.exception("semantic_set 失败: {}", exc)
            raise

    async def aclose(self) -> None:
        """关闭连接。"""
        try:
            await self._client.aclose()
        except Exception as exc:
            logger.warning("关闭 Redis 连接时异常: {}", exc)
