"""P1-P3 增量能力回归：端口、持久化、缓存、混合检索与 Agent 适配。"""

from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest

from app.api.routes import chat as chat_route
from app.core.agent.adapters import RegistryToolInvoker, RouterLLMProvider
from app.core.chat import service as chat_service_module
from app.core.chat.service import ChatApplicationService
from app.core.intent.recognizer import IntentRecognizer
from app.core.rag.pipeline import RAGPipeline
from app.core.tools.schemas import ToolResult
from app.infrastructure.database.repositories import (
    ConversationMemory,
    TraceRepository,
    canonical_conversation_id,
)
from app.infrastructure.llm.adapter import RouterLLM
from app.infrastructure.trace.tracer import Tracer, TraceRecord, TraceSpan
from app.models.enums import RetrievalMode
from app.models.schemas import ChatMessage, RAGResponse, RetrievalResult


class _FakeStore:
    async def search(
        self,
        query: str,
        top_k: int = 4,
        max_distance: float | None = None,
    ) -> list[RetrievalResult]:
        return [
            RetrievalResult(
                id="vector-1",
                content="向量命中的退款内容",
                score=0.3,
                metadata={"filename": "vector.md"},
            )
        ]


class _FakeGenerator:
    async def generate(
        self,
        query: str,
        contexts: list[RetrievalResult],
        chat_history: list[Any],
    ) -> Any:
        raise AssertionError("检索测试不应触发生成器")


async def _keyword_documents() -> dict[str, str]:
    return {"keyword-1": "退款政策：签收后七天内可申请退款"}


@pytest.mark.asyncio
async def test_hybrid_retrieval_fuses_vector_and_keyword() -> None:
    pipeline = RAGPipeline(
        _FakeStore(),
        _FakeGenerator(),
        retrieval_mode=RetrievalMode.HYBRID,
        keyword_provider=_keyword_documents,
    )

    results = await pipeline.retrieve("退款政策", top_k=5)

    assert {item.id for item in results} >= {"vector-1", "keyword-1"}
    assert any(item.source == "hybrid" for item in results)
    assert all(item.metadata.get("rrf", 0) > 0 for item in results)


@pytest.mark.asyncio
async def test_keyword_retrieval_hits_chinese_documents() -> None:
    pipeline = RAGPipeline(
        _FakeStore(),
        _FakeGenerator(),
        retrieval_mode=RetrievalMode.KEYWORD,
        keyword_provider=_keyword_documents,
    )

    results = await pipeline.retrieve("退款政策", top_k=3)

    assert [item.id for item in results] == ["keyword-1"]
    assert results[0].source == "keyword"


def test_canonical_conversation_id_is_stable() -> None:
    first = canonical_conversation_id("customer-42")
    second = canonical_conversation_id("customer-42")
    assert first == second
    assert len(first) == 36


class _FakeAsyncSession:
    def __init__(self, owner: _FakeSessionFactory) -> None:
        self.owner = owner

    async def __aenter__(self) -> _FakeAsyncSession:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def add_all(self, rows: list[Any]) -> None:
        self.owner.added.extend(rows)

    async def commit(self) -> None:
        self.owner.commits += 1


class _FakeSessionFactory:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.commits = 0

    def __call__(self) -> _FakeAsyncSession:
        return _FakeAsyncSession(self)


@pytest.mark.asyncio
async def test_trace_repository_maps_span_duration_and_result() -> None:
    factory = _FakeSessionFactory()
    record = TraceRecord(trace_id="trace-1")
    record.spans.append(
        TraceSpan(
            span_id="span-1",
            trace_id="trace-1",
            operation="chat",
            parent_span_id=None,
            start_time=0.0,
            end_time=0.05,
            result={"mode": "rag"},
        )
    )

    saved = await TraceRepository(factory).save_record(record)  # type: ignore[arg-type]

    assert saved == 1
    assert factory.commits == 1
    assert len(factory.added) == 1
    row = factory.added[0]
    assert row.trace_id == "trace-1"
    assert row.duration_ms == 50
    assert row.payload == {"mode": "rag"}


def test_conversation_memory_is_read_only() -> None:
    class FakeRepository:
        def __init__(self) -> None:
            self.reads: list[int] = []

        async def get_recent_messages(
            self,
            conversation_key: str,
            limit: int = 8,
        ) -> list[str]:
            self.reads.append(limit)
            return ["历史消息"]

    repository = FakeRepository()
    memory = ConversationMemory(repository)  # type: ignore[arg-type]

    import asyncio

    messages = asyncio.run(memory.get_relevant("conversation-1", "q", limit=3))

    assert messages == ["历史消息"]
    assert repository.reads == [3]


@pytest.mark.asyncio
async def test_registry_tool_invoker_serializes_tool_result() -> None:
    class FakeRegistry:
        def list_tool_names(self) -> list[str]:
            return ["fake"]

        def get_tools_description(self) -> str:
            return "- fake: fake tool"

        async def invoke(self, name: str, arguments: dict[str, Any]) -> ToolResult:
            assert name == "fake"
            return ToolResult(
                status="need_info",
                action="NEED_ORDER",
                reply="请提供订单号",
            )

    observation = await RegistryToolInvoker(FakeRegistry()).invoke(  # type: ignore[arg-type]
        "fake",
        {},
    )
    payload = json.loads(observation)
    assert payload["status"] == "need_info"
    assert payload["action"] == "NEED_ORDER"


@pytest.mark.asyncio
async def test_router_llm_exposes_agent_completion_alias() -> None:
    class FakeRouter:
        async def chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> Any:
            assert messages
            return SimpleNamespace(content="ok")

    llm = RouterLLM(FakeRouter())  # type: ignore[arg-type]
    assert await llm.acomplete([{"role": "user", "content": "hi"}]) == "ok"
    assert await RouterLLMProvider(FakeRouter()).get_llm("react").acomplete(
        [{"role": "user", "content": "hi"}]
    ) == "ok"


@pytest.mark.asyncio
async def test_rag_cache_get_set_roundtrip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeRedis:
        def __init__(self) -> None:
            self.values: dict[str, str] = {}

        async def get(self, key: str) -> str | None:
            return self.values.get(key)

        async def set(self, key: str, value: str, ttl: int = 3600) -> None:
            self.values[key] = value
            assert ttl > 0

    fake = FakeRedis()
    monkeypatch.setattr(chat_service_module, "get_redis_cache", lambda: fake)

    request = chat_route.ChatRequest(
        messages=[ChatMessage(role="user", content="退款政策")]
    )
    chat_service = ChatApplicationService(Tracer(), IntentRecognizer())
    key = chat_service.rag_cache_key(request)
    assert await chat_service.get_cached_rag(key) is None

    response = RAGResponse(
        answer="七天可退",
        model="deepseek-flash",
    )
    await chat_service.store_cached_rag(key, response)

    cached = await chat_service.get_cached_rag(key)
    assert cached is not None
    assert cached["content"] == "七天可退"


def test_rag_cache_key_changes_with_retrieval_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = chat_route.ChatRequest(
        messages=[ChatMessage(role="user", content="退款政策")]
    )
    monkeypatch.setattr(
        chat_route.get_settings(),
        "rag_retrieval_mode",
        "vector",
    )
    chat_service = ChatApplicationService(Tracer(), IntentRecognizer())
    first = chat_service.rag_cache_key(request)
    monkeypatch.setattr(
        chat_route.get_settings(),
        "rag_retrieval_mode",
        "hybrid",
    )
    second = chat_service.rag_cache_key(request)
    assert first != second


def test_datetime_helper_uses_utc() -> None:
    from app.infrastructure.database.repositories import utc_now_iso

    parsed = datetime.fromisoformat(utc_now_iso())
    assert parsed.utcoffset() is not None
