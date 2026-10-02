"""Cross-Encoder 重排序模块。"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from app.models.schemas import RetrievalResult


class Reranker:
    """重排序器：使用 Cross-Encoder 对检索结果重新排序。"""

    # 默认模型：需在 transformers 5.x 下可加载（提供 safetensors 权重，且中文效果更好）
    DEFAULT_MODEL = "BAAI/bge-reranker-base"

    def __init__(
        self,
        model_name: str | None = None,
        device: str | None = None,
        *,
        strict: bool = False,
    ) -> None:
        """
        :param model_name: sentence-transformers CrossEncoder 模型名或路径，默认
            :attr:`DEFAULT_MODEL`；``ms-marco-MiniLM-L-6-v2`` 仅提供 ``pytorch_model.bin``，
            在 transformers 5.x 下无法加载
        :param device: 如 cuda / cpu / mps，None 表示由库自动选择
        :param strict: 为 True 时模型加载/推理失败直接抛错；默认 False 则降级为原始顺序
        """
        self._model_name = model_name or self.DEFAULT_MODEL
        self._device = device
        self._strict = strict
        self._model: Any = None

    def _load_model(self) -> Any:
        """懒加载 CrossEncoder。"""
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as e:
            raise RuntimeError("请安装 sentence-transformers 以使用 Reranker") from e
        kwargs: dict[str, Any] = {}
        if self._device:
            kwargs["device"] = self._device
        self._model = CrossEncoder(self._model_name, **kwargs)
        return self._model

    async def rerank(
        self,
        query: str,
        documents: list[RetrievalResult],
        top_k: int = 5,
    ) -> list[RetrievalResult]:
        """对文档列表按与 query 相关性重排，返回 top_k。"""
        if not documents:
            return []
        if top_k <= 0:
            return []

        def _sync_predict() -> list[float]:
            model = self._load_model()
            pairs = [(query, d.content) for d in documents]
            raw = model.predict(pairs)
            if hasattr(raw, "tolist"):
                return list(raw.tolist())
            return list(raw)

        try:
            scores = await asyncio.to_thread(_sync_predict)
        except Exception as e:
            logger.exception("CrossEncoder 推理失败: {}", e)
            if self._strict:
                raise RuntimeError(f"重排序失败: {e}") from e
            # 降级：不做重排，保留原顺序，避免整条 RAG 链路不可用
            logger.warning("重排不可用（{}），已回退为原始检索顺序", self._model_name)
            return [d.model_copy(deep=True) for d in documents[:top_k]]

        if len(scores) != len(documents):
            raise RuntimeError("重排序分数数量与文档数量不一致")

        ranked = sorted(
            zip(documents, scores, strict=True),
            key=lambda x: float(x[1]),
            reverse=True,
        )
        out: list[RetrievalResult] = []
        for doc, sc in ranked[:top_k]:
            new_doc = doc.model_copy(deep=True)
            new_doc.score = float(sc)
            new_doc.metadata = {**new_doc.metadata, "rerank_score": float(sc)}
            out.append(new_doc)
        return out
