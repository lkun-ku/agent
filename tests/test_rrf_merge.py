# -*- coding: utf-8 -*-
"""P2-3：RRF 合并时不能拿 L2 距离和 BM25 分数比大小。"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.rag.retriever import MultiRetriever


class FakeEmbedder:
    def embed_query(self, text: str) -> list[float]:
        return [0.1, 0.2]


class FakeHit:
    def __init__(self, doc_id: str, distance: float, text: str) -> None:
        self.id = doc_id
        self.distance = distance
        self.entity = {"id": doc_id, "text": text}


class FakeCollection:
    def __init__(self, hits: list[FakeHit]) -> None:
        self._hits = hits

    def search(self, **kwargs: Any):
        return [self._hits]


@pytest.mark.asyncio
async def test_same_id_prefers_vector_text_over_higher_bm25_score() -> None:
    collection = FakeCollection([FakeHit("d1", distance=0.2, text="VECTOR_TEXT")])
    retriever = MultiRetriever(collection, FakeEmbedder())
    retriever.register_keyword_documents({"d1": "索引类型"})

    results = await retriever.hybrid_search("索引类型", top_k=5)

    assert len(results) == 1
    assert results[0].id == "d1"
    assert results[0].content == "VECTOR_TEXT", "同 id 时应保留向量来源的原文"
    assert results[0].source == "hybrid"
