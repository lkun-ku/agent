"""文本嵌入：本地 sentence-transformers 中文向量模型。

默认使用 ``BAAI/bge-small-zh-v1.5``（512 维），配合 ``local_only=True`` 可完全离线
运行（需事先把模型放入 HuggingFace 缓存或用本地路径）。
"""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Any

from loguru import logger


class SentenceTransformerEmbedder:
    """把 SentenceTransformer 适配成 ``embed_query`` / ``embed_documents`` 接口。"""

    def __init__(
        self,
        model_name: str,
        *,
        device: str | None = None,
        local_only: bool = True,
    ) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self._model: Any = SentenceTransformer(
            model_name,
            device=device,
            local_files_only=local_only,
        )
        # 兼容 sentence-transformers 新旧 API（旧方法名已废弃）
        get_dim = getattr(self._model, "get_embedding_dimension", None)
        if get_dim is None:
            get_dim = self._model.get_sentence_embedding_dimension
        dimension = get_dim()
        if dimension is None:
            raise RuntimeError(f"无法获取嵌入维度: {model_name}")
        self.dimension = int(dimension)
        logger.info("嵌入模型已加载 model={} dim={}", model_name, self.dimension)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量编码（L2 归一化，便于内积/余弦检索）。"""
        if not texts:
            return []
        vectors = self._model.encode(
            texts,
            normalize_embeddings=True,
            batch_size=16,
            show_progress_bar=False,
        )
        return [[float(x) for x in vec] for vec in vectors]

    def embed_query(self, text: str) -> list[float]:
        """单条查询编码。"""
        vectors = self.embed_documents([text])
        return vectors[0] if vectors else []

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self.embed_documents, texts)

    async def aembed_query(self, text: str) -> list[float]:
        return await asyncio.to_thread(self.embed_query, text)


@lru_cache(maxsize=2)
def get_embedder(model_name: str, local_only: bool = True) -> SentenceTransformerEmbedder:
    """进程级单例：模型加载较慢（首次约 10-20s），避免重复初始化。"""
    return SentenceTransformerEmbedder(model_name, local_only=local_only)
