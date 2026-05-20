# -*- coding: utf-8 -*-
"""熔断状态机：Closed -> Open -> Half-Open -> Closed / 重新 Open。"""

from __future__ import annotations

import asyncio

import pytest

from app.infrastructure.llm.circuit_breaker import CircuitBreaker, CircuitState


@pytest.mark.asyncio
async def test_closed_open_half_open_closed() -> None:
    breaker = CircuitBreaker(
        failure_threshold=2, recovery_timeout=0.1, half_open_max=1
    )
    calls = {"n": 0}

    async def fail() -> str:
        calls["n"] += 1
        raise RuntimeError("boom")

    for _ in range(2):
        with pytest.raises(RuntimeError):
            await breaker.call(fail)

    assert breaker.state is CircuitState.OPEN
    snapshot = breaker.snapshot()
    assert snapshot["state"] == "open"
    assert snapshot["failures"] == 2
    assert snapshot["retry_in"] > 0

    with pytest.raises(RuntimeError, match="OPEN"):
        await breaker.call(fail)
    assert calls["n"] == 2, "OPEN 状态不应再调用下游"

    await asyncio.sleep(0.12)

    async def ok() -> str:
        return "ok"

    assert await breaker.call(ok) == "ok"
    assert breaker.state is CircuitState.CLOSED
    assert breaker.snapshot()["failures"] == 0


@pytest.mark.asyncio
async def test_half_open_failure_reopens() -> None:
    breaker = CircuitBreaker(
        failure_threshold=1, recovery_timeout=0.1, half_open_max=3
    )

    async def fail() -> str:
        raise RuntimeError("down")

    with pytest.raises(RuntimeError):
        await breaker.call(fail)
    assert breaker.state is CircuitState.OPEN

    await asyncio.sleep(0.12)

    with pytest.raises(RuntimeError):
        await breaker.call(fail)
    assert breaker.state is CircuitState.OPEN
