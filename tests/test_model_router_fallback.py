# -*- coding: utf-8 -*-
"""模型路由：失败降级与熔断跳过。"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.infrastructure.llm.model_router import ModelConfig, ModelRouter


class FakeCompletions:
    def __init__(self, fail: bool) -> None:
        self.fail = fail

    async def create(self, **params: Any) -> Any:
        if self.fail:
            raise RuntimeError("model down")
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
            usage=None,
        )


class FakeClient:
    def __init__(self, fail: bool) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions(fail))


def make_router(threshold: int = 5) -> ModelRouter:
    router = ModelRouter(
        [
            ModelConfig(model_id="m1", api_key="k", priority=0),
            ModelConfig(model_id="m2", api_key="k", priority=1),
        ],
        failure_threshold=threshold,
        recovery_timeout=0.05,
    )
    router._clients = {  # type: ignore[attr-defined]
        "m1": FakeClient(True),
        "m2": FakeClient(False),
    }
    return router


@pytest.mark.asyncio
async def test_fallback_to_second_model() -> None:
    router = make_router(threshold=5)

    response = await router.chat([{"role": "user", "content": "hi"}])

    assert response.model_id == "m2"
    assert response.content == "ok"
    assert router.snapshot()["m1"]["failures"] == 1


@pytest.mark.asyncio
async def test_open_breaker_skips_failed_model() -> None:
    router = make_router(threshold=1)

    await router.chat([{"role": "user", "content": "hi"}])
    assert router.snapshot()["m1"]["state"] == "open"

    response = await router.chat([{"role": "user", "content": "hi"}])

    assert response.model_id == "m2"
    assert router.snapshot()["m1"]["failures"] == 1, "OPEN 期间不应继续累加失败"
