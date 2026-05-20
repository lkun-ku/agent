# -*- coding: utf-8 -*-
"""ReAct 必须忽略模型自编的 Observation，并以真实工具结果继续。"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.agent.react_agent import ReActAgent


class ScriptedLLM:
    def __init__(self, answers: list[str]) -> None:
        self._answers = list(answers)
        self.calls: list[list[dict[str, str]]] = []

    async def acomplete(self, messages, **kwargs: Any) -> str:
        self.calls.append(list(messages))
        return self._answers.pop(0)


class FakeTools:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def invoke(self, name: str, arguments: dict[str, Any]) -> str:
        self.calls.append((name, arguments))
        return "REAL_60"


@pytest.mark.asyncio
async def test_action_wins_over_fabricated_observation() -> None:
    llm = ScriptedLLM(
        [
            "Thought: 查询\nAction: echo\nAction Input: {}\n"
            "Observation: FAKE_0\nThought: 结束\nFinal Answer: 0",
            "Thought: 使用真实结果\nFinal Answer: 60",
        ]
    )
    tools = FakeTools()
    agent = ReActAgent(llm=llm, tools=tools, memory=None, max_steps=2)

    result = await agent.run("问题", {"tool_names": ["echo"]})

    assert result.success
    assert result.final_answer == "60", "不能用自编结论覆盖真实工具结果"
    assert tools.calls == [("echo", {})]

    second_prompt = "\n".join(message["content"] for message in llm.calls[1])
    assert "REAL_60" in second_prompt
    assert "FAKE_0" not in second_prompt
