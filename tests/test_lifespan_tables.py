# -*- coding: utf-8 -*-
"""P1-6：启动生命周期必须确保表存在，且数据库不可用时不能阻断启动。"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.main import lifespan


class FakeApp:
    def __init__(self) -> None:
        self.state = SimpleNamespace()


class FakeConn:
    def __init__(self, calls: list[Any], fail: bool = False) -> None:
        self._calls = calls
        self._fail = fail

    async def run_sync(self, fn: Any) -> None:
        if self._fail:
            raise RuntimeError("db down")
        self._calls.append(fn)


class FakeBegin:
    def __init__(self, engine: FakeEngine) -> None:
        self._engine = engine

    async def __aenter__(self) -> FakeConn:
        return FakeConn(self._engine.calls, fail=self._engine.fail)

    async def __aexit__(self, *args: Any) -> bool:
        return False


class FakeEngine:
    def __init__(self, fail: bool = False) -> None:
        self.calls: list[Any] = []
        self.fail = fail

    def begin(self) -> FakeBegin:
        return FakeBegin(self)

    async def dispose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_lifespan_calls_create_all(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = FakeEngine()
    monkeypatch.setattr("app.main.init_engine", lambda *a, **kw: engine)
    monkeypatch.setattr("app.main.configure_session", lambda e: None)

    async with lifespan(FakeApp()):  # type: ignore[arg-type]
        pass

    assert any(getattr(fn, "__name__", "") == "create_all" for fn in engine.calls)


@pytest.mark.asyncio
async def test_lifespan_survives_unavailable_database(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = FakeEngine(fail=True)
    monkeypatch.setattr("app.main.init_engine", lambda *a, **kw: engine)
    monkeypatch.setattr("app.main.configure_session", lambda e: None)

    async with lifespan(FakeApp()):  # type: ignore[arg-type]
        pass  # 不应抛异常，服务仍可启动
