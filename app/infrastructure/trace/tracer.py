"""全链路追踪：内存存储 Span 树与查询接口。"""

from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import httpx
from loguru import logger


def _hex_id(value: str, length: int) -> str:
    """把 UUID/任意 trace 标识转成 OTLP 需要的定长十六进制。"""
    try:
        raw = uuid.UUID(value).hex
    except ValueError:
        raw = hashlib.sha1(value.encode("utf-8")).hexdigest()
    return raw[:length].ljust(length, "0")


@dataclass
class TraceSpan:
    """单次操作 Span。"""

    span_id: str
    trace_id: str
    operation: str
    parent_span_id: str | None
    start_time: float
    start_epoch: float = field(default_factory=time.time)
    end_time: float | None = None
    end_epoch: float | None = None
    result: dict[str, Any] | None = None
    usage: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class TraceRecord:
    """一次 Trace 的完整记录。"""

    trace_id: str
    spans: list[TraceSpan] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


class Tracer:
    """全链路追踪器：记录 Agent 执行的每个步骤（进程内存储，可替换为导出到 OTLP）。"""

    def __init__(self, max_traces: int = 5000) -> None:
        self._max_traces = max_traces
        self._traces: dict[str, TraceRecord] = {}
        self._lock = threading.RLock()
        self._current_parent: dict[str, str | None] = {}

    def start_trace(self, trace_id: str, operation: str) -> TraceSpan:
        """开始新的根 Span（同 trace_id 下若已有记录则追加 Span）。"""
        with self._lock:
            rec = self._traces.get(trace_id)
            if rec is None:
                rec = TraceRecord(trace_id=trace_id)
                self._traces[trace_id] = rec
                self._trim_locked()

            span = TraceSpan(
                span_id=str(uuid.uuid4()),
                trace_id=trace_id,
                operation=operation,
                parent_span_id=None,
                start_time=time.perf_counter(),
            )
            rec.spans.append(span)
            self._current_parent[trace_id] = span.span_id
            logger.debug("trace={} span={} op={} 开始", trace_id, span.span_id, operation)
            return span

    def start_child_span(
        self,
        trace_id: str,
        operation: str,
        parent_span_id: str | None = None,
    ) -> TraceSpan:
        """在已有 Trace 下创建子 Span。"""
        with self._lock:
            rec = self._traces.get(trace_id)
            if rec is None:
                rec = TraceRecord(trace_id=trace_id)
                self._traces[trace_id] = rec
                self._trim_locked()

            parent = parent_span_id or self._current_parent.get(trace_id)
            span = TraceSpan(
                span_id=str(uuid.uuid4()),
                trace_id=trace_id,
                operation=operation,
                parent_span_id=parent,
                start_time=time.perf_counter(),
            )
            rec.spans.append(span)
            self._current_parent[trace_id] = span.span_id
            return span

    def end_span(
        self,
        span: TraceSpan,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """结束 Span 并记录结果或错误。"""
        with self._lock:
            rec = self._traces.get(span.trace_id)
            if rec is None:
                logger.warning("end_span 找不到 trace_id={}", span.trace_id)
                return
            span.end_time = time.perf_counter()
            span.end_epoch = time.time()
            span.result = result
            if isinstance(result, dict):
                span.usage = result.get("usage")
            span.error = error
            logger.debug(
                "trace={} span={} op={} 结束 error={}",
                span.trace_id,
                span.span_id,
                span.operation,
                error,
            )

    def get_trace(self, trace_id: str) -> TraceRecord | None:
        """按 trace_id 获取完整追踪记录。"""
        with self._lock:
            rec = self._traces.get(trace_id)
            if rec is None:
                return None
            # 返回浅拷贝，避免外部修改内部列表结构
            return TraceRecord(
                trace_id=rec.trace_id,
                spans=list(rec.spans),
                created_at=rec.created_at,
            )

    def total_tokens(self, record: TraceRecord) -> int:
        """汇总一条 trace 中所有 span 的 total_tokens。"""
        total = 0
        for span in record.spans:
            usage = span.usage or {}
            total += int(usage.get("total_tokens", 0) or 0)
        return total

    def export_jsonl(self, trace_id: str, path: str = "logs/trace.jsonl") -> bool:
        """把一条 trace 追加写入 JSONL；trace 不存在时返回 False。"""
        record = self.get_trace(trace_id)
        if record is None:
            return False
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(asdict(record), ensure_ascii=False, default=str)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        return True

    async def export_otlp(
        self,
        trace_id: str,
        endpoint: str,
        *,
        service_name: str = "enterprise-ai-agent",
        headers: dict[str, str] | None = None,
        client: Any | None = None,
    ) -> bool:
        """按 OTLP/HTTP JSON 导出；失败返回 False，不抛异常。"""
        record = self.get_trace(trace_id)
        if record is None or not record.spans:
            return False

        trace_hex = _hex_id(record.trace_id, 32)

        spans_payload: list[dict[str, Any]] = []
        for span in record.spans:
            start_ns = int(span.start_epoch * 1_000_000_000)
            end_epoch = span.end_epoch or span.start_epoch
            end_ns = int(end_epoch * 1_000_000_000)

            attributes: list[dict[str, Any]] = []
            usage = span.usage or {}
            if "total_tokens" in usage:
                attributes.append(
                    {
                        "key": "usage.total_tokens",
                        "value": {"intValue": str(usage["total_tokens"])},
                    }
                )
            if span.error:
                attributes.append(
                    {"key": "error", "value": {"stringValue": span.error}}
                )

            if span.end_time is None:
                status_code = 0
            elif span.error:
                status_code = 2
            else:
                status_code = 1

            spans_payload.append(
                {
                    "traceId": trace_hex,
                    "spanId": _hex_id(span.span_id, 16),
                    "parentSpanId": _hex_id(span.parent_span_id, 16)
                    if span.parent_span_id
                    else "",
                    "name": span.operation,
                    "kind": 1,
                    "startTimeUnixNano": str(start_ns),
                    "endTimeUnixNano": str(end_ns),
                    "attributes": attributes,
                    "status": {"code": status_code},
                }
            )

        payload = {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {
                                "key": "service.name",
                                "value": {"stringValue": service_name},
                            }
                        ]
                    },
                    "scopeSpans": [
                        {
                            "scope": {"name": "app.tracer"},
                            "spans": spans_payload,
                        }
                    ],
                }
            ]
        }

        own_client = client is None
        http_client = client or httpx.AsyncClient(timeout=10.0)
        try:
            response = await http_client.post(
                endpoint.rstrip("/") + "/v1/traces",
                json=payload,
                headers={"Content-Type": "application/json", **(headers or {})},
            )
            return 200 <= response.status_code < 300
        except Exception as exc:  # noqa: BLE001
            logger.warning("OTLP 导出失败: {}", exc)
            return False
        finally:
            if own_client:
                await http_client.aclose()

    def _trim_locked(self) -> None:
        """限制内存中 trace 数量。"""
        if len(self._traces) <= self._max_traces:
            return
        # 删除最旧的一批 key（简单按字典序，生产可改为按 created_at）
        excess = len(self._traces) - self._max_traces
        for key in list(self._traces.keys())[:excess]:
            del self._traces[key]
