"""模型路由回归测试：思考模式透传与降级。"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.infrastructure.llm.model_router import ModelConfig, ModelRouter, build_thinking_extra


class _CapturingClient:
    """记录 chat.completions.create 的入参。"""

    def __init__(self) -> None:
        self.params: dict[str, Any] = {}
        outer = self

        class _Completions:
            async def create(self, **kwargs: Any) -> Any:
                outer.params = kwargs
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
                    usage=SimpleNamespace(
                        prompt_tokens=1, completion_tokens=1, total_tokens=2
                    ),
                )

        self.chat = SimpleNamespace(completions=_Completions())


def _router(thinking: bool | None) -> tuple[ModelRouter, _CapturingClient]:
    cfg = ModelConfig(
        model_id="test-model",
        api_key="sk-test",
        base_url="http://127.0.0.1:9/v1",
        thinking=thinking,
    )
    router = ModelRouter([cfg])
    client = _CapturingClient()
    router._clients["test-model"] = client  # type: ignore[assignment]
    return router, client


def test_build_thinking_extra() -> None:
    assert build_thinking_extra(True) == {"thinking": {"type": "enabled"}}
    assert build_thinking_extra(False) == {"thinking": {"type": "disabled"}}


async def test_thinking_disabled_is_forwarded() -> None:
    router, client = _router(thinking=False)
    await router.chat([{"role": "user", "content": "hi"}])
    assert client.params["extra_body"] == {"thinking": {"type": "disabled"}}
    assert client.params["model"] == "test-model"


async def test_thinking_enabled_is_forwarded() -> None:
    router, client = _router(thinking=True)
    await router.chat([{"role": "user", "content": "hi"}])
    assert client.params["extra_body"] == {"thinking": {"type": "enabled"}}


async def test_thinking_none_sends_no_extra_body() -> None:
    router, client = _router(thinking=None)
    await router.chat([{"role": "user", "content": "hi"}])
    assert "extra_body" not in client.params


async def test_caller_extra_body_is_merged() -> None:
    router, client = _router(thinking=False)
    await router.chat(
        [{"role": "user", "content": "hi"}],
        extra_body={"custom": 1},
    )
    assert client.params["extra_body"] == {"custom": 1, "thinking": {"type": "disabled"}}


async def test_empty_configs_rejected() -> None:
    with pytest.raises(ValueError):
        ModelRouter([])
