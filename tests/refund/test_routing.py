"""确认退款只作为 Agent 工具存在，不暴露独立 HTTP 资源。"""

from __future__ import annotations

from app.config import get_settings
from app.core.tools import get_tool_registry, reset_tool_registry
from app.main import app


def test_no_standalone_refund_routes() -> None:
    paths = set(app.openapi()["paths"])
    assert not {path for path in paths if "refund" in path}


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
