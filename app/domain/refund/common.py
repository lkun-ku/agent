"""公共层：时钟、金额、容错 JSON、按需加载。

不依赖任何业务模块，供 contracts / activities / workflow / adapters / interfaces 共用。
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import ModuleType
from typing import Any, Protocol


def normalize(value: datetime) -> datetime:
    """统一东八区 naive，避免与 datetime.now() 比较时报错。"""
    if value.tzinfo is not None:
        value = value.astimezone(timezone(timedelta(hours=8))).replace(tzinfo=None)
    return value


class Clock(Protocol):
    """业务时钟端口；注入使用，避免全局可变状态。"""

    def now(self) -> datetime: ...


class SystemClock:
    """生产系统时钟。"""

    def now(self) -> datetime:
        return datetime.now()


def now() -> datetime:
    """供纯函数/适配器使用的默认时钟。"""
    return datetime.now()


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
    "Clock",
    "SystemClock",
    "dumps",
    "import_string",
    "lazy_exports",
    "lazy_module",
    "loads",
    "normalize",
    "now",
    "paid_cents",
    "to_cents",
    "yuan",
]
