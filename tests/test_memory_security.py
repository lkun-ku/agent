# -*- coding: utf-8 -*-
"""P0-4：长期记忆的 session_id 必须走白名单，非法输入在 embed 之前被拒绝。"""

from __future__ import annotations

import pytest

from app.core.memory.long_term import LongTermMemory


class FakeEmbedder:
    def __init__(self) -> None:
        self.calls = 0

    def embed_query(self, text: str) -> list[float]:
        self.calls += 1
        return [0.1, 0.2, 0.3]


class FakeCollection:
    def __init__(self) -> None:
        self.search_expr: str | None = None
        self.deleted: list[str] = []

    def insert(self, data, **kwargs) -> None:
        return None

    def search(self, **kwargs):
        self.search_expr = kwargs.get("expr")
        return [[]]

    def delete(self, expr: str) -> None:
        self.deleted.append(expr)

    def flush(self) -> None:
        return None


@pytest.mark.asyncio
async def test_recall_rejects_quote_in_session_id_before_embedding() -> None:
    embedder = FakeEmbedder()
    memory = LongTermMemory(FakeCollection(), embedder)

    with pytest.raises(ValueError, match="非法 session_id"):
        await memory.recall("问题", 'a" or pk != "')

    assert embedder.calls == 0, "非法 session_id 不应触发嵌入调用"


@pytest.mark.asyncio
async def test_forget_rejects_illegal_session_id() -> None:
    memory = LongTermMemory(FakeCollection(), FakeEmbedder())

    with pytest.raises(ValueError, match="非法 memory_id"):
        await memory.forget('x" or 1 == 1 or "')


@pytest.mark.asyncio
async def test_recall_accepts_safe_session_id_and_uses_filter() -> None:
    collection = FakeCollection()
    memory = LongTermMemory(collection, FakeEmbedder())

    items = await memory.recall("问题", "sess-01_A")

    assert items == []
    assert collection.search_expr == 'session_id == "sess-01_A"'
