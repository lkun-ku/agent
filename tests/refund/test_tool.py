"""退款工具与 Agent 意图调用链测试。"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlite_store import Store

from app.api.routes import chat as chat_route
from app.core.chat import service as chat_service
from app.core.intent.recognizer import IntentRecognizer, is_refund_action
from app.core.tools import ToolRegistry
from app.core.tools.refund import AgentService, RefundService, RefundTool
from app.core.tools.schemas import RefundToolResult
from app.domain.refund.activities.ingest import load_dataset

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "refund"


def _tool(tmp_path: Path) -> tuple[RefundTool, str]:
    dataset = load_dataset(data_dir=DATA)
    record = dataset.records[0]
    service = AgentService(
        RefundService(Store(tmp_path / "tool.db"), dataset=dataset)
    )
    return RefundTool(service), record.refund_id


@pytest.mark.asyncio
async def test_refund_tool_executes_workflow(tmp_path: Path) -> None:
    tool, refund_id = _tool(tmp_path)
    try:
        result = await tool.execute(refund_id=refund_id, reason="我要退款")
        assert result.case_id
        assert result.action
        assert result.status in {
            "auto_completed",
            "need_human",
            "waiting_return",
            "rejected",
            "processing",
        }
        assert result.reply
    finally:
        tool.close()


@pytest.mark.asyncio
async def test_refund_tool_without_order_is_a_clarification() -> None:
    result = await RefundTool().execute(reason="我要退款")
    assert result.status == "need_info"
    assert result.action == "NEED_ORDER"


@pytest.mark.asyncio
async def test_refund_tool_rejects_wrong_argument_types() -> None:
    tool = RefundTool()
    record_result = await tool.execute(record=[])
    order_result = await tool.execute(order_id=[])
    assert record_result.action == "INVALID_ARGUMENT"
    assert order_result.action == "INVALID_ARGUMENT"


@pytest.mark.asyncio
async def test_intent_routes_to_refund_tool(tmp_path: Path) -> None:
    tool, refund_id = _tool(tmp_path)
    registry = ToolRegistry()
    registry.register(tool)
    try:
        result = await registry.invoke("refund", {"refund_id": refund_id})
        assert isinstance(result, RefundToolResult)
        assert result.case_id
    finally:
        registry.close()


@pytest.mark.asyncio
async def test_refund_intent_and_policy_are_distinguished() -> None:
    recognizer = IntentRecognizer()
    action = await recognizer.recognize("我要退款，订单号 3821467092533817042")
    assert action.intent == "售后"
    assert action.sub_intent == "退款"
    assert action.slots["order_id"] == "3821467092533817042"
    assert is_refund_action("我要退款") is True

    policy = await recognizer.recognize("退货政策是什么")
    assert policy.intent in {"问答", "售后"}
    assert is_refund_action("退货政策是什么") is False


def test_chat_entry_uses_refund_tool_without_llm_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool, refund_id = _tool(tmp_path)
    registry = ToolRegistry()
    registry.register(tool)
    monkeypatch.setattr(
        chat_service,
        "get_tool_registry",
        lambda: registry,
    )
    monkeypatch.setattr(
        chat_service,
        "get_settings",
        lambda: type(
            "S",
            (),
            {
                "refund_enabled": True,
                "openai_api_key": "",
                "conversation_persistence_enabled": False,
                "trace_persistence_enabled": False,
            },
        )(),
    )
    app = FastAPI()
    app.include_router(chat_route.router, prefix="/api/v1")
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/chat",
            json={
                "messages": [
                    {
                        "role": "user",
                        "content": f"我要退款，退款单号 {refund_id}",
                    }
                ]
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["tool"] == "refund"
        assert body["tool_result"]["case_id"]
        assert body["content"]
    finally:
        registry.close()
