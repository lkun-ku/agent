"""多路检索：向量（Milvus）、BM25 关键词、混合 + RRF 融合。"""

from __future__ import annotations

import asyncio
from typing import Any, Protocol, runtime_checkable

from loguru import logger

from app.core.rag.search import BM25Index, rrf_fuse, tokenize
from app.models.enums import RetrievalMode
from app.models.schemas import RetrievalResult


@runtime_checkable
class EmbeddingProtocol(Protocol):
    """与 LangChain Embeddings 兼容的嵌入接口。"""

    def embed_query(self, text: str) -> list[float]:
        ...


@runtime_checkable
class MilvusSearchable(Protocol):
    """支持向量检索的 Milvus Collection 或兼容封装。"""

    def search(
        self,
        data: list[list[float]],
        anns_field: str,
        param: dict[str, Any],
        limit: int,
        output_fields: list[str] | None = None,
        **kwargs: Any,
    ) -> Any:
        ...


# 兼容旧内部引用；新代码统一使用公共检索内核。
_tokenize = tokenize
_BM25Index = BM25Index


class MultiRetriever:
    """多路检索引擎：支持向量检索 + BM25 关键词检索 + 混合检索（RRF）。"""

    # Milvus 常见字段名，若集合不同可通过类属性或实例赋值覆盖（与 Schema 一致）
    anns_field: str = "embedding"
    text_field: str = "text"
    id_field: str = "id"

    # 向量检索参数
    metric_param: dict[str, Any] = {"metric_type": "L2", "params": {"nprobe": 16}}

    def __init__(self, milvus_client: Any, embedding_model: Any) -> None:
        """
        :param milvus_client: pymilvus Collection 或实现 ``search`` 的兼容对象
        :param embedding_model: 含 ``embed_query(str) -> list[float]`` 的嵌入模型
        """
        self._milvus = milvus_client
        self._embed = embedding_model
        self._bm25 = _BM25Index()
        # doc_id -> 全文，用于 BM25 结果组装
        self._id_to_text: dict[str, str] = {}
        self._rrf_k: int = 60

    def register_keyword_documents(self, id_to_text: dict[str, str]) -> None:
        """
        注册用于 BM25 的文档（通常与向量库中的分块 ID 一致）。

        :param id_to_text: 文档 ID 到文本的映射
        """
        self._bm25.clear()
        self._id_to_text.clear()
        for did, text in id_to_text.items():
            self._bm25.add_document(did, text)
            self._id_to_text[did] = text
        logger.info("BM25 索引已更新，文档数: {}", len(id_to_text))

    async def retrieve(
        self, query: str, top_k: int = 10, mode: str = "hybrid"
    ) -> list[RetrievalResult]:
        """执行检索。"""
        mode_norm = mode.lower().strip()
        try:
            rm = RetrievalMode(mode_norm)
        except ValueError:
            logger.warning("未知检索模式 {}，回退为 hybrid", mode)
            rm = RetrievalMode.HYBRID

        if rm == RetrievalMode.VECTOR:
            return await self.vector_search(query, top_k)
        if rm == RetrievalMode.KEYWORD:
            return await self.keyword_search(query, top_k)
        return await self.hybrid_search(query, top_k)

    async def vector_search(self, query: str, top_k: int) -> list[RetrievalResult]:
        """向量语义检索。"""
        if not isinstance(self._embed, EmbeddingProtocol):
            raise TypeError("embedding_model 需实现 embed_query 方法")

        def _sync_embed() -> list[float]:
            return list(self._embed.embed_query(query))

        try:
            vector = await asyncio.to_thread(_sync_embed)
        except Exception as e:
            logger.exception("向量编码失败: {}", e)
            raise RuntimeError(f"向量编码失败: {e}") from e

        if not vector:
            raise RuntimeError("嵌入向量为空")

        def _sync_search() -> list[RetrievalResult]:
            return self._search_milvus(vector, top_k)

        try:
            return await asyncio.to_thread(_sync_search)
        except Exception as e:
            logger.exception("Milvus 向量检索失败: {}", e)
            raise RuntimeError(f"向量检索失败: {e}") from e

    def _search_milvus(self, vector: list[float], top_k: int) -> list[RetrievalResult]:
        """同步 Milvus 查询并封装为 RetrievalResult。"""
        coll = self._milvus
        if not isinstance(coll, MilvusSearchable):
            raise TypeError("milvus_client 需实现 search 方法")

        output_fields = [self.text_field, self.id_field]
        # 部分集合主键字段名为 id，自动兼容
        raw = coll.search(
            data=[vector],
            anns_field=self.anns_field,
            param=self.metric_param,
            limit=top_k,
            output_fields=output_fields,
        )
        results: list[RetrievalResult] = []
        hits = raw[0] if raw else []
        for rank, hit in enumerate(hits):
            entity = getattr(hit, "entity", None) or {}
            if hasattr(hit, "entity"):
                try:
                    entity = hit.entity.to_dict()
                except Exception:
                    entity = getattr(hit, "entity", {})
            # 距离 / 分数：distance 越小越好（L2）；IP 越大越好
            score = float(getattr(hit, "distance", 0.0) or 0.0)
            # 统一为「越大越好」：对 L2 做简单反转（仅用于展示）
            text = entity.get(self.text_field) or entity.get("text") or ""
            rid = str(entity.get(self.id_field) or entity.get("id") or hit.id)
            results.append(
                RetrievalResult(
                    id=rid,
                    content=str(text),
                    score=score,
                    metadata={"rank": rank},
                    source="vector",
                )
            )
        return results

    async def keyword_search(self, query: str, top_k: int) -> list[RetrievalResult]:
        """BM25 关键词检索（需先 register_keyword_documents）。"""
        def _run() -> list[RetrievalResult]:
            ranked = self._bm25.search(query, top_k)
            out: list[RetrievalResult] = []
            for doc_id, sc in ranked:
                text = self._id_to_text.get(doc_id, "")
                out.append(
                    RetrievalResult(
                        id=doc_id,
                        content=text,
                        score=float(sc),
                        metadata={},
                        source="keyword",
                    )
                )
            return out

        try:
            return await asyncio.to_thread(_run)
        except Exception as e:
            logger.exception("BM25 检索失败: {}", e)
            raise RuntimeError(f"BM25 检索失败: {e}") from e

    def _rrf_fuse(
        self,
        lists: list[list[RetrievalResult]],
        top_k: int,
    ) -> list[RetrievalResult]:
        """倒数排名融合（RRF），按 id 合并多路结果。"""
        return rrf_fuse(lists, top_k=top_k, k=self._rrf_k)

    async def hybrid_search(self, query: str, top_k: int) -> list[RetrievalResult]:
        """混合检索：并行向量 + BM25，RRF 融合。"""
        vec_task = self.vector_search(query, top_k)
        kw_task = self.keyword_search(query, top_k)
        vec_res, kw_res = await asyncio.gather(vec_task, kw_task, return_exceptions=True)

        lists: list[list[RetrievalResult]] = []
        if isinstance(vec_res, list):
            lists.append(vec_res)
        else:
            logger.error("向量检索分支失败: {}", vec_res)
        if isinstance(kw_res, list) and kw_res:
            lists.append(kw_res)
        elif isinstance(kw_res, Exception):
            logger.error("关键词检索分支失败: {}", kw_res)

        if not lists:
            raise RuntimeError("混合检索两路均失败或无结果")
        if len(lists) == 1:
            return lists[0][:top_k]
        return self._rrf_fuse(lists, top_k)
