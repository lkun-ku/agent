"""知识库向量存储：文档分块入库与相似度检索（Milvus）。"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from loguru import logger

from app.models.schemas import RetrievalResult

if TYPE_CHECKING:
    from app.infrastructure.embeddings import SentenceTransformerEmbedder
    from app.infrastructure.vectordb.milvus_client import MilvusManager


class KnowledgeStore:
    """把文档分块写入 Milvus，并按语义检索。"""

    def __init__(
        self,
        manager: MilvusManager,
        embedder: SentenceTransformerEmbedder,
        collection: str,
        dimension: int,
    ) -> None:
        self._manager = manager
        self._embedder = embedder
        self._collection = collection
        self._dimension = dimension
        self._ready = False
        self._lock = asyncio.Lock()

    async def ensure_collection(self) -> None:
        """懒创建集合（含 text / doc_id / filename / chunk_index 字段）。

        每次都校验集合真实存在：外部删除集合（如 ``--clean`` 重置）后可自愈，
        不需要重启服务。
        """
        if await self._is_ready():
            return
        async with self._lock:
            if await self._is_ready():
                return
            from pymilvus import DataType, FieldSchema

            await self._manager.create_collection(
                self._collection,
                self._dimension,
                extra_fields=[
                    FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=8192),
                    FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=64),
                    FieldSchema(name="filename", dtype=DataType.VARCHAR, max_length=512),
                    FieldSchema(name="chunk_index", dtype=DataType.INT32),
                ],
            )
            self._ready = True
            logger.info("知识库集合就绪 collection={} dim={}", self._collection, self._dimension)

    async def _is_ready(self) -> bool:
        if not self._ready:
            return False
        try:
            return await self._manager.collection_exists(self._collection)
        except Exception as exc:  # noqa: BLE001
            logger.warning("校验集合存在性失败，按未就绪处理: {}", exc)
            return False

    async def add_chunks(self, rows: list[dict[str, Any]]) -> int:
        """写入分块。``rows`` 需包含 id / text / doc_id / filename / chunk_index。"""
        if not rows:
            return 0
        await self.ensure_collection()
        vectors = await self._embedder.aembed_documents([str(r["text"]) for r in rows])
        metadata = [
            {
                "id": str(r["id"]),
                "text": str(r["text"]),
                "doc_id": str(r.get("doc_id") or ""),
                "filename": str(r.get("filename") or "")[:512],
                "chunk_index": int(r.get("chunk_index") or 0),
            }
            for r in rows
        ]
        # 幂等写入：同一 chunk_id 先删后插，避免重复入库产生冗余向量
        ids = [str(m["id"]) for m in metadata]
        try:
            await self._manager.delete(self._collection, ids)
        except Exception as exc:  # noqa: BLE001
            logger.warning("按主键预删失败（忽略，不影响写入）: {}", exc)
        await self._manager.insert(self._collection, vectors, metadata)
        logger.info("已写入向量 collection={} count={}", self._collection, len(rows))
        return len(rows)

    async def delete_chunks(self, ids: list[str]) -> int:
        """按主键删除向量（文档更新/清理时使用）。"""
        if not ids:
            return 0
        await self.ensure_collection()
        await self._manager.delete(self._collection, ids)
        logger.info("已删除向量 collection={} count={}", self._collection, len(ids))
        return len(ids)

    async def search(self, query: str, top_k: int = 4) -> list[RetrievalResult]:
        """按语义检索相关分块。"""
        if not query.strip():
            return []
        if top_k < 1:
            raise ValueError("top_k 必须大于 0")
        await self.ensure_collection()
        vector = await self._embedder.aembed_query(query)
        if not vector:
            return []
        hits = await self._manager.search(
            self._collection,
            vector,
            top_k=top_k,
            output_fields=["text", "doc_id", "filename", "chunk_index"],
        )
        results: list[RetrievalResult] = []
        for hit in hits:
            text = str(hit.get("text") or "")
            if not text:
                continue
            results.append(
                RetrievalResult(
                    id=str(hit.get("id") or ""),
                    content=text,
                    score=float(hit.get("distance") or 0.0),
                    metadata={
                        "doc_id": hit.get("doc_id"),
                        "filename": hit.get("filename"),
                        "chunk_index": hit.get("chunk_index"),
                    },
                    source="vector",
                )
            )
        return results
