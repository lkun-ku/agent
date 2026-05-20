# -*- coding: utf-8 -*-
"""OTLP/HTTP JSON 导出：字段、ID 格式与失败返回。"""

from __future__ import annotations

from typing import Any

import pytest

from app.infrastructure.trace.tracer import Tracer


class FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class FakeClient:
    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code
        self.calls: list[tuple[str, dict[str, Any], dict[str, str]]] = []

    async def post(
        self,
        url: str,
        json: dict[str, Any],
        headers: dict[str, str],
    ) -> FakeResponse:
        self.calls.append((url, json, headers))
        return FakeResponse(self.status_code)

    async def aclose(self) -> None:
        return None


def build_trace() -> tuple[Tracer, str]:
    tracer = Tracer()
    trace_id = "11111111-1111-1111-1111-111111111111"
    root = tracer.start_trace(trace_id, "chat")
    tracer.end_span(root, result={"usage": {"total_tokens": 5}})
    return tracer, trace_id


@pytest.mark.asyncio
async def test_export_builds_otlp_payload() -> None:
    tracer, trace_id = build_trace()
    client = FakeClient()

    ok = await tracer.export_otlp(trace_id, "http://collector:4318", client=client)

    assert ok is True
    url, payload, headers = client.calls[0]
    assert url == "http://collector:4318/v1/traces"
    assert headers["Content-Type"] == "application/json"

    spans = payload["resourceSpans"][0]["scopeSpans"][0]["spans"]
    assert len(spans) == 1
    span = spans[0]
    assert span["traceId"] == "11111111111111111111111111111111"
    assert len(span["spanId"]) == 16
    assert span["parentSpanId"] == ""
    assert span["name"] == "chat"
    assert int(span["endTimeUnixNano"]) >= int(span["startTimeUnixNano"])
    assert span["attributes"][0]["key"] == "usage.total_tokens"


@pytest.mark.asyncio
async def test_export_returns_false_on_error_status() -> None:
    tracer, trace_id = build_trace()
    client = FakeClient(status_code=500)

    assert await tracer.export_otlp(trace_id, "http://collector:4318", client=client) is False


@pytest.mark.asyncio
async def test_export_unknown_trace_returns_false() -> None:
    tracer = Tracer()
    client = FakeClient()

    assert await tracer.export_otlp("missing", "http://collector:4318", client=client) is False
