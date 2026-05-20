# -*- coding: utf-8 -*-
"""3.1：BM25 批量建索引必须保持结果正确，并把建索引耗时降下来。"""

from __future__ import annotations

import time

import pytest

from app.core.rag.retriever import MultiRetriever


def make_docs(n: int) -> dict[str, str]:
    return {
        f"d{i}": f"第{i}条：向量 索引 类型 检索 文档 召回" for i in range(n)
    }


@pytest.mark.asyncio
async def test_register_documents_keeps_keyword_search_working() -> None:
    retriever = MultiRetriever(None, None)
    retriever.register_keyword_documents(make_docs(50))

    results = await retriever.keyword_search("索引 类型", top_k=5)

    assert results
    assert all(r.id.startswith("d") for r in results)


def test_register_5000_docs_finishes_under_one_second() -> None:
    retriever = MultiRetriever(None, None)
    docs = make_docs(5_000)

    t0 = time.perf_counter()
    retriever.register_keyword_documents(docs)
    elapsed = time.perf_counter() - t0

    assert elapsed < 1.0, f"批量建索引耗时 {elapsed:.2f}s，超过 1s"
