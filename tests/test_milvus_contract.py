# -*- coding: utf-8 -*-
"""P0-5：Milvus 适配器必须满足长期记忆与检索的字段契约，并提供 flush。"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

import app.infrastructure.vectordb.milvus_client as mod
from app.infrastructure.vectordb.milvus_client import MilvusManager


class FakeCollection:
    instances: list[FakeCollection] = []

    def __init__(self, name=None, schema=None, using=None) -> None:
        self.name = name
        self.schema = schema
        self.inserted: Any = None
        self.flushed = False
        FakeCollection.instances.append(self)

    def create_index(self, **kwargs: Any) -> None:
        return None

    def insert(self, data: Any) -> None:
        self.inserted = data

    def flush(self) -> None:
        self.flushed = True


@pytest.fixture()
def patched(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeCollection.instances.clear()
    monkeypatch.setattr(mod, "Collection", FakeCollection)
    monkeypatch.setattr(mod, "utility", SimpleNamespace(has_collection=lambda *a, **k: False))
    monkeypatch.setattr(mod, "connections", SimpleNamespace(connect=lambda **k: None))


@pytest.mark.asyncio
async def test_create_collection_includes_required_fields(patched: None) -> None:
    manager = MilvusManager()

    await manager.create_collection("docs", 4)

    collection = FakeCollection.instances[-1]
    names = {field.name for field in collection.schema.fields}
    assert {"id", "embedding", "text", "session_id", "meta"} <= names


@pytest.mark.asyncio
async def test_insert_writes_text_session_and_meta(patched: None) -> None:
    manager = MilvusManager()

    ids = await manager.insert(
        "docs",
        [[0.1, 0.2]],
        [{"id": "d1", "text": "你好", "session_id": "s1", "meta": {"k": "v"}}],
    )

    row = FakeCollection.instances[-1].inserted[0]
    assert ids == ["d1"]
    assert row["id"] == "d1"
    assert row["text"] == "你好"
    assert row["session_id"] == "s1"
    assert json.loads(row["meta"]) == {"k": "v"}
    assert FakeCollection.instances[-1].flushed is True


@pytest.mark.asyncio
async def test_flush_method_exists(patched: None) -> None:
    manager = MilvusManager()

    await manager.flush("docs")

    assert FakeCollection.instances[-1].flushed is True
