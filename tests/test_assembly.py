# -*- coding: utf-8 -*-
"""P0-1：装配层把 core 协议接到基础设施，并保留开关。"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.core.tools.builtin.calculator import CalculatorTool
from app.core.tools.registry import ToolRegistry
from app.infrastructure.trace.tracer import Tracer


class FakeRouter:
    def __init__(self, content: str) -> None:
        self._content = content
        self.calls: list[list[dict[str, str]]] = []

    async def chat(self, messages, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(list(messages))
        return SimpleNamespace(content=self._content)


@pytest.mark.asyncio
async def test_service_returns_answer_mode_and_steps() -> None:
    from app.services.agent_service import AgentService

    router = FakeRouter("Thought: 直接回答\nFinal Answer: 答案")
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    service = AgentService(
        model_router=router,
        tools=registry,
        tracer=Tracer(),
        config={"enable_reflection": False, "react_max_steps": 2},
    )

    response = await service.run("1+1 等于几", session_id="s1")

    assert response.success
    assert response.answer == "答案"
    assert response.mode_used == "react"
    assert response.trace_id
    assert len(response.steps) >= 1, "装配后应能看到执行步骤"


@pytest.mark.asyncio
async def test_model_router_adapter_maps_chat_to_acomplete() -> None:
    from app.services.agent_service import ModelRouterAdapter

    router = FakeRouter("hello")
    llm = ModelRouterAdapter(router).get_llm("react")

    assert await llm.acomplete([{"role": "user", "content": "hi"}]) == "hello"
    assert router.calls


@pytest.mark.asyncio
async def test_tool_registry_adapter_delegates() -> None:
    from app.services.agent_service import ToolRegistryAdapter

    registry = ToolRegistry()
    registry.register(CalculatorTool())
    adapter = ToolRegistryAdapter(registry)

    assert adapter.list_tool_names() == ["calculator"]
    assert float(await adapter.invoke("calculator", {"expression": "1+2"})) == 3.0


def test_agent_switch_default_is_off() -> None:
    from app.config import Settings

    # 断言字段默认值，不依赖本机 .env（E2E 时可能被设为 true）
    assert Settings.model_fields["agent_enabled"].default is False


@pytest.mark.asyncio
async def test_chat_uses_agent_service_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api.routes import chat as chat_module
    from app.core.agent.orchestrator import AgentResponse, IntentContext
    from app.models.schemas import ChatMessage, ChatRequest

    class FakeSettings:
        agent_enabled = True
        openai_model = "gpt-test"
        otlp_endpoint = ""
        trace_jsonl_path = ""

    class FakeService:
        async def run(self, user_input, session_id="default", mode="react"):
            return AgentResponse(
                answer="agent-answer",
                mode_used="react",
                success=True,
                trace_id="t-agent",
                intent=IntentContext(),
            )

    async def fake_service():
        return FakeService()

    monkeypatch.setattr(chat_module, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(chat_module, "get_agent_service", fake_service)

    response = await chat_module.chat(
        ChatRequest(messages=[ChatMessage(role="user", content="hi")])
    )

    assert response.content == "agent-answer"
    assert response.trace_id == "t-agent"


@pytest.mark.asyncio
async def test_chat_agent_failure_returns_502(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi import HTTPException

    from app.api.routes import chat as chat_module
    from app.core.agent.orchestrator import AgentResponse, IntentContext
    from app.models.schemas import ChatMessage, ChatRequest

    class FakeSettings:
        agent_enabled = True
        openai_model = "gpt-test"
        otlp_endpoint = ""
        trace_jsonl_path = ""

    class FailingService:
        async def run(self, user_input, session_id="default", mode="react"):
            return AgentResponse(
                answer="",
                mode_used="react",
                success=False,
                trace_id="t-fail",
                intent=IntentContext(),
                error="所有候选模型均不可用",
            )

    async def fake_service():
        return FailingService()

    monkeypatch.setattr(chat_module, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(chat_module, "get_agent_service", fake_service)

    with pytest.raises(HTTPException) as exc_info:
        await chat_module.chat(
            ChatRequest(messages=[ChatMessage(role="user", content="hi")])
        )

    assert exc_info.value.status_code == 502
    assert "所有候选模型均不可用" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_chat_direct_path_when_agent_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api.routes import chat as chat_module
    from app.models.schemas import ChatMessage, ChatRequest

    class OffSettings:
        agent_enabled = False
        otlp_endpoint = ""
        trace_jsonl_path = ""

    class FakeRouter:
        async def chat(self, messages, **kwargs):
            return SimpleNamespace(
                model_id="direct-model",
                content="direct-answer",
                usage=None,
            )

    def fail_service():  # pragma: no cover
        raise AssertionError("关闭开关时不应使用 AgentService")

    monkeypatch.setattr(chat_module, "get_settings", lambda: OffSettings())
    monkeypatch.setattr(chat_module, "get_agent_service", fail_service)
    monkeypatch.setattr(chat_module, "get_model_router", lambda: FakeRouter())

    response = await chat_module.chat(
        ChatRequest(messages=[ChatMessage(role="user", content="hi")])
    )

    assert response.content == "direct-answer"


def test_stream_client_is_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api.routes import chat as chat_module

    class StreamSettings:
        openai_api_key = "test-key"
        openai_api_base = "https://example.com/v1"

    monkeypatch.setattr(chat_module, "get_settings", lambda: StreamSettings())
    chat_module.get_openai_client.cache_clear()

    assert chat_module.get_openai_client() is chat_module.get_openai_client()
    chat_module.get_openai_client.cache_clear()


@pytest.mark.asyncio
async def test_memory_adapter_maps_context_and_role() -> None:
    from app.models.enums import MessageRole
    from app.models.schemas import MemoryContext, Message
    from app.services.agent_service import MemoryManagerAdapter

    class FakeManager:
        def __init__(self) -> None:
            self.saved: Message | None = None

        async def get_context(self, session_id: str, query: str) -> MemoryContext:
            return MemoryContext(
                session_id=session_id,
                short_term_messages=[
                    Message(role=MessageRole.USER, content="hi")
                ],
                long_term_items=[],
            )

        async def save(self, session_id: str, message: Message) -> None:
            self.saved = message

    manager = FakeManager()
    adapter = MemoryManagerAdapter(manager)

    assert await adapter.get_relevant("s1", "q") == ["hi"]

    await adapter.append_turn("s1", "assistant", "yo", {"k": "v"})

    assert manager.saved is not None
    assert manager.saved.role == MessageRole.ASSISTANT
    assert manager.saved.content == "yo"
