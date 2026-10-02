"""PostgreSQL 仓储：会话消息与 Trace 持久化。"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.database.models import Conversation, Message, TraceLog
from app.infrastructure.trace.tracer import TraceRecord

_CONVERSATION_NAMESPACE = uuid.UUID("4f8c3af8-9c58-4c8b-8840-4f68f7f54c9c")


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

    async def append_message(
        self,
        conversation_key: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """写入单条消息；会话不存在时自动创建。返回规范后的会话 ID。"""
        cid = canonical_conversation_id(conversation_key)
        async with self._sessions() as session:
            conversation = await session.get(Conversation, cid)
            if conversation is None:
                conversation = Conversation(
                    id=cid,
                    title=content[:120],
                    meta={"source": "agent"},
                )
                session.add(conversation)
            session.add(
                Message(
                    conversation_id=cid,
                    role=role,
                    content=content,
                    meta=metadata or {},
                )
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
    """把 ConversationRepository 适配成通用 Agent 的 MemoryLike。

    默认只读：/chat 统一负责写入一轮完整问答，避免 Orchestrator 重复写回复。
    """

    def __init__(
        self,
        repository: ConversationRepository,
        *,
        write_turns: bool = False,
    ) -> None:
        self._repository = repository
        self._write_turns = write_turns

    async def get_relevant(
        self,
        session_id: str,
        query: str,
        limit: int = 8,
    ) -> list[str]:
        """通用 Agent 记忆接口；query 当前仅用于日志语义，不做向量召回。"""
        _ = query
        return await self._repository.get_recent_messages(session_id, limit=limit)

    async def append_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """通用 Agent 写入一条消息；默认由 /chat 统一写入完整轮次。"""
        if not self._write_turns:
            return
        await self._repository.append_message(session_id, role, content, metadata)


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
                    payload=span.result or {},
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


def utc_now_iso() -> str:
    """供仓储测试与日志使用的稳定 UTC 时间格式。"""
    return datetime.now(UTC).isoformat()


__all__ = [
    "ConversationMemory",
    "ConversationRepository",
    "TraceRepository",
    "canonical_conversation_id",
    "utc_now_iso",
]

# 显式导出 Sequence 仅为类型工具友好；运行时不使用。
_ = Sequence
