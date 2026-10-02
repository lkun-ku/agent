"""RAG 输入边界与生成空值处理。"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.rag.generator import RAGGenerator
from app.core.rag.pipeline import RAGPipeline
from app.models.schemas import RetrievalResult


class _FakeStore:
    async def search(self, query: str, top_k: int = 4) -> list[RetrievalResult]:
        return []


class _FakeGenerator:
    async def generate(
        self,
        query: str,
        contexts: list[RetrievalResult],
        chat_history: list[Any],
    ) -> Any:
        raise AssertionError("不应调用生成器")


@pytest.mark.asyncio
async def test_retrieve_rejects_non_positive_top_k() -> None:
    pipeline = RAGPipeline(_FakeStore(), _FakeGenerator())
    with pytest.raises(ValueError, match="top_k"):
        await pipeline.retrieve("q", top_k=0)


@pytest.mark.asyncio
async def test_retrieve_rejects_negative_distance() -> None:
    pipeline = RAGPipeline(_FakeStore(), _FakeGenerator())
    with pytest.raises(ValueError, match="max_distance"):
        await pipeline.retrieve("q", max_distance=-1.0)


@pytest.mark.asyncio
async def test_generator_rejects_blank_query() -> None:
    generator = RAGGenerator(object())
    with pytest.raises(ValueError, match="query"):
        await generator.generate("   ", [], [])
