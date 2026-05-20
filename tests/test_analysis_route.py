# -*- coding: utf-8 -*-
"""/analysis 路由：成功返回与失败 502。"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from app.api.routes import analysis as analysis_module
from app.core.agent.orchestrator import AgentResponse, IntentContext


class FakeService:
    def __init__(self, success: bool = True, answer: str = "销售额 100") -> None:
        self._success = success
        self._answer = answer

    async def run(self, question: str, session_id: str = "analysis") -> AgentResponse:
        return AgentResponse(
            answer=self._answer,
            mode_used="react",
            success=self._success,
            trace_id="t-analysis",
            intent=IntentContext(),
            steps=[{"phase": "sql", "row_count": 1}] if self._success else [],
            error=None if self._success else "SQL 无法生成",
        )


@pytest.mark.asyncio
async def test_analysis_returns_answer_and_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        analysis_module, "get_analysis_service", lambda: FakeService()
    )

    response = await analysis_module.analyze(
        analysis_module.AnalysisRequest(question="这个月销售额是多少")
    )

    assert response.answer == "销售额 100"
    assert response.trace_id == "t-analysis"
    assert response.steps[0]["phase"] == "sql"


@pytest.mark.asyncio
async def test_analysis_failure_returns_502(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        analysis_module,
        "get_analysis_service",
        lambda: FakeService(success=False, answer=""),
    )

    with pytest.raises(HTTPException) as exc_info:
        await analysis_module.analyze(
            analysis_module.AnalysisRequest(question="这个月销售额是多少")
        )

    assert exc_info.value.status_code == 502
    assert "SQL 无法生成" in str(exc_info.value.detail)
