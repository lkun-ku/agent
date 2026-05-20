# -*- coding: utf-8 -*-
"""P1-4：模型路由必须是进程级单例，否则熔断计数活不过一次请求。"""

from __future__ import annotations

import pytest

from app.api.routes.chat import get_model_router


class FakeSettings:
    openai_api_key = "test-key"
    openai_api_base = None
    openai_model = "gpt-test"


def test_get_model_router_returns_same_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.routes.chat.get_settings", lambda: FakeSettings())
    get_model_router.cache_clear()

    first = get_model_router()
    second = get_model_router()

    assert first is second
    get_model_router.cache_clear()
