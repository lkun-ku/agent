# -*- coding: utf-8 -*-
"""Trace 落库：每个 span 一行，带 usage 与耗时。"""

from __future__ import annotations

from typing import Any

import pytest

from app.infrastructure.trace.tracer import Tracer
from app.services.trace_service import TraceLogWriter


class FakeSession:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.committed = False

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.committed = True


class FakeContext:
    def __init__(self, session: FakeSession) -> None:
        self._session = session

    async def __aenter__(self) -> FakeSession:
        return self._session

    async def __aexit__(self, *args: Any) -> bool:
        return False


class FakeFactory:
    def __init__(self, session: FakeSession) -> None:
        self._session = session

    def __call__(self) -> FakeContext:
        return FakeContext(self._session)


@pytest.mark.asyncio
async def test_persist_writes_one_row_per_span() -> None:
    tracer = Tracer()
    root = tracer.start_trace("t1", "chat")
    tracer.end_span(root, result={"usage": {"total_tokens": 5}})
    child = tracer.start_child_span("t1", "llm")
    tracer.end_span(child)
    record = tracer.get_trace("t1")
    assert record is not None

    session = FakeSession()
    writer = TraceLogWriter(FakeFactory(session))

    rows = await writer.persist(record)

    assert rows == 2
    assert len(session.added) == 2
    assert session.committed
    first = session.added[0]
    assert first.trace_id == "t1"
    assert first.payload["usage"] == {"total_tokens": 5}
    assert first.duration_ms is not None
