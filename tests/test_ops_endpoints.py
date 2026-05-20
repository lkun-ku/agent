# -*- coding: utf-8 -*-
"""运维端点：熔断状态快照与 trace 查询。"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.infrastructure.llm.circuit_breaker import CircuitBreaker


def test_breaker_snapshot_fields() -> None:
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60.0, name="llm:test")

    snapshot = breaker.snapshot()

    assert snapshot == {
        "name": "llm:test",
        "state": "closed",
        "failures": 0,
        "threshold": 3,
        "retry_in": 0.0,
    }


def test_router_snapshot_lists_models() -> None:
    from app.infrastructure.llm.model_router import ModelConfig, ModelRouter

    router = ModelRouter([ModelConfig(model_id="m1", api_key="test-key")])

    snapshot = router.snapshot()

    assert set(snapshot) == {"m1"}
    assert snapshot["m1"]["state"] == "closed"


@pytest.mark.asyncio
async def test_health_circuit_returns_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api.routes import chat, health

    class FakeRouter:
        async def refresh(self) -> None:
            return None

        def snapshot(self):
            return {"m1": {"state": "closed"}}

    monkeypatch.setattr(chat, "get_model_router", lambda: FakeRouter())

    assert await health.health_circuit() == {"m1": {"state": "closed"}}


@pytest.mark.asyncio
async def test_trace_endpoint_returns_record(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api.routes import chat, health
    from app.infrastructure.trace.tracer import Tracer

    tracer = Tracer()
    span = tracer.start_trace("trace-x", "chat")
    tracer.end_span(span)
    monkeypatch.setattr(chat, "_tracer", tracer)

    data = await health.get_trace("trace-x")

    assert data["trace_id"] == "trace-x"
    assert len(data["spans"]) == 1


@pytest.mark.asyncio
async def test_trace_endpoint_404(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api.routes import chat, health
    from app.infrastructure.trace.tracer import Tracer

    monkeypatch.setattr(chat, "_tracer", Tracer())

    with pytest.raises(HTTPException):
        await health.get_trace("missing")
