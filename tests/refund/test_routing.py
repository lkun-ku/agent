"""确认退款主链路仍是 Agent 工具，仅暴露受保护的运营后台接口。"""

from __future__ import annotations

from app.config import get_settings
from app.core.tools import get_tool_registry, reset_tool_registry
from app.main import app

ALLOWED_REFUND_PATHS = {
    "/api/v1/refunds",
    "/api/v1/refunds/{case_id}",
    "/api/v1/refunds/tasks",
    "/api/v1/refunds/templates",
}


def test_refund_routes_are_limited_to_ops_api() -> None:
    paths = set(app.openapi()["paths"])
    refund_paths = {path for path in paths if "refund" in path}
    assert refund_paths == ALLOWED_REFUND_PATHS


def test_no_legacy_standalone_refund_routes() -> None:
    paths = set(app.openapi()["paths"])
    legacy = {path for path in paths if path.startswith("/api/v1/refund/")}
    assert not legacy


def test_refund_tool_is_registered_when_enabled(
    monkeypatch,
) -> None:
    monkeypatch.setenv("REFUND_ENABLED", "true")
    get_settings.cache_clear()
    reset_tool_registry()
    try:
        registry = get_tool_registry()
        assert "refund" in registry.list_tool_names()
    finally:
        reset_tool_registry()
        monkeypatch.delenv("REFUND_ENABLED", raising=False)
        get_settings.cache_clear()
