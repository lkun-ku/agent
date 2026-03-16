"""SentenceTransformer 嵌入适配器：实现 core 层的 EmbeddingProtocol。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


class SentenceTransformerEmbedder:
    """把 sentence-transformers 的编码能力适配成 embed_query / embed_documents。"""

    def __init__(
        self,
        model_name: str = "BAAI/bge-small-zh-v1.5",
        dim: int = 512,
        device: str | None = None,
    ) -> None:
        self._model_name = model_name
        self._dim = dim
        self._device = device
        self._model: Any = None

    @property
    def dim(self) -> int:
        return self._dim

    def _load(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            kwargs: dict[str, Any] = {}
            if self._device:
                kwargs["device"] = self._device
            self._model = SentenceTransformer(self._model_name, **kwargs)
        return self._model

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """批量编码；返回维度与构造参数不一致时立即失败，避免写入错误维度的向量。"""
        model = self._load()
        vectors = model.encode(
            list(texts),
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        out = [v.tolist() for v in vectors]
        if out and len(out[0]) != self._dim:
            raise ValueError(
                f"嵌入维度 {len(out[0])} 与期望维度 {self._dim} 不一致，"
                "请检查模型与 Milvus 集合定义"
            )
        return out

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    def assert_dim(self, expected: int) -> None:
        """启动期断言集合维度与模型维度一致。"""
        if expected != self._dim:
            raise ValueError(f"集合维度 {expected} 与嵌入维度 {self._dim} 不一致")
