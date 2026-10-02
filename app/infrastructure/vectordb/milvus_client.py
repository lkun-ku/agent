"""Milvus 向量库管理器：集合生命周期与向量检索封装。"""

from __future__ import annotations

import asyncio
import warnings
from collections.abc import Callable
from typing import Any, TypeVar

from loguru import logger

try:
    from pymilvus import (
        Collection,
        CollectionSchema,
        DataType,
        FieldSchema,
        connections,
        utility,
    )
except ImportError:  # pragma: no cover
    Collection = Any
    CollectionSchema = Any
    DataType = Any
    FieldSchema = Any
    connections = Any
    utility = Any

try:
    from pymilvus import PyMilvusDeprecationWarning

    # pymilvus 2.x 的 ORM API 仍在使用；升级到 3.x 前先屏蔽第三方弃用日志。
    warnings.filterwarnings("ignore", category=PyMilvusDeprecationWarning)
except ImportError:  # pragma: no cover
    pass


T = TypeVar("T")


def _run_sync(func: Callable[..., T], *args: Any, **kwargs: Any) -> asyncio.Future[T]:
    """在线程池中执行同步 Milvus SDK 调用，避免阻塞事件循环。"""
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, lambda: func(*args, **kwargs))


class MilvusManager:
    """Milvus 向量数据库管理器（异步包装同步 SDK）。"""

    def __init__(
        self,
        host: str = "localhost",
        port: str = "19530",
        alias: str = "default",
        **conn_kwargs: Any,
    ) -> None:
        self._host = host
        self._port = port
        self._alias = alias
        self._conn_kwargs = conn_kwargs
        self._connected = False

    async def _ensure_connection(self) -> None:
        if self._connected:
            return
        try:

            def _connect() -> None:
                connections.connect(
                    alias=self._alias,
                    host=self._host,
                    port=self._port,
                    **self._conn_kwargs,
                )

            await _run_sync(_connect)
            self._connected = True
            logger.info("已连接 Milvus {}:{}", self._host, self._port)
        except Exception as exc:
            logger.exception("连接 Milvus 失败: {}", exc)
            raise

    async def collection_exists(self, name: str) -> bool:
        """判断集合是否存在（供上层自愈逻辑使用）。"""
        await self._ensure_connection()
        return bool(await _run_sync(utility.has_collection, name, self._alias))

    async def collection_count(self, name: str) -> int:
        """返回集合中的实体数；集合不存在时返回 0（用于判断是否需要回填）。"""
        if not await self.collection_exists(name):
            return 0

        def _count() -> int:
            col = Collection(name, using=self._alias)
            return int(col.num_entities)

        return int(await _run_sync(_count))

    async def create_collection(
        self,
        name: str,
        dim: int,
        extra_fields: list[Any] | None = None,
    ) -> None:
        """创建向量集合；若已存在则跳过。

        :param extra_fields: 额外的 ``FieldSchema`` 列表。默认只建 ``id``（主键）与
            ``embedding``；若需要对接 ``MultiRetriever``（要求 ``text`` 字段）或
            ``LongTermMemory``（要求 ``content``/``session_id``/``meta``），需在此传入。
        """
        await self._ensure_connection()

        def _create() -> None:
            if utility.has_collection(name, using=self._alias):
                logger.info("集合 [{}] 已存在，跳过创建", name)
                return
            fields = [
                FieldSchema(
                    name="id",
                    dtype=DataType.VARCHAR,
                    is_primary=True,
                    max_length=64,
                ),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
            ]
            if extra_fields:
                fields.extend(extra_fields)
            schema = CollectionSchema(
                fields=fields,
                description=f"向量集合 {name}",
            )
            col = Collection(name, schema, using=self._alias)
            idx = {"index_type": "IVF_FLAT", "metric_type": "L2", "params": {"nlist": 128}}
            col.create_index(field_name="embedding", index_params=idx)
            logger.info("已创建集合 [{}] dim={}", name, dim)

        try:
            await _run_sync(_create)
        except Exception as exc:
            logger.exception("创建集合失败 name={}: {}", name, exc)
            raise

    async def insert(
        self,
        collection: str,
        vectors: list[list[float]],
        metadata: list[dict[str, Any]],
    ) -> list[str]:
        """插入向量与元数据；主键取自 metadata 中的 id 字段。"""
        await self._ensure_connection()
        if len(vectors) != len(metadata):
            raise ValueError("vectors 与 metadata 长度必须一致")

        ids: list[str] = []
        for i, m in enumerate(metadata):
            rid = m.get("id")
            if rid is None:
                rid = f"auto_{i}"
            ids.append(str(rid))

        def _insert() -> None:
            col = Collection(collection, using=self._alias)
            if any(len(m) > 1 for m in metadata):
                # 含额外字段时按“字段名 -> 值”的字典行插入
                rows = [
                    {**m, "id": rid, "embedding": vec}
                    for rid, vec, m in zip(ids, vectors, metadata, strict=True)
                ]
                col.insert(rows)
            else:
                col.insert([ids, vectors])
            col.flush()

        try:
            await _run_sync(_insert)
            return ids
        except Exception as exc:
            logger.exception("Milvus 插入失败 collection={}: {}", collection, exc)
            raise

    async def search(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int = 10,
        *,
        output_fields: list[str] | None = None,
        **search_params: Any,
    ) -> list[dict[str, Any]]:
        """向量相似度检索，返回命中 id、距离与指定的额外字段。"""
        await self._ensure_connection()
        params = search_params.get(
            "params",
            {"metric_type": "L2", "params": {"nprobe": 10}},
        )
        extra_fields = [f for f in (output_fields or []) if f != "id"]

        def _search() -> list[dict[str, Any]]:
            col = Collection(collection, using=self._alias)
            col.load()
            res = col.search(
                data=[query_vector],
                anns_field="embedding",
                param=params,
                limit=top_k,
                output_fields=["id", *extra_fields],
            )
            out: list[dict[str, Any]] = []
            for hits in res:
                for hit in hits:
                    row: dict[str, Any] = {
                        "id": hit.entity.get("id"),
                        "distance": float(hit.distance),
                    }
                    for field in extra_fields:
                        row[field] = hit.entity.get(field)
                    out.append(row)
            return out

        try:
            return await _run_sync(_search)
        except Exception as exc:
            logger.exception("Milvus 检索失败 collection={}: {}", collection, exc)
            raise

    async def delete(self, collection: str, ids: list[str]) -> None:
        """按主键删除向量。"""
        await self._ensure_connection()
        if not ids:
            return

        expr = "id in [" + ", ".join(f'"{i}"' for i in ids) + "]"

        def _delete() -> None:
            col = Collection(collection, using=self._alias)
            col.delete(expr)
            # 必须 flush，否则删除对后续检索不可见
            col.flush()

        try:
            await _run_sync(_delete)
        except Exception as exc:
            logger.exception("Milvus 删除失败 collection={}: {}", collection, exc)
            raise
