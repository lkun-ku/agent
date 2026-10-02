"""根路径页面回归测试：首页与聊天演示页可访问，且不污染 OpenAPI。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

# 不使用 with 上下文，避免触发 lifespan（无需数据库）
client = TestClient(app)


def test_index_returns_html() -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "企业级 AI Agent 服务" in resp.text
    assert "/docs" in resp.text


def test_chat_ui_returns_html() -> None:
    resp = client.get("/ui")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "/api/v1/chat" in resp.text
    assert "/api/v1/chat/stream" in resp.text


def test_pages_are_excluded_from_openapi() -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert "/" not in paths
    assert "/ui" not in paths
    assert "/api/v1/chat" in paths


def test_html_has_no_template_residue() -> None:
    """f-string 转义不应残留 {{ }} 字样。"""
    for path in ("/", "/ui"):
        body = client.get(path).text
        assert "{{" not in body
        assert "}}" not in body
