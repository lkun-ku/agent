# -*- coding: utf-8 -*-
"""短期记忆：窗口压缩、token 触发与 LLM 失败退化。"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.memory.short_term import ShortTermMemory
from app.models.enums import MessageRole
from app.models.schemas import Message


class FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, list[str]] = {}
        self.kv: dict[str, str] = {}

    async def set(self, key: str, value: str, nx: bool = False, ex: int | None = None) -> bool | None:
        if nx and key in self.kv:
            return None
        self.kv[key] = value
        return True

    async def rpush(self, key: str, value: str) -> None:
        self.data.setdefault(key, []).append(value)

    async def llen(self, key: str) -> int:
        return len(self.data.get(key, []))

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        values = self.data.get(key, [])
        if end == -1:
            end = len(values) - 1
        return values[start : end + 1]

    async def delete(self, key: str) -> None:
        self.data.pop(key, None)
        self.kv.pop(key, None)


class FakeLLM:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    async def ainvoke(self, prompt: Any, **kwargs: Any) -> str:
        self.calls += 1
        if self.fail:
            raise RuntimeError("llm down")
        return "压缩摘要"


def message(index: int, content: str | None = None) -> Message:
    return Message(
        role=MessageRole.USER,
        content=content or f"第 {index} 条消息",
    )


@pytest.mark.asyncio
async def test_mark_once_is_idempotent() -> None:
    memory = ShortTermMemory(FakeRedis(), FakeLLM())

    assert await memory.mark_once("k") is True
    assert await memory.mark_once("k") is False

    await memory.forget_key("k")

    assert await memory.mark_once("k") is True


@pytest.mark.asyncio
async def test_window_overflow_triggers_summary() -> None:
    redis = FakeRedis()
    llm = FakeLLM()
    memory = ShortTermMemory(redis, llm, window_size=2, max_tokens=100_000)

    for i in range(4):
        await memory.add_message("s1", message(i))

    history = await memory.get_history("s1")

    assert len(history) == 3
    assert history[0].role is MessageRole.SYSTEM
    assert "[历史摘要]" in history[0].content
    assert llm.calls >= 1


@pytest.mark.asyncio
async def test_token_threshold_triggers_summary() -> None:
    memory = ShortTermMemory(FakeRedis(), FakeLLM(), window_size=100, max_tokens=5)

    await memory.add_message("s1", message(1, "很长的内容" * 10))
    assert len(await memory.get_history("s1")) == 1

    await memory.add_message("s1", message(2, "另一段很长的内容" * 10))

    history = await memory.get_history("s1")
    assert history[0].role is MessageRole.SYSTEM
    assert "[历史摘要]" in history[0].content


@pytest.mark.asyncio
async def test_summary_failure_falls_back_to_truncation() -> None:
    memory = ShortTermMemory(
        FakeRedis(), FakeLLM(fail=True), window_size=2, max_tokens=100_000
    )

    for i in range(3):
        await memory.add_message("s1", message(i))

    history = await memory.get_history("s1")

    assert history[0].role is MessageRole.SYSTEM
    assert "第 0 条消息" in history[0].content
    assert len(history) == 3
