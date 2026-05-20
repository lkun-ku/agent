# -*- coding: utf-8 -*-
"""上传向量入库：分批嵌入、写入 text，并返回可回填的 vector_id。"""

from __future__ import annotations

from typing import Any

import pytest

from app.services.indexing_service import DocumentIndexer


class FakeMilvus:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[list[float]], list[dict[str, Any]]]] = []

    async def insert(
        self,
        collection: str,
        vectors: list[list[float]],
        metadata: list[dict[str, Any]],
    ) -> list[str]:
        self.calls.append((collection, vectors, metadata))
        return [m["id"] for m in metadata]


class FakeEmbedder:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2] for _ in texts]


@pytest.mark.asyncio
async def test_index_batches_chunks_and_returns_ids() -> None:
    milvus = FakeMilvus()
    indexer = DocumentIndexer(milvus, FakeEmbedder(), "kb", batch_size=2)

    ids = await indexer.index("doc-1", ["a", "b", "c", "d", "e"])

    assert ids == ["doc-1:0", "doc-1:1", "doc-1:2", "doc-1:3", "doc-1:4"]
    assert len(milvus.calls) == 3
    assert milvus.calls[0][0] == "kb"
    assert milvus.calls[0][2][0] == {"id": "doc-1:0", "text": "a"}
    assert len(milvus.calls[2][1]) == 1


@pytest.mark.asyncio
async def test_index_empty_chunks_is_noop() -> None:
    milvus = FakeMilvus()
    indexer = DocumentIndexer(milvus, FakeEmbedder(), "kb")

    assert await indexer.index("doc-1", []) == []
    assert milvus.calls == []
