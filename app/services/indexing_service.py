"""文档索引服务：分块 -> 嵌入 -> Milvus；并提供知识检索工具工厂。"""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from loguru import logger

from app.infrastructure.embedding.st_embedder import SentenceTransformerEmbedder
from app.infrastructure.vectordb.milvus_client import MilvusManager

if TYPE_CHECKING:
    from app.core.tools.builtin.knowledge import KnowledgeSearchTool

EMBED_DIM = 512


@lru_cache(maxsize=1)
def get_embedder() -> SentenceTransformerEmbedder:
    """进程级共享的嵌入器（模型延迟加载）。"""
    return SentenceTransformerEmbedder(dim=EMBED_DIM)


class DocumentIndexer:
    """把文档分块批量写入 Milvus，返回 vector_id 供 ORM 回填。"""

    def __init__(
        self,
        milvus: Any,
        embedder: Any,
        collection: str,
        batch_size: int = 64,
    ) -> None:
        self._milvus = milvus
        self._embedder = embedder
        self.collection_name = collection
        self._batch_size = max(1, batch_size)

    @property
    def embedder(self) -> Any:
        return self._embedder

    async def index(self, doc_id: str, chunks: list[str]) -> list[str]:
        if not chunks:
            return []
        ids: list[str] = []
        for start in range(0, len(chunks), self._batch_size):
            batch = chunks[start : start + self._batch_size]
            vectors = await asyncio.to_thread(self._embedder.embed_documents, batch)
            metas = [
                {"id": f"{doc_id}:{start + offset}", "text": text}
                for offset, text in enumerate(batch)
            ]
            await self._milvus.insert(self.collection_name, vectors, metas)
            ids.extend(meta["id"] for meta in metas)
        logger.info("文档 {} 写入向量库 {} 条", doc_id, len(ids))
        return ids


_indexer: DocumentIndexer | None = None
_index_lock = asyncio.Lock()


async def get_indexer() -> DocumentIndexer:
    global _indexer
    if _indexer is not None:
        return _indexer

    async with _index_lock:
        if _indexer is None:
            from app.config import get_settings

            settings = get_settings()
            milvus = MilvusManager()
            await milvus.create_collection(settings.milvus_collection_name, EMBED_DIM)
            _indexer = DocumentIndexer(
                milvus,
                get_embedder(),
                settings.milvus_collection_name,
            )
    return _indexer


async def build_knowledge_tool(llm: Any) -> KnowledgeSearchTool:
    """构建知识检索工具；集合或模型不可用时由调用方降级。"""
    from pymilvus import Collection

    from app.core.rag.generator import RAGGenerator
    from app.core.rag.retriever import MultiRetriever
    from app.core.tools.builtin.knowledge import KnowledgeSearchTool

    indexer = await get_indexer()
    collection = await asyncio.to_thread(Collection, indexer.collection_name)
    await asyncio.to_thread(collection.load)
    retriever = MultiRetriever(collection, indexer.embedder)
    return KnowledgeSearchTool(retriever, RAGGenerator(llm=llm))
