# -*- coding: utf-8 -*-
"""P2-5：Span 要能挂 usage、可按 trace 汇总 token，并落 JSONL。"""

from __future__ import annotations

import json
from pathlib import Path

from app.infrastructure.trace.tracer import Tracer


def build_trace() -> Tracer:
    tracer = Tracer()
    root = tracer.start_trace("t1", "chat")
    tracer.end_span(root, result={"usage": {"total_tokens": 5}})
    child = tracer.start_child_span("t1", "llm")
    tracer.end_span(child, result={"usage": {"total_tokens": 7}})
    return tracer


def test_span_records_usage_and_total_tokens() -> None:
    tracer = build_trace()

    record = tracer.get_trace("t1")

    assert record is not None
    assert [s.usage for s in record.spans] == [
        {"total_tokens": 5},
        {"total_tokens": 7},
    ]
    assert tracer.total_tokens(record) == 12


def test_export_jsonl_writes_one_line(tmp_path: Path) -> None:
    tracer = build_trace()
    path = tmp_path / "trace.jsonl"

    assert tracer.export_jsonl("t1", str(path)) is True

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["trace_id"] == "t1"
    assert len(payload["spans"]) == 2


def test_export_unknown_trace_returns_false(tmp_path: Path) -> None:
    tracer = Tracer()
    assert tracer.export_jsonl("missing", str(tmp_path / "x.jsonl")) is False
