"""RAG 管线回归测试：分块映射、距离阈值过滤、引用上下文拼装。"""

from __future__ import annotations

from typing import Any

from app.core.rag.pipeline import RAGPipeline
from app.models.schemas import Citation, RAGResponse, RetrievalResult


class _FakeStore:
    def __init__(self, results: list[RetrievalResult]) -> None:
        self.rows: list[dict[str, Any]] = []
        self._results = results
        self.last_top_k = 0

    async def add_chunks(self, rows: list[dict[str, Any]]) -> int:
        self.rows = rows
        return len(rows)

    async def search(self, query: str, top_k: int = 4) -> list[RetrievalResult]:
        self.last_top_k = top_k
        return list(self._results)


class _FakeGenerator:
    def __init__(self) -> None:
        self.contexts: list[RetrievalResult] = []

    async def generate(
        self,
        query: str,
        contexts: list[RetrievalResult],
        chat_history: list[Any],
    ) -> RAGResponse:
        self.contexts = contexts
        return RAGResponse(
            answer="答案 [1]",
            citations=[Citation(index=1, result_id="c1", snippet="s")],
            model="test-model",
        )


async def test_index_document_builds_rows() -> None:
    store = _FakeStore([])
    pipeline = RAGPipeline(store, _FakeGenerator())  # type: ignore[arg-type]

    count = await pipeline.index_document(
        doc_id="doc-1",
        filename="a.txt",
        chunks=["第一段", "第二段"],
        chunk_ids=["c1", "c2"],
    )

    assert count == 2
    assert store.rows[0] == {
        "id": "c1",
        "text": "第一段",
        "doc_id": "doc-1",
        "filename": "a.txt",
        "chunk_index": 0,
    }
    assert store.rows[1]["chunk_index"] == 1


async def test_retrieve_filters_by_distance() -> None:
    near = RetrievalResult(id="c1", content="相关", score=0.5)
    far = RetrievalResult(id="c2", content="无关", score=1.6)
    store = _FakeStore([near, far])
    pipeline = RAGPipeline(store, _FakeGenerator())  # type: ignore[arg-type]

    results = await pipeline.retrieve("问题", top_k=4)

    assert [r.id for r in results] == ["c1"]
    assert store.last_top_k == 4


async def test_answer_prefixes_context_with_source() -> None:
    generator = _FakeGenerator()
    pipeline = RAGPipeline(_FakeStore([]), generator)  # type: ignore[arg-type]
    contexts = [
        RetrievalResult(
            id="c1",
            content="原始内容",
            score=0.3,
            metadata={"filename": "policy.txt", "chunk_index": 2},
        )
    ]

    response = await pipeline.answer("问题", [], contexts)

    assert generator.contexts[0].content == "[policy.txt#2] 原始内容"
    assert response.citations[0].result_id == "c1"
