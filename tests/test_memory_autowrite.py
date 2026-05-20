# -*- coding: utf-8 -*-
"""长期记忆自动写入：用户表达“记住/偏好”等意图时落库，其余不写。"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.memory.manager import MemoryManager
from app.models.schemas import Message
from app.services.agent_service import MemoryManagerAdapter


class FakeLTM:
    def __init__(self) -> None:
        self.stored: list[tuple[str, str, dict[str, Any]]] = []
        self.contents: set[str] = set()

    async def store(self, session_id: str, content: str, metadata: dict[str, Any]) -> str:
        self.stored.append((session_id, content, metadata))
        self.contents.add(content)
        return "mem-1"

    async def exists(self, session_id: str, content: str) -> bool:
        return content in self.contents

    async def recall(self, *args: Any, **kwargs: Any) -> list[Any]:
        return []


class FakeSTM:
    def __init__(self) -> None:
        self.keys: set[str] = set()

    async def get_history(self, session_id: str) -> list[Message]:
        return []

    async def add_message(self, session_id: str, message: Message) -> None:
        return None

    async def mark_once(self, key: str, ttl: int = 0) -> bool:
        if key in self.keys:
            return False
        self.keys.add(key)
        return True

    async def forget_key(self, key: str) -> None:
        self.keys.discard(key)


class FakeManager:
    def __init__(self) -> None:
        self.saved: list[tuple[str, Message]] = []
        self.long: list[tuple[str, str, dict[str, Any] | None]] = []

    async def save(self, session_id: str, message: Message) -> None:
        self.saved.append((session_id, message))

    async def save_long_term(
        self,
        session_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        self.long.append((session_id, content, metadata))
        return "mem-1"


@pytest.mark.asyncio
async def test_manager_save_long_term_delegates() -> None:
    ltm = FakeLTM()
    manager = MemoryManager(FakeSTM(), ltm)  # type: ignore[arg-type]

    memory_id = await manager.save_long_term("s1", "记住：偏好简洁", {"source": "auto"})

    assert memory_id == "mem-1"
    assert ltm.stored[0][1] == "记住：偏好简洁"
    assert ltm.stored[0][2]["source"] == "auto"


@pytest.mark.asyncio
async def test_manager_save_long_term_deduplicates() -> None:
    ltm = FakeLTM()
    manager = MemoryManager(FakeSTM(), ltm)  # type: ignore[arg-type]

    first = await manager.save_long_term("s1", "记住：偏好简洁", {})
    second = await manager.save_long_term("s1", "记住：偏好简洁", {})

    assert first == "mem-1"
    assert second is None
    assert len(ltm.stored) == 1


@pytest.mark.asyncio
async def test_manager_skips_content_already_in_long_term() -> None:
    ltm = FakeLTM()
    ltm.contents.add("记住：偏好简洁")
    manager = MemoryManager(FakeSTM(), ltm)  # type: ignore[arg-type]

    result = await manager.save_long_term("s1", "记住：偏好简洁", {})

    assert result is None
    assert ltm.stored == []


@pytest.mark.asyncio
async def test_adapter_auto_writes_only_trigger_user_messages() -> None:
    manager = FakeManager()
    adapter = MemoryManagerAdapter(manager)

    await adapter.append_turn("s1", "user", "请记住我的偏好是简洁")
    await adapter.append_turn("s1", "user", "你好")
    await adapter.append_turn("s1", "user", "我叫什么？")
    await adapter.append_turn("s1", "user", "我的偏好是什么？")
    await adapter.append_turn("s1", "assistant", "请记住这条")

    assert len(manager.saved) == 5
    assert len(manager.long) == 1
    assert manager.long[0][1] == "请记住我的偏好是简洁"
    assert manager.long[0][2]["source"] == "auto"
