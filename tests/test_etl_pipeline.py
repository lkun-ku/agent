# -*- coding: utf-8 -*-
"""ETL 流水线：分块结果与 on_chunks 异步钩子。"""

from __future__ import annotations

from typing import Any

import pytest

from app.etl.pipeline import ETLPipeline


@pytest.mark.asyncio
async def test_on_chunks_receives_chunks_and_parsed_document() -> None:
    seen: dict[str, Any] = {}

    async def on_chunks(chunks: list[str], parsed: Any) -> None:
        seen["chunks"] = chunks
        seen["parsed"] = parsed

    result = await ETLPipeline().run_bytes(
        b"hello world",
        "note.txt",
        "text/plain",
        on_chunks=on_chunks,
    )

    assert result.chunks == ["hello world"]
    assert seen["chunks"] == result.chunks
    assert seen["parsed"].text == "hello world"
    assert result.meta["chunk_count"] == 1
