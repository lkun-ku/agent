"""JSON 序列化与容错反序列化工具。"""

from __future__ import annotations

import json
from typing import Any


def dumps_json(value: Any, *, sort_keys: bool = False) -> str:
    """序列化 JSON；统一禁用 ASCII 转义，避免中文可读性下降。"""
    return json.dumps(value, ensure_ascii=False, sort_keys=sort_keys)


def loads_json(
    raw: str | bytes | bytearray | None,
    default: Any = None,
) -> Any:
    """解析 JSON。

    空输入返回 ``default``；非法 JSON 继续抛出异常，避免静默吞掉脏数据。
    """
    if raw is None:
        return default
    text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
    if not text:
        return default
    return json.loads(text)


__all__ = ["dumps_json", "loads_json"]
