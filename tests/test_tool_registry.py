# -*- coding: utf-8 -*-
"""P0-2：ToolRegistry 必须提供 list_tool_names / invoke，且 invoke 永不抛异常。"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.tools.base import BaseTool, ToolParameter
from app.core.tools.builtin.calculator import CalculatorTool
from app.core.tools.registry import ToolRegistry


class BoomTool(BaseTool):
    name = "boom"
    description = "总是失败的工具"

    def __init__(self) -> None:
        super().__init__()
        self.parameters = [ToolParameter(name="text", type="string", required=True)]

    async def execute(self, **kwargs: Any) -> Any:
        raise RuntimeError("boom")


@pytest.fixture()
def registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(CalculatorTool())
    reg.register(BoomTool())
    return reg


def test_list_tool_names(registry: ToolRegistry) -> None:
    assert registry.list_tool_names() == ["calculator", "boom"]


@pytest.mark.asyncio
async def test_invoke_executes_registered_tool(registry: ToolRegistry) -> None:
    result = await registry.invoke("calculator", {"expression": "1+2"})
    assert float(result) == 3.0


@pytest.mark.asyncio
async def test_invoke_unknown_tool_returns_hint(registry: ToolRegistry) -> None:
    result = await registry.invoke("nope", {})
    assert "未注册" in result
    assert "calculator" in result


@pytest.mark.asyncio
async def test_invoke_missing_required_arg_returns_schema(registry: ToolRegistry) -> None:
    result = await registry.invoke("calculator", {"expr": "1+2"})
    assert "缺少必填参数" in result
    assert "expression" in result
    assert "type" in result  # 回灌的是 JSON schema，而不是异常栈


@pytest.mark.asyncio
async def test_invoke_tool_error_is_converted_to_observation(registry: ToolRegistry) -> None:
    result = await registry.invoke("boom", {"text": "x"})
    assert "工具执行异常" in result
    assert "RuntimeError" in result
