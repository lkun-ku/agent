"""公共层：时钟、金额、容错 JSON、按需加载。

不依赖任何业务模块，供 contracts / activities / workflow / adapters / interfaces 共用。
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import ModuleType
from typing import Any

_FIXED_NOW: datetime | None = None


def normalize(value: datetime) -> datetime:
    """统一东八区 naive，避免与 datetime.now() 比较时报错。"""
    if value.tzinfo is not None:
        value = value.astimezone(timezone(timedelta(hours=8))).replace(tzinfo=None)
    return value


def now() -> datetime:
    return _FIXED_NOW or datetime.now()


@contextmanager
def fixed_now(value: datetime | None) -> Iterator[None]:
    """固定业务时钟，保证时效类规则可回归。"""
    global _FIXED_NOW
    old, _FIXED_NOW = _FIXED_NOW, normalize(value) if value else None
    try:
        yield
    finally:
        _FIXED_NOW = old


def set_now(value: datetime | None) -> None:
    global _FIXED_NOW
    _FIXED_NOW = normalize(value) if value else None


def to_cents(value: Decimal | float | str, field: str = "金额") -> int:
    """元 -> 整数分；出现半分精度直接报错。"""
    dec = Decimal(str(value))
    cents = dec * 100
    if cents != cents.to_integral_value():
        raise ValueError(f"{field} 存在小于分的精度: {value!r}")
    return int(cents)


def yuan(cents: int) -> float:
    return round(cents / 100, 2)


def paid_cents(goods: int, freight: int, tax: int, discount: int) -> int:
    return goods + freight + tax - discount


def loads(raw: Any, default: Any = None) -> Any:
    try:
        return json.loads(raw) if raw else (default if default is not None else {})
    except (TypeError, ValueError):
        return default if default is not None else {}


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def lazy_module(name: str) -> ModuleType:
    """按需导入，避免包门面连坐加载重依赖。"""
    return importlib.import_module(name)


def import_string(path: str) -> Any:
    """支持 'a.b:attr' 与 'a.b.attr' 两种写法。"""
    if ":" in path:
        module, attr = path.split(":", 1)
    else:
        module, _, attr = path.rpartition(".")
    return getattr(importlib.import_module(module), attr)


def lazy_exports(mapping: dict[str, str]) -> Callable[[str], Any]:
    """PEP 562 懒加载门面；mapping: 导出名 -> 'module:attr'。"""

    def __getattr__(name: str) -> Any:
        if name not in mapping:
            raise AttributeError(name)
        mod, _, attr = mapping[name].partition(":")
        value = getattr(lazy_module(mod), attr) if attr else lazy_module(mod)
        globals()[name] = value
        return value

    return __getattr__


__all__ = [
    "dumps",
    "fixed_now",
    "import_string",
    "lazy_exports",
    "lazy_module",
    "loads",
    "normalize",
    "now",
    "paid_cents",
    "set_now",
    "to_cents",
    "yuan",
]
