# -*- coding: utf-8 -*-
"""编排器必须把用户轮次也写入记忆，否则短期记忆与自动长期写入都失效。"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.agent.orchestrator import AgentOrchestrator


class FakeLLM:
    async def acomplete(self, messages, **kwargs: Any) -> str:
        return "Thought: 直接回答\nFinal Answer: 收到"


class FakeRouter:
    def get_llm(self, purpose: str) -> FakeLLM:
        return FakeLLM()


class RecordingMemory:
    def __init__(self) -> None:
        self.turns: list[tuple[str, str, str]] = []

    async def get_relevant(self, session_id: str, query: str, limit: int = 8) -> list[str]:
        return []

    async def append_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.turns.append((session_id, role, content))


class FakeTools:
    def list_tool_names(self) -> list[str]:
        return []

    async def invoke(self, name: str, arguments: dict[str, Any]) -> str:
        return ""


class FakeTracer:
    def new_trace_id(self) -> str:
        return "t1"

    def start_span(self, *args: Any, **kwargs: Any) -> object:
        return object()

    def end_span(self, span: Any, error: BaseException | None = None) -> None:
        return None

    def log_event(self, trace_id: str, name: str, payload: dict[str, Any]) -> None:
        return None


@pytest.mark.asyncio
async def test_orchestrator_appends_user_and_assistant_turns() -> None:
    memory = RecordingMemory()
    orchestrator = AgentOrchestrator(
        config={"enable_reflection": False, "react_max_steps": 1},
        model_router=FakeRouter(),
        memory_manager=memory,
        tool_registry=FakeTools(),
        tracer=FakeTracer(),
    )

    response = await orchestrator.run("我的偏好是简洁", session_id="s1")

    assert response.success
    assert memory.turns[0][1] == "user"
    assert memory.turns[0][2] == "我的偏好是简洁"
    assert memory.turns[-1][1] == "assistant"
    assert memory.turns[-1][2] == "收到"
