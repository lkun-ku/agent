# -*- coding: utf-8 -*-
"""P1-2：ReAct 的提示里必须带工具描述与参数，而不只是工具名。"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.agent.react_agent import ReActAgent


class CapturingLLM:
    def __init__(self, answer: str = "Thought: 已有答案\nFinal Answer: ok") -> None:
        self._answer = answer
        self.calls: list[list[dict[str, str]]] = []

    async def acomplete(self, messages, **kwargs) -> str:
        self.calls.append(list(messages))
        return self._answer


class FakeTools:
    async def invoke(self, name: str, arguments: dict[str, Any]) -> str:
        return "unused"


@pytest.mark.asyncio
async def test_prompt_uses_tool_catalog_from_context() -> None:
    llm = CapturingLLM()
    agent = ReActAgent(llm=llm, tools=FakeTools(), memory=None, max_steps=1)

    await agent.run(
        "1+2 等于几",
        {
            "tool_names": ["calculator"],
            "tool_catalog": "- calculator: 计算数学表达式（参数: expression: string）",
        },
    )

    assert llm.calls, "应当至少调用一次 LLM"
    user_prompt = llm.calls[0][1]["content"]
    assert "expression" in user_prompt
    assert "计算数学表达式" in user_prompt


@pytest.mark.asyncio
async def test_prompt_falls_back_to_tool_names_without_catalog() -> None:
    llm = CapturingLLM()
    agent = ReActAgent(llm=llm, tools=FakeTools(), memory=None, max_steps=1)

    await agent.run("hi", {"tool_names": ["calculator"]})

    user_prompt = llm.calls[0][1]["content"]
    assert "- calculator" in user_prompt
