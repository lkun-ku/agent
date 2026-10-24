"""根路径页面：服务总览、聊天演示、离线文档与诊断页。

页面资产外置于 ``app/static``，Python 只负责服务端渲染点与响应头。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.shared.times import seconds_iso_now

router = APIRouter(tags=["web"], include_in_schema=False)

_STATIC_DIR = Path(__file__).resolve().parents[2] / "static"

# 页面禁用缓存：避免浏览器继续使用旧版页面。
_NO_STORE = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
    "X-Content-Type-Options": "nosniff",
}


def _html(name: str) -> str:
    return (_STATIC_DIR / name).read_text(encoding="utf-8")


@router.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    """服务总览页。"""
    return HTMLResponse(_html("index.html"), headers=_NO_STORE)


@router.get("/ui", response_class=HTMLResponse)
async def chat_ui() -> HTMLResponse:
    """内置聊天演示页。"""
    return HTMLResponse(_html("chat.html"), headers=_NO_STORE)


def _render_doc_list(app: Any) -> str:
    """服务端渲染接口列表，避免依赖前端脚本拉取 OpenAPI。"""
    from html import escape

    spec = app.openapi()
    groups: dict[str, list[str]] = {}
    for path, item in spec.get("paths", {}).items():
        for method, operation in item.items():
            tag = (operation.get("tags") or ["default"])[0]
            row = (
                f'<div class="ep" data-path="{escape(path)}" data-method="{method}">'
                f'<span class="m {method}">{method.upper()}</span>'
                f'<span class="p">{escape(path)}</span></div>'
            )
            groups.setdefault(tag, []).append(row)

    parts: list[str] = []
    for tag, rows in groups.items():
        parts.append(f'<div class="tag">{escape(tag)}</div>')
        parts.extend(rows)
    return "".join(parts)


def _docs_response(app: Any) -> HTMLResponse:
    """渲染离线 API 文档。"""
    return HTMLResponse(
        _html("docs.html").replace("__SERVER_LIST__", _render_doc_list(app)),
        headers=_NO_STORE,
    )


@router.get("/docs", response_class=HTMLResponse)
async def offline_docs(request: Request) -> HTMLResponse:
    """离线 API 文档：服务端渲染接口列表，不依赖任何 CDN。"""
    return _docs_response(request.app)


@router.get("/redoc", response_class=HTMLResponse)
async def offline_redoc(request: Request) -> HTMLResponse:
    """ReDoc 依赖 CDN，离线环境下返回自包含文档页。"""
    return _docs_response(request.app)


@router.get("/swagger", response_class=HTMLResponse)
@router.get("/api-docs", response_class=HTMLResponse)
async def docs_alias(request: Request) -> HTMLResponse:
    """/swagger、/api-docs 别名，等同 /docs（避免旧书签或习惯路径 404）。"""
    return _docs_response(request.app)


@router.get("/diag", response_class=HTMLResponse)
async def diagnostics(request: Request) -> HTMLResponse:
    """连通性诊断页：展示服务端请求信息并探测各接口可达性。"""
    info: dict[str, Any] = {
        "client_host": request.client.host if request.client else "unknown",
        "host_header": request.headers.get("host", ""),
        "user_agent": request.headers.get("user-agent", ""),
        "x_forwarded_for": request.headers.get("x-forwarded-for", ""),
        "server_time": seconds_iso_now(),
    }
    body = _html("diag.html").replace(
        "__INFO__", json.dumps(info, ensure_ascii=False, indent=2)
    )
    return HTMLResponse(body, headers=_NO_STORE)
