"""Trace 持久化：把内存 Span 树写入 trace_logs。"""

from __future__ import annotations

from typing import Any

from app.infrastructure.database.models import TraceLog
from app.infrastructure.trace.tracer import TraceRecord


class TraceLogWriter:
    """按 span 写入 trace_logs；失败由调用方决定是否告警。"""

    def __init__(self, session_factory: Any | None = None) -> None:
        self._factory = session_factory

    def _resolve_factory(self) -> Any | None:
        if self._factory is not None:
            return self._factory
        from app.infrastructure.database.session import async_session_factory

        return async_session_factory

    async def persist(self, record: TraceRecord) -> int:
        factory = self._resolve_factory()
        if factory is None:
            return 0

        rows = 0
        async with factory() as session:
            for span in record.spans:
                duration = None
                if span.end_time is not None:
                    duration = max(0, int((span.end_time - span.start_time) * 1000))
                session.add(
                    TraceLog(
                        trace_id=record.trace_id,
                        span_id=span.span_id,
                        operation=span.operation,
                        payload={
                            "result": span.result,
                            "usage": span.usage,
                            "parent_span_id": span.parent_span_id,
                        },
                        error=span.error,
                        duration_ms=duration,
                    )
                )
                rows += 1
            await session.commit()
        return rows
