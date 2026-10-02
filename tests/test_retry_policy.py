"""LLM 重试策略：有限次数、指数退避、耗尽后终止。"""

from __future__ import annotations

from typing import Any

import pytest

from app.infrastructure.llm.model_router import LLMResponse, ModelConfig, ModelRouter


def _router(max_retries: int = 2) -> ModelRouter:
    return ModelRouter(
        [
            ModelConfig(
                model_id="test-model",
                api_key="sk-test",
                base_url="http://127.0.0.1:9/v1",
            )
        ],
        max_retries=max_retries,
        retry_base_delay=0.5,
        retry_max_delay=5.0,
    )


@pytest.mark.asyncio
async def test_transient_error_retries_with_backoff_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router = _router(max_retries=2)
    calls = 0
    sleeps: list[float] = []

    async def flaky(*args: Any, **kwargs: Any) -> LLMResponse:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise TimeoutError("transient")
        return LLMResponse(content="ok", model_id="test-model")

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(router, "_try_model", flaky)
    monkeypatch.setattr(
        "app.infrastructure.llm.model_router.asyncio.sleep",
        fake_sleep,
    )

    response = await router.chat([{"role": "user", "content": "hi"}])
    assert response.content == "ok"
    assert calls == 3
    assert sleeps == [0.5, 1.0]


@pytest.mark.asyncio
async def test_retry_exhaustion_terminates(monkeypatch: pytest.MonkeyPatch) -> None:
    router = _router(max_retries=2)
    calls = 0

    async def always_timeout(*args: Any, **kwargs: Any) -> LLMResponse:
        nonlocal calls
        calls += 1
        raise TimeoutError("down")

    async def no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(router, "_try_model", always_timeout)
    monkeypatch.setattr(
        "app.infrastructure.llm.model_router.asyncio.sleep",
        no_sleep,
    )

    with pytest.raises(RuntimeError, match="所有候选模型均不可用"):
        await router.chat([{"role": "user", "content": "hi"}])
    assert calls == 3


@pytest.mark.asyncio
async def test_non_retryable_error_does_not_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    router = _router(max_retries=2)
    calls = 0

    async def bad_request(*args: Any, **kwargs: Any) -> LLMResponse:
        nonlocal calls
        calls += 1
        raise ValueError("invalid request")

    monkeypatch.setattr(router, "_try_model", bad_request)

    with pytest.raises(RuntimeError):
        await router.chat([{"role": "user", "content": "hi"}])
    assert calls == 1
