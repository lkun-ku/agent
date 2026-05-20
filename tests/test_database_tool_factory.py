# -*- coding: utf-8 -*-
"""database_query：session_factory 路径与显式 session 覆盖。"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.tools.builtin.database import DatabaseQueryTool


class FakeMappings:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def all(self) -> list[dict[str, Any]]:
        return self._rows


class FakeResult:
    def mappings(self) -> FakeMappings:
        return FakeMappings([{"n": 1}])


class FakeSession:
    def __init__(self) -> None:
        self.closed = False

    async def execute(self, statement: Any) -> FakeResult:
        return FakeResult()


class FakeContext:
    def __init__(self, session: FakeSession) -> None:
        self._session = session

    async def __aenter__(self) -> FakeSession:
        return self._session

    async def __aexit__(self, *args: Any) -> bool:
        return False


class FakeFactory:
    def __init__(self) -> None:
        self.calls = 0
        self.session = FakeSession()

    def __call__(self) -> FakeContext:
        self.calls += 1
        return FakeContext(self.session)


@pytest.mark.asyncio
async def test_uses_session_factory_when_session_absent() -> None:
    factory = FakeFactory()
    tool = DatabaseQueryTool(session_factory=factory)

    rows = await tool.execute(sql="SELECT 1 AS n")

    assert rows == [{"n": 1}]
    assert factory.calls == 1


@pytest.mark.asyncio
async def test_explicit_session_overrides_factory() -> None:
    factory = FakeFactory()
    tool = DatabaseQueryTool(session_factory=factory)

    rows = await tool.execute(sql="SELECT 1 AS n", session=FakeSession())

    assert rows == [{"n": 1}]
    assert factory.calls == 0


@pytest.mark.asyncio
async def test_missing_session_and_factory_raises() -> None:
    tool = DatabaseQueryTool()

    with pytest.raises(RuntimeError):
        await tool.execute(sql="SELECT 1")


@pytest.mark.asyncio
async def test_invalid_sql_is_rejected_before_factory_call() -> None:
    factory = FakeFactory()
    tool = DatabaseQueryTool(session_factory=factory)

    with pytest.raises(ValueError):
        await tool.execute(sql="DELETE FROM t")

    assert factory.calls == 0
