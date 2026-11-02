"""退款运营接口：提交测试订单、查询处理结果、查看人工任务。"""

from __future__ import annotations

import pathlib
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.tools import get_tool_registry
from app.core.tools.refund.agent_service import AgentService
from app.core.tools.refund.schemas import AgentRequest, AgentResponse
from app.core.tools.refund.tool import RefundTool
from app.domain.refund.activities.ingest import load_dataset

router = APIRouter(prefix="/refunds", tags=["refund-ops"])
page_router = APIRouter(tags=["refund-ops"])

_STATIC_DIR = pathlib.Path(__file__).resolve().parents[2] / "static"

_NO_STORE = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


class RefundSubmitRequest(BaseModel):
    """退款订单提交请求；三选一：record / refund_id / order_id。"""

    request_id: str = Field(default="", max_length=128)
    refund_id: str = Field(default="", max_length=128)
    order_id: str = Field(default="", max_length=128)
    record: dict[str, Any] | None = Field(default=None, description="完整退款订单快照")


def get_refund_agent_service() -> AgentService:
    """复用退款工具的进程级服务，避免运营接口重复创建连接池。"""
    settings = get_settings()
    if not settings.refund_enabled:
        raise HTTPException(
            status_code=503,
            detail="退款工具未启用，请设置 REFUND_ENABLED=true",
        )

    try:
        tool = get_tool_registry().get_tool("refund")
    except KeyError as exc:
        raise HTTPException(
            status_code=503,
            detail="退款工具未注册",
        ) from exc

    if not isinstance(tool, RefundTool):
        raise HTTPException(status_code=503, detail="退款工具类型异常")
    return tool.get_service()


def _admin_payload(
    service: AgentService,
    *,
    response: AgentResponse | None = None,
    case: Any = None,
) -> dict[str, Any]:
    """组装运营后台响应：出站结果 + 内部 CaseView + 全局统计。"""
    return {
        "response": response.to_dict() if response is not None else None,
        "case": case.to_dict() if case is not None else None,
        "stats": service.refund.stats(),
    }


@router.post("", summary="提交退款订单并执行自动化处理")
def submit_refund(
    payload: RefundSubmitRequest,
    service: AgentService = Depends(get_refund_agent_service),
) -> dict[str, Any]:
    """提供完整订单快照，或使用已有 refund_id / order_id。"""
    request = AgentRequest.from_payload(payload.model_dump(mode="json"))
    request.validate()
    try:
        response = service.submit(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    case = (
        service.refund.get_case(response.case_id)
        if response.case_id
        else None
    )
    return _admin_payload(service, response=response, case=case)


@router.get("/tasks", summary="查看人工审核/纠纷/举证任务")
def list_refund_tasks(
    service: AgentService = Depends(get_refund_agent_service),
) -> dict[str, Any]:
    """返回当前待人工处理的退款任务和全局统计。"""
    tasks = service.tasks()
    return {
        "tasks": [task.to_dict() for task in tasks],
        "stats": service.refund.stats(),
    }


@router.get("/templates", summary="查看可用的退款测试场景模板")
def refund_templates(
    service: AgentService = Depends(get_refund_agent_service),
) -> dict[str, Any]:
    """读取 data/refund 样例数据，供后台页面一键填入。"""
    settings = get_settings()
    dataset = load_dataset(data_dir=settings.refund_data_dir)
    templates = [
        {
            "refund_id": record.refund_id,
            "order_id": record.order_id,
            "scenario": record.scenario,
            "scenario_name": record.scenario_name,
            "expected_action": record.expected_action.value,
            "record": asdict(record),
        }
        for record in dataset.records
    ]
    return {"templates": templates}


@router.get("/{case_id}", summary="查询退款处理结果与内部细节")
def get_refund_case(
    case_id: str,
    service: AgentService = Depends(get_refund_agent_service),
) -> dict[str, Any]:
    """按售后单号查询状态、金额、规则命中、风险等级与人工任务。"""
    try:
        case = service.refund.get_case(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _admin_payload(service, case=case)


@page_router.get("/ops/refunds", include_in_schema=False, response_class=HTMLResponse)
def refund_admin_page() -> HTMLResponse:
    """退款运营后台页面。"""
    return HTMLResponse(
        (_STATIC_DIR / "refund-admin.html").read_text(encoding="utf-8"),
        headers=_NO_STORE,
    )
