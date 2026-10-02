"""意图识别的语义兜底分类器。

规则引擎擅长处理“我要退款”“退款政策是什么”这类强特征 query；当关键词完全
未命中时，使用本地嵌入模型做最近邻分类。该组件只输出意图与置信度，不执行业务动作。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

from loguru import logger


@dataclass(frozen=True)
class SemanticMatch:
    """语义分类结果。"""

    intent: str
    sub_intent: str
    confidence: float
    similarity: float
    rationale: str


IntentLabel = tuple[str, str]


class IntentEmbedder(Protocol):
    """语义分类器所需的最小嵌入接口。"""

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def aembed_query(self, text: str) -> list[float]: ...

# 每个意图保留少量高代表性语句；后续可迁移到 YAML/数据库并接入人工标注流程。
_SEMANTIC_EXAMPLES: dict[IntentLabel, tuple[str, ...]] = {
    ("问答", "知识问答"): (
        "这个报错是什么意思",
        "为什么这里需要设置主键",
        "帮我解释一下这段代码",
        "向量数据库的作用是什么",
        "列表和元组有什么区别",
    ),
    ("问答", "政策咨询"): (
        "退货政策是什么",
        "退款规则有哪些",
        "退货流程怎么走",
        "多久能收到退款",
        "哪些商品不支持退货",
        "退款条件是什么",
    ),
    ("问答", "闲聊"): (
        "你好",
        "谢谢你的帮助",
        "再见",
        "和我聊聊天",
    ),
    ("任务", "搜索"): (
        "帮我找一下 Python 列表资料",
        "搜索最新的退款政策",
        "帮我查一下这个报错",
        "在文档里找函数定义",
    ),
    ("任务", "计算"): (
        "帮我计算 12 乘以 8",
        "三加五等于多少",
        "算一下订单总金额",
        "把 128 除以 4",
    ),
    ("任务", "数据库"): (
        "查询订单表里的待退款记录",
        "写一个 SQL 统计昨天订单数",
        "数据库里有多少用户",
        "帮我查用户表的字段",
    ),
    ("售后", "退款"): (
        "我要退款",
        "帮我申请退货退款",
        "申请仅退款",
        "这笔订单需要退款处理",
        "退掉昨天买的商品",
        "把这笔钱退回来",
    ),
    ("文档", "上传"): (
        "上传这份 PDF",
        "把文档加入知识库",
        "我要上传一个 Markdown 文件",
        "导入这份资料",
    ),
    ("文档", "总结"): (
        "总结这份文档",
        "概括一下这篇资料",
        "帮我生成文档摘要",
        "总结一下这个 PDF 的重点",
    ),
}

# BGE 归一化向量的常见余弦区间：低于 0.65 通常跨意图噪声较大。
_SEMANTIC_SIMILARITY_FLOOR = 0.45
_SEMANTIC_SIMILARITY_CEILING = 0.80


def _similarity_to_confidence(similarity: float) -> float:
    """把余弦相似度映射到 0~1 的意图置信度。"""
    mapped = (similarity - _SEMANTIC_SIMILARITY_FLOOR) / (
        _SEMANTIC_SIMILARITY_CEILING - _SEMANTIC_SIMILARITY_FLOOR
    )
    return round(min(0.95, max(0.0, mapped)), 4)


class SemanticIntentClassifier:
    """基于本地嵌入模型的最近邻意图分类器；只在规则置信度不足时使用。"""

    def __init__(
        self,
        *,
        enabled: bool = True,
        min_similarity: float = 0.65,
        embedder: IntentEmbedder | None = None,
    ) -> None:
        self._enabled = enabled
        self._min_similarity = min_similarity
        self._embedder = embedder
        self._labels: list[IntentLabel] = []
        self._vectors: list[list[float]] = []
        self._ready = False
        self._lock = asyncio.Lock()

    async def classify(self, query: str) -> SemanticMatch | None:
        """返回语义最相近的意图；相似度不足或模型不可用时返回 None。"""
        if not self._enabled or not query.strip():
            return None
        await self._ensure_ready()
        embedder = self._embedder
        if embedder is None:
            raise RuntimeError("语义意图嵌入器未初始化")

        query_vector = await embedder.aembed_query(query)
        if not query_vector:
            return None

        label_scores: dict[IntentLabel, float] = {}
        for label, vector in zip(self._labels, self._vectors, strict=True):
            similarity = _dot_product(query_vector, vector)
            if label not in label_scores or similarity > label_scores[label]:
                label_scores[label] = similarity

        if not label_scores:
            return None

        best_label, best_similarity = max(
            label_scores.items(), key=lambda item: item[1]
        )
        if best_similarity < self._min_similarity:
            return None

        return SemanticMatch(
            intent=best_label[0],
            sub_intent=best_label[1],
            confidence=_similarity_to_confidence(best_similarity),
            similarity=round(best_similarity, 4),
            rationale=(
                f"语义近邻命中 {best_label[0]}/{best_label[1]}，"
                f"cosine={best_similarity:.4f}"
            ),
        )

    async def _ensure_ready(self) -> None:
        """懒加载示例向量与嵌入模型；进程内只初始化一次。"""
        if self._ready:
            return
        async with self._lock:
            if self._ready:
                return

            if self._embedder is None:
                from app.config import get_settings
                from app.infrastructure.embeddings import get_embedder

                settings = get_settings()
                self._embedder = get_embedder(
                    settings.embedding_model,
                    settings.embedding_local_only,
                )

            texts = [
                text
                for examples in _SEMANTIC_EXAMPLES.values()
                for text in examples
            ]
            vectors = await self._embedder.aembed_documents(texts)
            if len(vectors) != len(texts):
                raise RuntimeError("语义意图示例向量化数量不一致")

            self._labels = [
                label
                for label, examples in _SEMANTIC_EXAMPLES.items()
                for _ in examples
            ]
            self._vectors = vectors
            self._ready = True
            logger.info("意图语义分类器已就绪 examples={}", len(texts))


def _dot_product(left: list[float], right: list[float]) -> float:
    """计算归一化向量的内积；维度不一致视为不可比。"""
    if len(left) != len(right):
        return 0.0
    return sum(float(a) * float(b) for a, b in zip(left, right, strict=True))
