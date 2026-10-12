"""Phase 3：可观测性、健康矩阵、指标与保留策略回归。"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.infrastructure.database.repositories import redact_payload
from app.main import app


def test_redact_payload_masks_nested_credentials() -> None:
    payload = {
        "user": {"name": "alice", "api_key": "secret", "token": "abc"},
        "items": [{"authorization": "Bearer x", "note": "safe"}],
        "password": "p",
    }
    redacted = redact_payload(payload)
    assert redacted["user"]["name"] == "alice"
    assert redacted["user"]["api_key"] == "***"
    assert redacted["user"]["token"] == "***"
    assert redacted["items"][0]["authorization"] == "***"
    assert redacted["items"][0]["note"] == "safe"
    assert redacted["password"] == "***"


def test_metrics_endpoint_exposes_prometheus_format() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/metrics")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/plain")
        assert "enterprise_agent_http_requests_total" in response.text


def test_version_endpoint_reports_runtime_metadata() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/version")
        assert response.status_code == 200
        body = response.json()
        assert body["app_name"]
        assert body["app_version"]
        assert body["app_env"]


def test_http_middleware_binds_trace_context() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/health",
            headers={"x-trace-id": "trace-ctx", "x-conversation-id": "conv-ctx"},
        )
        assert response.status_code == 200
        assert response.headers["x-trace-id"] == "trace-ctx"
        assert response.headers["x-conversation-id"] == "conv-ctx"


def test_ready_endpoint_returns_dependency_matrix() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health/ready")
        assert response.status_code in {200, 503}
        body: dict[str, Any] = response.json()
        assert set(body) >= {"status", "database", "redis", "milvus", "app_env"}
        assert body["database"] in {"up", "down"}
        assert body["redis"] in {"up", "down", "skipped"}
        assert body["milvus"] in {"up", "down", "skipped"}
