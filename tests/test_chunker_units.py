# -*- coding: utf-8 -*-
"""P2-2：fixed 策略必须与其它策略同口径（token），而不是按字符。"""

from __future__ import annotations

import statistics

import tiktoken

from app.etl.chunker import ChunkStrategy, DocumentChunker

ENC = tiktoken.get_encoding("cl100k_base")


def make_text(chars: int = 5_000) -> str:
    sentence = "向量数据库支持多种索引类型，检索时需要权衡召回率、延迟与内存占用。"
    return (sentence * (chars // len(sentence) + 1))[:chars]


def test_fixed_chunks_are_measured_in_tokens() -> None:
    chunker = DocumentChunker(chunk_size=512, chunk_overlap=64)

    chunks = chunker.chunk(make_text(), strategy=ChunkStrategy.FIXED)
    sizes = [len(ENC.encode(c)) for c in chunks]

    assert chunks
    assert max(sizes) <= 520, f"存在超长块: max={max(sizes)}"
    assert 480 <= statistics.median(sizes) <= 520, f"p50={statistics.median(sizes)}"


def test_recursive_chunks_stay_within_token_budget() -> None:
    chunker = DocumentChunker(chunk_size=512, chunk_overlap=64)

    chunks = chunker.chunk(make_text(), strategy=ChunkStrategy.RECURSIVE)
    sizes = [len(ENC.encode(c)) for c in chunks]

    assert chunks
    assert max(sizes) <= 520
