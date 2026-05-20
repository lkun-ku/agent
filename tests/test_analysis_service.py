# -*- coding: utf-8 -*-
"""AnalysisService：分析工具集、提示词与 run 行为。"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.infrastructure.trace.tracer import Tracer
from app.services.analysis_service import ANALYSIS_SYSTEM_PROMPT, AnalysisService


class FakeRouter:
    async def chat(self, messages, **kwargs: Any) -> Any:
        return SimpleNamespace(content="Thought: 直接回答\nFinal Answer: 42")


class FakeFactory:
    def __call__(self) -> Any:  # pragma: no cover - 不应被调用
        raise AssertionError("最终回答路径不应访问数据库")


@pytest.mark.asyncio
async def test_tool_set_and_run() -> None:
    service = AnalysisService(FakeRouter(), FakeFactory(), Tracer())

    assert set(service.tool_names) == {
        "calculator",
        "database_query",
        "schema_inspect",
    }

    response = await service.run("这个月销售额是多少", session_id="s1")

    assert response.success
    assert response.answer == "42"


def test_prompt_requires_schema_and_readonly() -> None:
    assert "schema_inspect" in ANALYSIS_SYSTEM_PROMPT
    assert "只读" in ANALYSIS_SYSTEM_PROMPT
