# -*- coding: utf-8 -*-
"""P1-3：中文 BM25 必须能召回，而不是把整串汉字当成一个 token。"""

from __future__ import annotations

import pytest

from app.core.rag.retriever import MultiRetriever


@pytest.fixture()
def retriever() -> MultiRetriever:
    # keyword_search 不依赖 Milvus / 嵌入模型，可传 None
    r = MultiRetriever(milvus_client=None, embedding_model=None)
    r.register_keyword_documents(
        {
            "d1": "Milvus 支持多种索引类型，包括倒排文件索引和分层可导航小世界图。",
            "d2": "向量检索需要权衡召回率、延迟与内存占用。",
        }
    )
    return r


@pytest.mark.asyncio
async def test_chinese_query_hits_expected_document(retriever: MultiRetriever) -> None:
    results = await retriever.keyword_search("索引类型", top_k=5)

    assert results, "中文查询不应返回空列表"
    assert results[0].id == "d1"


@pytest.mark.asyncio
async def test_partial_chinese_terms_still_match(retriever: MultiRetriever) -> None:
    results = await retriever.keyword_search("召回率 延迟", top_k=5)

    assert results
    assert results[0].id == "d2"
