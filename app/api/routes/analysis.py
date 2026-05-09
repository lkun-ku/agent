"""经营分析 Agent 的 HTTP 入口。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.routes.chat import _tracer, get_model_router
from app.infrastructure.database import session as db_session
from app.services.analysis_service import AnalysisService

router = APIRouter(tags=["analysis"])
_service: AnalysisService | None = None


class AnalysisRequest(BaseModel):
    """分析请求。"""

    question: str = Field(..., min_length=1, description="自然语言问题")
    session_id: str = Field(default="analysis", description="会话标识")


class AnalysisResponse(BaseModel):
    """分析结果。"""

    answer: str
    steps: list[dict[str, Any]] = Field(default_factory=list)
    trace_id: str
    mode: str


def get_analysis_service() -> AnalysisService:
    """进程级单例；数据库未初始化时返回 503。"""
    global _service
    if _service is None:
        if db_session.async_session_factory is None:
            raise HTTPException(status_code=503, detail="数据库未初始化")
        _service = AnalysisService(
            get_model_router(),
            db_session.async_session_factory,
            _tracer,
        )
    return _service


@router.post("/analysis", response_model=AnalysisResponse)
async def analyze(request: AnalysisRequest) -> AnalysisResponse:
    """自然语言问数：返回结论、执行步骤与 trace。"""
    service = get_analysis_service()
    response = await service.run(request.question, request.session_id)

    if not response.success or not response.answer.strip():
        raise HTTPException(
            status_code=502,
            detail=f"分析失败: {response.error or '无有效回答'}",
        )

    return AnalysisResponse(
        answer=response.answer,
        steps=response.steps,
        trace_id=response.trace_id,
        mode=response.mode_used,
    )
