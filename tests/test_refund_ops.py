"""退款运营后台 API 与页面回归。"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.routes import refund_ops
from app.core.tools.refund.schemas import AgentRequest, AgentResponse
from app.domain.refund.contracts import CaseView
from app.main import app


class FakeRefundService:
    def stats(self) -> dict[str, Any]:
        return {"total_cases": 1, "refunded_amount": 1.0}

    def get_case(self, case_id: str) -> CaseView:
        return CaseView(
            return_id=case_id,
            status="closed",
            status_label="已关闭",
            action_code="AUTO_APPROVE_AND_REFUND",
            action_label="审核通过并发起退款",
            amount=1.0,
            reply="ok",
            reason="quality",
            reason_label="质量问题",
            risk_tier="A",
            trust_score=95,
            rule_hits=[],
            pending=None,
            handoff={},
            actions=[],
        )


class FakeAgentService:
    def __init__(self) -> None:
        self.refund = FakeRefundService()
        self.submitted: AgentRequest | None = None

    def submit(self, request: AgentRequest) -> AgentResponse:
        self.submitted = request
        return AgentResponse(
            request_id=request.request_id,
            case_id="R-TEST",
            refund_id=request.refund_id,
            order_id=request.order_id,
            status="auto_completed",
            action="AUTO_APPROVE_AND_REFUND",
            action_label="审核通过并发起退款",
            amount=1.0,
            reply="ok",
            reason="quality",
            reason_label="质量问题",
        )

    def tasks(self) -> list[dict[str, Any]]:
        return []


@pytest.fixture
def fake_service() -> FakeAgentService:
    return FakeAgentService()


@pytest.fixture
def client(
    fake_service: FakeAgentService,
    monkeypatch: Any,
) -> TestClient:
    monkeypatch.setattr(
        "app.api.routes.refund_ops.get_tool_registry",
        lambda: None,
    )
    app.dependency_overrides[refund_ops.get_refund_agent_service] = (
        lambda: fake_service
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_refund_admin_page_is_served(client: TestClient) -> None:
    response = client.get("/ops/refunds")
    assert response.status_code == 200
    assert "退款运营后台" in response.text


def test_refund_templates_are_served(client: TestClient) -> None:
    response = client.get("/api/v1/refunds/templates")
    assert response.status_code == 200
    body = response.json()
    assert body["templates"]
    first = body["templates"][0]
    assert first["record"]["refund_id"]


def test_submit_refund_record_returns_admin_details(
    client: TestClient,
    fake_service: FakeAgentService,
) -> None:
    response = client.post(
        "/api/v1/refunds",
        json={
            "request_id": "req-1",
            "refund_id": "RF-TEST",
            "order_id": "ORDER-TEST",
        },
    )
    assert response.status_code == 200
    body = response.json()

    assert body["response"]["action"] == "AUTO_APPROVE_AND_REFUND"
    assert body["response"]["status"] == "auto_completed"
    assert body["case"]["return_id"] == "R-TEST"
    assert body["case"]["risk_tier"] == "A"
    assert body["stats"]["total_cases"] == 1
    assert fake_service.submitted is not None
    assert fake_service.submitted.refund_id == "RF-TEST"


def test_get_refund_case_returns_admin_details(client: TestClient) -> None:
    response = client.get("/api/v1/refunds/R-TEST")
    assert response.status_code == 200
    body = response.json()
    assert body["case"]["return_id"] == "R-TEST"
    assert body["stats"]["total_cases"] == 1


def test_refund_tasks_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/refunds/tasks")
    assert response.status_code == 200
    assert response.json()["tasks"] == []
