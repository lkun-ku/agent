# -*- coding: utf-8 -*-
"""P1-5：反思打分低时必须触发一次带批评的重答，而不是只把分数放进响应。"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.agent.orchestrator import AgentOrchestrator, IntentContext


class ScriptedLLM:
    def __init__(self, answers: list[str]) -> None:
        self._answers = list(answers)
        self.calls: list[list[dict[str, str]]] = []

    async def acomplete(self, messages, **kwargs: Any) -> str:
        self.calls.append(list(messages))
        return self._answers.pop(0)


class FakeRouter:
    def __init__(self, llm: ScriptedLLM) -> None:
        self._llm = llm

    def get_llm(self, purpose: str) -> ScriptedLLM:
        return self._llm


class FakeMemory:
    async def get_relevant(self, session_id: str, query: str, limit: int = 8) -> list[str]:
        return []

    async def append_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        return None


class FakeTools:
    def list_tool_names(self) -> list[str]:
        return []

    async def invoke(self, name: str, arguments: dict[str, Any]) -> str:
        return ""


class FakeTracer:
    def new_trace_id(self) -> str:
        return "trace-1"

    def start_span(self, *args: Any, **kwargs: Any) -> object:
        return object()

    def end_span(self, span: Any, error: BaseException | None = None) -> None:
        return None

    def log_event(self, trace_id: str, name: str, payload: dict[str, Any]) -> None:
        return None


@pytest.mark.asyncio
async def test_low_quality_reflection_triggers_one_retry() -> None:
    llm = ScriptedLLM(
        [
            "Thought: 直接回答\nFinal Answer: 初版答案",
            '{"quality_score": 30, "is_complete": false, "likely_hallucination": false, '
            '"suggestions": ["补充来源"], "summary": "信息不足"}',
            "Thought: 补充后回答\nFinal Answer: 改进答案",
        ]
    )
    orchestrator = AgentOrchestrator(
        config={
            "enable_reflection": True,
            "react_max_steps": 1,
            "reflection_min_quality": 60,
        },
        model_router=FakeRouter(llm),
        memory_manager=FakeMemory(),
        tool_registry=FakeTools(),
        tracer=FakeTracer(),
    )

    response = await orchestrator.run(
        "解释一下向量索引",
        session_id="s1",
        mode="react",
        intent=IntentContext(confidence=0.9),
    )

    assert response.success
    assert response.answer == "改进答案"
    assert len(llm.calls) == 3, "应为：回答 → 反思 → 重答"
    retry_text = "\n".join(m["content"] for m in llm.calls[2])
    assert "补充来源" in retry_text
