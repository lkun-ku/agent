"""PostgreSQL 仓储：会话消息与 Trace 持久化。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.database.models import Conversation, Message, TraceLog
from app.infrastructure.trace.tracer import TraceRecord

_CONVERSATION_NAMESPACE = uuid.UUID("4f8c3af8-9c58-4c8b-8840-4f68f7f54c9c")
_SENSITIVE_KEYS = {
    "authorization",
    "api_key",
    "apikey",
    "token",
    "access_token",
    "refresh_token",
    "password",
    "secret",
}


def redact_payload(value: Any) -> Any:
    """递归脱敏常见凭据字段；业务文本保留，便于排障。"""
    if isinstance(value, dict):
        return {
            key: "***"
            if str(key).lower() in _SENSITIVE_KEYS
            else redact_payload(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_payload(item) for item in value)
    return value


def canonical_conversation_id(value: str) -> str:
    """把外部会话键规整为数据库 UUID；保持同一输入映射到同一会话。"""
    try:
        return str(uuid.UUID(value))
    except ValueError:
        return str(uuid.uuid5(_CONVERSATION_NAMESPACE, f"conversation:{value}"))


class ConversationRepository:
    """Conversation / Message 的最小持久化仓储。"""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = session_factory

    async def append_turn(
        self,
        conversation_key: str,
        user_content: str,
        assistant_content: str,
        *,
        assistant_metadata: dict[str, Any] | None = None,
        user_metadata: dict[str, Any] | None = None,
    ) -> str:
        """写入一轮问答；会话不存在时自动创建。返回规范后的会话 ID。"""
        cid = canonical_conversation_id(conversation_key)
        async with self._sessions() as session:
            conversation = await session.get(Conversation, cid)
            if conversation is None:
                conversation = Conversation(
                    id=cid,
                    title=user_content[:120],
                    meta={"source": "chat"},
                )
                session.add(conversation)

            session.add_all(
                [
                    Message(
                        conversation_id=cid,
                        role="user",
                        content=user_content,
                        meta=user_metadata or {},
                    ),
                    Message(
                        conversation_id=cid,
                        role="assistant",
                        content=assistant_content,
                        meta=assistant_metadata or {},
                    ),
                ]
            )
            await session.commit()
        return cid

    async def get_recent_messages(
        self,
        conversation_key: str,
        limit: int = 8,
    ) -> list[str]:
        """返回最近消息文本，时间升序；供通用 Agent 作为记忆上下文。"""
        cid = canonical_conversation_id(conversation_key)
        async with self._sessions() as session:
            result = await session.execute(
                select(Message.content)
                .where(Message.conversation_id == cid)
                .order_by(Message.created_at.desc(), Message.id.desc())
                .limit(max(1, limit))
            )
            rows = list(result.scalars().all())
        return list(reversed(rows))


class ConversationMemory:
    """把 ConversationRepository 适配成通用 Agent 的只读 MemoryLike。"""

    def __init__(self, repository: ConversationRepository) -> None:
        self._repository = repository

    async def get_relevant(
        self,
        session_id: str,
        query: str,
        limit: int = 8,
    ) -> list[str]:
        """通用 Agent 记忆接口；query 当前仅用于日志语义，不做向量召回。"""
        _ = query
        return await self._repository.get_recent_messages(session_id, limit=limit)


class TraceRepository:
    """TraceLog 持久化仓储。"""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = session_factory

    async def save_record(self, record: TraceRecord) -> int:
        """保存一次 Trace 的全部 Span，返回写入条数。"""
        rows: list[TraceLog] = []
        for span in record.spans:
            duration_ms = (
                int((span.end_time - span.start_time) * 1000)
                if span.end_time is not None
                else None
            )
            rows.append(
                TraceLog(
                    trace_id=record.trace_id,
                    span_id=span.span_id,
                    operation=span.operation,
                    payload=redact_payload(span.result or {}),
                    error=span.error,
                    duration_ms=duration_ms,
                )
            )
        if not rows:
            return 0

        async with self._sessions() as session:
            session.add_all(rows)
            await session.commit()
        return len(rows)

    async def prune_before(self, retention_days: int) -> int:
        """删除保留期之前的 TraceLog，返回删除行数。"""
        cutoff = datetime.now(UTC) - timedelta(days=max(1, retention_days))
        async with self._sessions() as session:
            result = await session.execute(
                delete(TraceLog).where(TraceLog.created_at < cutoff)
            )
            await session.commit()
            return int(cast("CursorResult[Any]", result).rowcount or 0)


class ObservabilityRetentionService:
    """按保留策略清理 Trace 与会话消息。"""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._trace_repository = TraceRepository(session_factory)
        self._sessions = session_factory

    async def cleanup(
        self,
        *,
        trace_retention_days: int,
        conversation_retention_days: int,
    ) -> dict[str, int]:
        trace_deleted = await self._trace_repository.prune_before(trace_retention_days)
        message_cutoff = datetime.now(UTC) - timedelta(
            days=max(1, conversation_retention_days)
        )
        async with self._sessions() as session:
            message_result = await session.execute(
                delete(Message).where(Message.created_at < message_cutoff)
            )
            await session.commit()
        return {
            "trace_logs": trace_deleted,
            "messages": int(cast("CursorResult[Any]", message_result).rowcount or 0),
        }


def utc_now_iso() -> str:
    """供仓储测试与日志使用的稳定 UTC 时间格式。"""
    return datetime.now(UTC).isoformat()


__all__ = [
    "ConversationMemory",
    "ConversationRepository",
    "ObservabilityRetentionService",
    "TraceRepository",
    "canonical_conversation_id",
    "redact_payload",
    "utc_now_iso",
]

