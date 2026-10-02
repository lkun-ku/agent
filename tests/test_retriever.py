"""检索相关回归测试：中文分词与混合检索融合。"""

from __future__ import annotations

from app.core.rag.retriever import MultiRetriever, _tokenize


class _FakeHit:
    def __init__(self, rid: str, text: str, dist: float) -> None:
        self.id = rid
        self.distance = dist
        self.entity = {"id": rid, "text": text}


class _FakeMilvus:
    def search(self, data, anns_field, param, limit, output_fields=None, **kwargs):
        return [[_FakeHit("d1", "向量检索与混合检索", 0.1), _FakeHit("d2", "天气很好", 0.9)]]


class _FakeEmbed:
    def embed_query(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]


def test_tokenize_splits_chinese_into_bigrams() -> None:
    """中文不能整句作为单一 token，否则查询永远无法命中。"""
    tokens = _tokenize("混合检索")
    assert "混合" in tokens
    assert "合检" in tokens
    assert "检索" in tokens
    assert "混合检索" not in tokens  # 不再产生整句 token


def test_tokenize_keeps_ascii_words() -> None:
    assert _tokenize("Milvus RAG 2024") == ["milvus", "rag", "2024"]


def test_tokenize_handles_single_char_cjk() -> None:
    assert _tokenize("好") == ["好"]


async def test_keyword_search_hits_chinese() -> None:
    retriever = MultiRetriever(_FakeMilvus(), _FakeEmbed())
    retriever.register_keyword_documents(
        {"d1": "向量检索与混合检索", "d2": "今天天气很好"}
    )
    results = await retriever.retrieve("混合检索", top_k=2, mode="keyword")
    assert [r.id for r in results] == ["d1"]
    assert results[0].source == "keyword"


async def test_hybrid_search_produces_rrf_scores() -> None:
    retriever = MultiRetriever(_FakeMilvus(), _FakeEmbed())
    retriever.register_keyword_documents({"d1": "向量检索与混合检索"})
    results = await retriever.retrieve("向量检索", top_k=3, mode="hybrid")
    assert results
    assert all(r.source == "hybrid" for r in results)
    assert all(r.metadata.get("rrf", 0) > 0 for r in results)


async def test_unknown_mode_falls_back_to_hybrid() -> None:
    retriever = MultiRetriever(_FakeMilvus(), _FakeEmbed())
    retriever.register_keyword_documents({"d1": "向量检索"})
    results = await retriever.retrieve("检索", top_k=2, mode="not-a-mode")
    assert results
