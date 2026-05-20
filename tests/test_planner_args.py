# -*- coding: utf-8 -*-
"""P1-1：Plan-and-Execute 的工具步骤必须能传结构化参数，而不是只有 hint。"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.agent.planner import PlannerAgent, SubTask


class RecordingTools:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def invoke(self, name: str, arguments: dict[str, Any]) -> str:
        self.calls.append((name, arguments))
        return "3.0"


class DummyLLM:
    async def acomplete(self, messages, **kwargs) -> str:
        return "最终答案"


@pytest.mark.asyncio
async def test_execute_passes_structured_tool_args() -> None:
    tools = RecordingTools()
    planner = PlannerAgent(llm=DummyLLM(), tools=tools, memory=None)
    plan = [
        SubTask(
            id="t1",
            title="计算 1+2",
            description="",
            action_type="tool",
            tool_name="calculator",
            tool_args={"expression": "1+2"},
        )
    ]

    result = await planner.execute(plan, "1+2 等于几", session_id="s1", tool_names=["calculator"])

    assert result.success
    assert tools.calls == [("calculator", {"expression": "1+2"})]


@pytest.mark.asyncio
async def test_execute_falls_back_to_hint_when_tool_args_missing() -> None:
    tools = RecordingTools()
    planner = PlannerAgent(llm=DummyLLM(), tools=tools, memory=None)
    plan = [
        SubTask(
            id="t1",
            title="计算",
            description="",
            action_type="tool",
            tool_name="calculator",
            tool_args_hint="expression=1+2",
        )
    ]

    await planner.execute(plan, "1+2 等于几", session_id="s1", tool_names=["calculator"])

    assert tools.calls[0][1]["hint"] == "expression=1+2"
    assert tools.calls[0][1]["user_query"] == "1+2 等于几"
