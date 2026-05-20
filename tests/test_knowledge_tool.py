# -*- coding: utf-8 -*-
"""知识检索工具：检索 -> 生成 -> 返回带引用的 JSON。"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.core.tools.builtin.knowledge import KnowledgeSearchTool
from app.core.tools.registry import ToolRegistry
from app.models.schemas import Citation, RAGResponse, RetrievalResult


class FakeRetriever:
    def __init__(self, results: list[RetrievalResult]) -> None:
        self._results = results
        self.calls: list[tuple[str, int, str]] = []

    async def retrieve(
        self, query: str, top_k: int = 10, mode: str = "hybrid"
    ) -> list[RetrievalResult]:
        self.calls.append((query, top_k, mode))
        return self._results


class FakeGenerator:
    async def generate(
        self,
        query: str,
        contexts: list[RetrievalResult],
        chat_history: list[Any],
    ) -> RAGResponse:
        return RAGResponse(
            answer="答案 [1]",
            citations=[Citation(index=1, result_id=contexts[0].id, snippet="片段")],
            invalid_citations=[],
            raw_contexts=list(contexts),
        )


def make_tool(results: list[RetrievalResult]) -> KnowledgeSearchTool:
    return KnowledgeSearchTool(FakeRetriever(results), FakeGenerator(), top_k=3)


@pytest.mark.asyncio
async def test_tool_returns_answer_and_citations() -> None:
    tool = make_tool([RetrievalResult(id="c1", content="内容", score=1.0)])

    payload = json.loads(await tool.execute(query="问题"))

    assert payload["answer"] == "答案 [1]"
    assert payload["citations"][0]["index"] == 1
    assert payload["citations"][0]["result_id"] == "c1"


@pytest.mark.asyncio
async def test_tool_reports_no_context() -> None:
    tool = make_tool([])

    result = await tool.execute(query="问题")

    assert "未检索到" in result


@pytest.mark.asyncio
async def test_tool_rejects_empty_query() -> None:
    tool = make_tool([])

    with pytest.raises(ValueError):
        await tool.execute(query="  ")


@pytest.mark.asyncio
async def test_tool_works_through_registry() -> None:
    registry = ToolRegistry()
    registry.register(make_tool([RetrievalResult(id="c1", content="内容", score=1.0)]))

    raw = await registry.invoke("knowledge_search", {"query": "问题"})

    assert json.loads(raw)["answer"] == "答案 [1]"
