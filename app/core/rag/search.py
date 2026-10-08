"""检索内核：中文友好 BM25 与 RRF 融合。

该模块不依赖数据库、向量库和 LLM，供多路检索器与 RAG Pipeline 复用。
"""

from __future__ import annotations

import math
import re
from collections import defaultdict

from app.models.schemas import RetrievalResult

_WORD_PATTERN = re.compile(r"[A-Za-z0-9_]+")
_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]+")


def tokenize(text: str) -> list[str]:
    """中英文分词：英文/数字按词切分，中文按二元组（bigram）切分。

    不能按 ``[\\w\\u4e00-\\u9fff]+`` 整体切分，否则整句中文会被当成单一 token，
    查询与文档永远无法命中，导致 BM25 对中文失效。
    """
    tokens: list[str] = [token.lower() for token in _WORD_PATTERN.findall(text)]
    for segment in _CJK_PATTERN.findall(text):
        if len(segment) == 1:
            tokens.append(segment)
            continue
        tokens.extend(segment[index : index + 2] for index in range(len(segment) - 1))
    return tokens


class BM25Index:
    """内存 BM25（Okapi）索引，用于关键词检索。"""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._doc_ids: list[str] = []
        self._doc_freqs: list[dict[str, int]] = []
        self._doc_lens: list[int] = []
        self._avgdl: float = 0.0
        self._df: defaultdict[str, int] = defaultdict(int)
        self._N: int = 0
        self._idf: dict[str, float] = {}

    def clear(self) -> None:
        """清空索引。"""
        self._doc_ids.clear()
        self._doc_freqs.clear()
        self._doc_lens.clear()
        self._avgdl = 0.0
        self._df.clear()
        self._N = 0
        self._idf.clear()

    def add_document(self, doc_id: str, text: str) -> None:
        """添加文档并更新统计量。"""
        tokens = tokenize(text)
        term_freq: defaultdict[str, int] = defaultdict(int)
        for token in tokens:
            term_freq[token] += 1
        for token in term_freq:
            self._df[token] += 1

        self._doc_ids.append(doc_id)
        self._doc_freqs.append(dict(term_freq))
        self._doc_lens.append(len(tokens))
        self._N += 1
        self._avgdl = sum(self._doc_lens) / self._N if self._N else 0.0
        self._idf = {
            term: math.log(1.0 + (self._N - df + 0.5) / (df + 0.5))
            for term, df in self._df.items()
        }

    def search(self, query: str, top_k: int) -> list[tuple[str, float]]:
        """返回 ``(doc_id, bm25_score)`` 降序列表。"""
        if self._N == 0:
            return []
        query_terms = tokenize(query)
        if not query_terms:
            return []

        scores: dict[str, float] = {}
        for index, doc_id in enumerate(self._doc_ids):
            term_freq = self._doc_freqs[index]
            doc_len = self._doc_lens[index]
            score = 0.0
            for term in query_terms:
                if term not in term_freq:
                    continue
                idf = self._idf.get(term, 0.0)
                freq = term_freq[term]
                denominator = freq + self.k1 * (
                    1 - self.b + self.b * doc_len / (self._avgdl or 1.0)
                )
                score += idf * (freq * (self.k1 + 1)) / denominator
            if score > 0:
                scores[doc_id] = score

        return sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_k]


def rrf_fuse(
    result_lists: list[list[RetrievalResult]],
    *,
    top_k: int,
    k: int = 60,
) -> list[RetrievalResult]:
    """倒数排名融合（RRF），按结果 ID 合并多路检索结果。"""
    scores: dict[str, float] = {}
    best_by_id: dict[str, RetrievalResult] = {}

    for results in result_lists:
        for rank, item in enumerate(results):
            scores[item.id] = scores.get(item.id, 0.0) + 1.0 / (k + rank + 1)
            if item.id not in best_by_id or item.score > best_by_id[item.id].score:
                best_by_id[item.id] = item

    merged: list[RetrievalResult] = []
    for item_id in sorted(scores, key=lambda key: scores[key], reverse=True)[:top_k]:
        base = best_by_id[item_id].model_copy(deep=True)
        base.score = scores[item_id]
        base.metadata = {**base.metadata, "rrf": scores[item_id]}
        base.source = "hybrid"
        merged.append(base)
    return merged


__all__ = ["BM25Index", "rrf_fuse", "tokenize"]
