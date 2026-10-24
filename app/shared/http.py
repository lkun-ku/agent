"""HTTP/SSE 通用编码工具。"""

from __future__ import annotations

import json
from typing import Any


def encode_sse_event(payload: dict[str, Any]) -> bytes:
    """编码一个 SSE 数据帧；统一中文不转义与换行结束符。"""
    return b"data: " + json.dumps(payload, ensure_ascii=False).encode() + b"\n\n"


def encode_sse_done() -> bytes:
    """编码 SSE 结束帧。"""
    return encode_sse_event({"done": True})


__all__ = ["encode_sse_done", "encode_sse_event"]
