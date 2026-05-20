# -*- coding: utf-8 -*-
"""schema_inspect：列全表 / 查单表列 / 未知表 / 数据库异常。"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.core.tools.builtin.schema import SchemaInspectTool


class FakeRow:
    def __init__(self, values: tuple[Any, ...]) -> None:
        self._values = values

    def __getitem__(self, index: int) -> Any:
        return self._values[index]


class FakeResult:
    def __init__(self, rows: list[FakeRow]) -> None:
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)


class FakeSession:
    def __init__(self, tables: list[str], columns: list[tuple[str, str]], fail: bool = False) -> None:
        self._tables = tables
        self._columns = columns
        self._fail = fail

    async def execute(self, statement: Any, params: dict[str, Any] | None = None) -> FakeResult:
        if self._fail:
            raise RuntimeError("db down")
        sql = str(statement)
        if "information_schema.tables" in sql:
            return FakeResult([FakeRow((name,)) for name in self._tables])
        if "information_schema.columns" in sql:
            table = (params or {}).get("table")
            if table != "demo_orders":
                return FakeResult([])
            return FakeResult([FakeRow(col) for col in self._columns])
        if "select distinct" in sql:
            if '"region"' in sql:
                return FakeResult([FakeRow(("华东",)), FakeRow(("华南",))])
            if '"status"' in sql:
                return FakeResult([FakeRow(("paid",)), FakeRow(("refunded",))])
            return FakeResult([])
        return FakeResult([])


class FakeContext:
    def __init__(self, session: FakeSession) -> None:
        self._session = session

    async def __aenter__(self) -> FakeSession:
        return self._session

    async def __aexit__(self, *args: Any) -> bool:
        return False


class FakeFactory:
    def __init__(self, session: FakeSession) -> None:
        self._session = session

    def __call__(self) -> FakeContext:
        return FakeContext(self._session)


def make_tool() -> SchemaInspectTool:
    session = FakeSession(
        tables=["demo_customers", "demo_orders", "demo_products"],
        columns=[
            ("id", "character varying"),
            ("amount", "numeric"),
            ("region", "character varying"),
            ("status", "character varying"),
        ],
    )
    return SchemaInspectTool(FakeFactory(session))


@pytest.mark.asyncio
async def test_lists_all_tables() -> None:
    payload = json.loads(await make_tool().execute())

    assert payload["tables"] == ["demo_customers", "demo_orders", "demo_products"]


@pytest.mark.asyncio
async def test_lists_columns_for_known_table() -> None:
    payload = json.loads(await make_tool().execute(table="demo_orders"))

    assert payload["table"] == "demo_orders"
    assert {"name": "amount", "type": "numeric"} in payload["columns"]
    assert payload["samples"]["region"] == ["华东", "华南"]
    assert payload["samples"]["status"] == ["paid", "refunded"]


@pytest.mark.asyncio
async def test_unknown_table_returns_message() -> None:
    result = await make_tool().execute(table="missing_table")

    assert "未找到表" in result


@pytest.mark.asyncio
async def test_database_error_is_returned_as_text() -> None:
    session = FakeSession(tables=[], columns=[], fail=True)
    tool = SchemaInspectTool(FakeFactory(session))

    result = await tool.execute()

    assert "失败" in result
