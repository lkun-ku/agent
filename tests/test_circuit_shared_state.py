# -*- coding: utf-8 -*-
"""熔断状态外置：多副本共享计数，存储故障时回退内存。"""

from __future__ import annotations

from typing import Any

import pytest

from app.infrastructure.llm.circuit_breaker import CircuitBreaker, CircuitState


class FakeStore:
    def __init__(self) -> None:
        self.data: dict[str, dict[str, Any]] = {}
        self.fail = False

    async def load(self, name: str) -> dict[str, Any] | None:
        if self.fail:
            raise RuntimeError("store down")
        return self.data.get(name)

    async def save(self, name: str, state: dict[str, Any]) -> None:
        if self.fail:
            raise RuntimeError("store down")
        self.data[name] = dict(state)


@pytest.mark.asyncio
async def test_two_replicas_share_failure_count() -> None:
    store = FakeStore()
    replica_a = CircuitBreaker(
        failure_threshold=2,
        recovery_timeout=0.1,
        name="shared",
        state_store=store,
    )
    replica_b = CircuitBreaker(
        failure_threshold=2,
        recovery_timeout=0.1,
        name="shared",
        state_store=store,
    )

    async def fail() -> str:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await replica_a.call(fail)
    with pytest.raises(RuntimeError):
        await replica_b.call(fail)

    assert store.data["shared"]["failures"] == 2
    assert store.data["shared"]["state"] == "open"

    calls = {"n": 0}

    async def downstream() -> str:
        calls["n"] += 1
        return "ok"

    with pytest.raises(RuntimeError, match="OPEN"):
        await replica_b.call(downstream)

    assert calls["n"] == 0, "共享状态为 OPEN 时不应调用下游"


@pytest.mark.asyncio
async def test_store_failure_falls_back_to_memory() -> None:
    store = FakeStore()
    store.fail = True
    breaker = CircuitBreaker(
        failure_threshold=1,
        recovery_timeout=0.1,
        name="fallback",
        state_store=store,
    )

    async def fail() -> str:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await breaker.call(fail)

    assert breaker.state is CircuitState.OPEN
