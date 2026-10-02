"""RAG 主链路：分块入库、语义检索与引用生成。

对外暴露进程级单例 :func:`get_pipeline`，供 ``/chat`` 与 ``/documents/upload`` 复用，
避免重复加载嵌入模型（首次加载约 10-20s）。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger

from app.config import get_settings
from app.core.rag.generator import RAGGenerator
from app.core.rag.retriever import _BM25Index
from app.core.rag.store import KnowledgeStore
from app.infrastructure.embeddings import get_embedder
from app.infrastructure.llm.adapter import RouterLLM
from app.infrastructure.llm.model_router import ModelConfig, ModelRouter
from app.infrastructure.vectordb.milvus_client import MilvusManager
from app.models.enums import RetrievalMode
from app.models.schemas import RAGResponse, RetrievalResult


class RAGPipeline:
    """组合「向量/关键词/混合检索 + （可选）重排 + 生成」能力。"""

    def __init__(
        self,
        store: KnowledgeStore,
        generator: RAGGenerator,
        reranker: Any | None = None,
        rerank_candidates: int = 12,
        *,
        retrieval_mode: RetrievalMode = RetrievalMode.VECTOR,
        keyword_provider: Callable[[], Awaitable[dict[str, str]]] | None = None,
    ) -> None:
        self._store = store
        self._generator = generator
        self._reranker = reranker
        self._rerank_candidates = rerank_candidates
        self._retrieval_mode = retrieval_mode
        self._keyword_provider = keyword_provider
        self._keyword_index = _BM25Index()
        self._keyword_text: dict[str, str] = {}
        self._keyword_loaded = False
        self._keyword_lock = asyncio.Lock()

    async def index_document(
        self,
        doc_id: str,
        filename: str,
        chunks: list[str],
        chunk_ids: list[str],
    ) -> int:
        """把文档分块写入向量库，返回成功条数。"""
        rows = [
            {
                "id": chunk_id,
                "text": text[:8000],
                "doc_id": doc_id,
                "filename": filename,
                "chunk_index": index,
            }
            for index, (chunk_id, text) in enumerate(zip(chunk_ids, chunks, strict=True))
        ]
        return await self._store.add_chunks(rows)

    async def delete_chunks(self, ids: list[str]) -> int:
        """按主键删除向量。"""
        return await self._store.delete_chunks(ids)

    async def retrieve(
        self,
        query: str,
        top_k: int = 4,
        max_distance: float | None = None,
    ) -> list[RetrievalResult]:
        """按语义检索相关分块；距离超过阈值的结果视为未命中。

        启用重排时先扩大召回再精排，提高相关性；hybrid 模式融合向量与 BM25。
        """
        if top_k < 1:
            raise ValueError("top_k 必须大于 0")
        limit = get_settings().rag_max_distance if max_distance is None else max_distance
        if limit < 0:
            raise ValueError("max_distance 不能为负数")
        candidates = self._rerank_candidates if self._reranker is not None else top_k

        vector_results: list[RetrievalResult] = []
        if self._retrieval_mode is not RetrievalMode.KEYWORD:
            results = await self._store.search(query, top_k=candidates)
            if results:
                logger.info(
                    "RAG 向量检索 top1距离={:.4f} top2距离={} 阈值={} 候选数={}",
                    results[0].score,
                    f"{results[1].score:.4f}" if len(results) > 1 else "-",
                    limit,
                    len(results),
                )
            else:
                logger.info("RAG 向量检索无候选（向量库可能为空）")
            vector_results = [item for item in results if item.score <= limit]

        keyword_results: list[RetrievalResult] = []
        if self._retrieval_mode is not RetrievalMode.VECTOR:
            keyword_results = await self._keyword_search(query, top_k=candidates)

        if self._retrieval_mode is RetrievalMode.KEYWORD:
            combined = keyword_results
        elif self._retrieval_mode is RetrievalMode.HYBRID:
            combined = self._fuse([vector_results, keyword_results], top_k=candidates)
        else:
            combined = vector_results

        if self._reranker is not None and len(combined) > 1:
            combined = await self._reranker.rerank(query, combined, top_k=top_k)
        return combined[:top_k]

    async def _keyword_search(
        self,
        query: str,
        top_k: int,
    ) -> list[RetrievalResult]:
        """从 PostgreSQL 分块构建 BM25 索引并执行关键词检索。"""
        if self._keyword_provider is None:
            return []
        try:
            async with self._keyword_lock:
                if not self._keyword_loaded:
                    documents = await self._keyword_provider()
                    self._keyword_index.clear()
                    self._keyword_text.clear()
                    for doc_id, text in documents.items():
                        self._keyword_index.add_document(doc_id, text)
                        self._keyword_text[doc_id] = text
                    self._keyword_loaded = True
                    logger.info("RAG BM25 索引已加载 documents={}", len(documents))

            ranked = self._keyword_index.search(query, top_k=top_k)
            return [
                RetrievalResult(
                    id=doc_id,
                    content=self._keyword_text.get(doc_id, ""),
                    score=float(score),
                    metadata={"rank": rank},
                    source="keyword",
                )
                for rank, (doc_id, score) in enumerate(ranked)
            ]
        except Exception as exc:  # noqa: BLE001
            logger.warning("RAG 关键词检索失败，忽略该路结果: {}", exc)
            return []

    @staticmethod
    def _fuse(
        result_lists: list[list[RetrievalResult]],
        *,
        top_k: int,
        k: int = 60,
    ) -> list[RetrievalResult]:
        """按 RRF 融合多路检索结果。"""
        scores: dict[str, float] = {}
        best_by_id: dict[str, RetrievalResult] = {}
        for results in result_lists:
            for rank, item in enumerate(results):
                score = scores.get(item.id, 0.0) + 1.0 / (k + rank + 1)
                scores[item.id] = score
                if item.id not in best_by_id or item.score > best_by_id[item.id].score:
                    best_by_id[item.id] = item

        merged: list[RetrievalResult] = []
        for item_id in sorted(scores, key=lambda key: scores[key], reverse=True)[:top_k]:
            base = best_by_id[item_id].model_copy(deep=True)
            base.score = scores[item_id]
            base.metadata = {**base.metadata, "rrf": scores[item_id]}
            base.source = "hybrid"
            merged.append(base)
        return merged

    async def answer(
        self,
        query: str,
        chat_history: list[Any],
        contexts: list[RetrievalResult],
    ) -> RAGResponse:
        """基于检索上下文生成带引用的回答。"""
        enriched = [
            ctx.model_copy(
                update={
                    "content": (
                        f"[{ctx.metadata.get('filename') or 'doc'}"
                        f"#{ctx.metadata.get('chunk_index')}] {ctx.content}"
                    )
                }
            )
            for ctx in contexts
        ]
        return await self._generator.generate(query, enriched, chat_history)


def build_pipeline() -> RAGPipeline:
    """按当前配置构建 RAG 管线（会加载嵌入模型，属阻塞操作）。"""
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("未配置 OPENAI_API_KEY，无法启用 RAG")

    embedder = get_embedder(settings.embedding_model, settings.embedding_local_only)

    conn_kwargs: dict[str, Any] = {}
    if settings.milvus_user:
        conn_kwargs["user"] = settings.milvus_user
    if settings.milvus_password:
        conn_kwargs["password"] = settings.milvus_password

    manager = MilvusManager(
        host=settings.milvus_host,
        port=str(settings.milvus_port),
        alias="rag",
        **conn_kwargs,
    )
    store = KnowledgeStore(
        manager=manager,
        embedder=embedder,
        collection=settings.rag_collection_name,
        dimension=embedder.dimension,
    )
    router = ModelRouter(
        [
            ModelConfig(
                model_id=settings.openai_model,
                api_key=settings.openai_api_key,
                base_url=settings.openai_api_base or None,
                thinking=settings.openai_thinking,
            )
        ],
        max_retries=settings.llm_max_retries,
        retry_base_delay=settings.llm_retry_base_delay,
        retry_max_delay=settings.llm_retry_max_delay,
    )
    generator = RAGGenerator(RouterLLM(router), model_name=settings.openai_model)

    reranker = None
    if settings.reranker_model:
        from app.core.rag.reranker import Reranker

        reranker = Reranker(model_name=settings.reranker_model)
        logger.info("已启用重排模型 {}", settings.reranker_model)

    async def _load_keyword_documents() -> dict[str, str]:
        from sqlalchemy import select

        from app.infrastructure.database import session as database_session
        from app.infrastructure.database.models import DocumentChunk

        factory = database_session.async_session_factory
        if factory is None:
            return {}
        async with factory() as session:
            rows = await session.execute(select(DocumentChunk.id, DocumentChunk.content))
            return {str(row_id): str(content) for row_id, content in rows.all()}

    try:
        retrieval_mode = RetrievalMode(settings.rag_retrieval_mode)
    except ValueError:
        logger.warning("未知检索模式 {}，回退为 vector", settings.rag_retrieval_mode)
        retrieval_mode = RetrievalMode.VECTOR

    logger.info(
        "RAG 管线已构建 embedding={} collection={} dim={} rerank={} retrieval_mode={}",
        settings.embedding_model,
        settings.rag_collection_name,
        embedder.dimension,
        reranker is not None,
        retrieval_mode.value,
    )
    return RAGPipeline(
        store,
        generator,
        reranker=reranker,
        rerank_candidates=settings.rag_rerank_candidates,
        retrieval_mode=retrieval_mode,
        keyword_provider=_load_keyword_documents,
    )


_pipeline: RAGPipeline | None = None
_pipeline_lock = asyncio.Lock()


async def get_pipeline() -> RAGPipeline | None:
    """获取进程级 RAG 管线；未启用时返回 ``None``。"""
    global _pipeline
    settings = get_settings()
    if not settings.rag_enabled:
        return None
    if _pipeline is not None:
        return _pipeline
    async with _pipeline_lock:
        if _pipeline is None:
            _pipeline = await asyncio.to_thread(build_pipeline)
    return _pipeline
