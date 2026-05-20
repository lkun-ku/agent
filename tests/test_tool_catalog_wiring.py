# -*- coding: utf-8 -*-
"""编排器必须把工具描述与参数传进 ReAct 提示，而不只是工具名。"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.core.tools.builtin.calculator import CalculatorTool
from app.core.tools.registry import ToolRegistry
from app.infrastructure.trace.tracer import Tracer
from app.services.agent_service import AgentService


class CapturingRouter:
    def __init__(self) -> None:
        self.prompts: list[list[dict[str, str]]] = []

    async def chat(self, messages, **kwargs: Any) -> Any:
        self.prompts.append(list(messages))
        return SimpleNamespace(content="Thought: 直接回答\nFinal Answer: done")


@pytest.mark.asyncio
async def test_orchestrator_passes_tool_catalog_to_react() -> None:
    router = CapturingRouter()
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    service = AgentService(
        model_router=router,
        tools=registry,
        tracer=Tracer(),
        config={"enable_reflection": False, "react_max_steps": 1},
    )

    await service.run("1+1 等于几", session_id="s1")

    prompt = "\n".join(message["content"] for message in router.prompts[0])
    assert "expression" in prompt, "工具参数应出现在 ReAct 提示中"
    assert "计算" in prompt
