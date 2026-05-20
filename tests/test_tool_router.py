# -*- coding: utf-8 -*-
"""工具路由：按查询意图挑选工具，无命中时兜底返回。"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.tools.base import BaseTool
from app.core.tools.router import ToolRouter


class FakeTool(BaseTool):
    def __init__(self, name: str, description: str) -> None:
        super().__init__()
        self.name = name
        self.description = description

    async def execute(self, **kwargs: Any) -> str:
        return ""


def tools() -> list[BaseTool]:
    return [
        FakeTool("calculator", "计算数学表达式"),
        FakeTool("search", "搜索网页与新闻"),
        FakeTool("database_query", "执行只读 SQL 查询"),
    ]


@pytest.mark.asyncio
async def test_route_prefers_calculator() -> None:
    picked = await ToolRouter(max_tools=1).route("帮我计算 1+2", tools())

    assert picked[0].name == "calculator"


@pytest.mark.asyncio
async def test_route_prefers_search() -> None:
    picked = await ToolRouter(max_tools=1).route("搜索一下今天的新闻", tools())

    assert picked[0].name == "search"


@pytest.mark.asyncio
async def test_route_falls_back_when_no_keyword() -> None:
    picked = await ToolRouter(max_tools=2).route("你好", tools())

    assert len(picked) == 2
