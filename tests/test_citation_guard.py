# -*- coding: utf-8 -*-
"""P2-4：越界引用必须被记录为质量信号，而不是静默丢弃。"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.rag.generator import RAGGenerator
from app.models.schemas import RetrievalResult


class FakeLLM:
    def __init__(self, answer: str) -> None:
        self._answer = answer

    async def ainvoke(self, input: Any, **kwargs: Any) -> str:
        return self._answer


def make_contexts(n: int = 3) -> list[RetrievalResult]:
    return [
        RetrievalResult(id=f"c{i}", content=f"第 {i} 块内容", score=1.0 - i * 0.1)
        for i in range(1, n + 1)
    ]


@pytest.mark.asyncio
async def test_out_of_range_citation_is_recorded() -> None:
    generator = RAGGenerator(llm=FakeLLM("根据 [1] 和 [9] 可知"))

    response = await generator.generate("问题", make_contexts(3), [])

    assert [c.index for c in response.citations] == [1]
    assert response.invalid_citations == [9]


@pytest.mark.asyncio
async def test_duplicate_and_valid_citations_are_handled() -> None:
    generator = RAGGenerator(llm=FakeLLM("见 [1][1][2]"))

    response = await generator.generate("问题", make_contexts(3), [])

    assert [c.index for c in response.citations] == [1, 2]
    assert response.invalid_citations == []
