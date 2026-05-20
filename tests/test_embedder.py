# -*- coding: utf-8 -*-
"""P0-3：必须有可用的 Embedding 实现，且维度可断言。"""

from __future__ import annotations

import numpy as np
import pytest

from app.core.rag.retriever import EmbeddingProtocol
from app.infrastructure.embedding.st_embedder import SentenceTransformerEmbedder


class FakeModel:
    def __init__(self, dim: int) -> None:
        self.dim = dim

    def encode(self, texts, normalize_embeddings=True, convert_to_numpy=True):
        return np.ones((len(texts), self.dim), dtype=np.float32)


def make_embedder(dim: int = 512) -> SentenceTransformerEmbedder:
    embedder = SentenceTransformerEmbedder(model_name="fake-model", dim=dim)
    embedder._model = FakeModel(dim)  # 跳过模型下载，只测适配器行为
    return embedder


def test_implements_embedding_protocol() -> None:
    assert isinstance(make_embedder(512), EmbeddingProtocol)


def test_embed_query_returns_configured_dimension() -> None:
    vec = make_embedder(512).embed_query("向量检索")

    assert len(vec) == 512
    assert all(isinstance(x, float) for x in vec[:3])


def test_assert_dim_rejects_mismatch() -> None:
    embedder = make_embedder(512)
    embedder.assert_dim(512)

    with pytest.raises(ValueError, match="维度"):
        embedder.assert_dim(1024)


def test_embed_documents_detects_model_dimension_mismatch() -> None:
    embedder = make_embedder(512)
    embedder._model = FakeModel(3)

    with pytest.raises(ValueError, match="维度"):
        embedder.embed_documents(["a", "b"])
