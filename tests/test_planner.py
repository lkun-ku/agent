"""规划与编排回归测试：计划解析失败必须可感知并降级。"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.core.agent.orchestrator import AgentOrchestrator, InMemoryTracer
from app.core.agent.planner import PlannerAgent, PlanningError


class _ScriptedLLM:
    """按调用顺序返回预设输出。"""

    def __init__(self, outputs: list[str]) -> None:
        self._outputs = outputs
        self.calls = 0

    async def acomplete(self, messages, **kwargs: Any) -> str:
        idx = min(self.calls, len(self._outputs) - 1)
        self.calls += 1
        return self._outputs[idx]


class _StubRouter:
    def __init__(self, llm: Any) -> None:
        self._llm = llm

    def get_llm(self, purpose: str) -> Any:
        return self._llm


class _StubMemory:
    async def get_relevant(self, session_id: str, query: str, limit: int = 8) -> list[str]:
        return []

    async def append_turn(self, session_id, role, content, metadata=None) -> None:
        return None


class _StubTools:
    def list_tool_names(self) -> list[str]:
        return []

    async def invoke(self, name: str, arguments: dict[str, Any]) -> str:
        return ""


async def test_plan_raises_on_unparsable_output() -> None:
    planner = PlannerAgent(_ScriptedLLM(["这不是 JSON"]), _StubTools(), None)
    with pytest.raises(PlanningError):
        await planner.plan("随便问点什么")


async def test_plan_raises_on_empty_subtasks() -> None:
    planner = PlannerAgent(_ScriptedLLM([json.dumps({"subtasks": []})]), _StubTools(), None)
    with pytest.raises(PlanningError):
        await planner.plan("随便问点什么")


async def test_run_with_replan_returns_failure_instead_of_fake_answer() -> None:
    planner = PlannerAgent(_ScriptedLLM(["这不是 JSON"]), _StubTools(), None)
    result = await planner.run_with_replan("目标", "s1")
    assert result.success is False
    assert result.final_answer == ""
    assert "计划生成失败" in (result.error or "")


async def test_orchestrator_degrades_to_react_when_plan_fails() -> None:
    llm = _ScriptedLLM(["这不是 JSON", "Thought: 直接回答\nFinal Answer: 降级成功"])
    orchestrator = AgentOrchestrator(
        {"enable_reflection": False, "fallback_react_on_plan_failure": True},
        _StubRouter(llm),
        _StubMemory(),
        _StubTools(),
        InMemoryTracer(),
    )
    resp = await orchestrator.run("随便问", "s2", mode="plan_execute")
    assert resp.success is True
    assert resp.degraded is True
    assert resp.mode_used == "react"
    assert resp.answer == "降级成功"


async def test_orchestrator_react_success() -> None:
    llm = _ScriptedLLM(["Thought: 无需工具\nFinal Answer: 42"])
    orchestrator = AgentOrchestrator(
        {"enable_reflection": False},
        _StubRouter(llm),
        _StubMemory(),
        _StubTools(),
        InMemoryTracer(),
    )
    resp = await orchestrator.run("1+2*3", "s3", mode="react")
    assert resp.success is True
    assert resp.answer == "42"
    assert resp.mode_used == "react"
