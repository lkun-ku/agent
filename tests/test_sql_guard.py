# -*- coding: utf-8 -*-
"""P2-1：SQL 只读校验必须是词法级，不误杀 created_at、也不放过写操作。"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.tools.builtin.database import DatabaseQueryTool


class FakeResult:
    def mappings(self) -> FakeResult:
        return self

    def all(self) -> list[dict[str, Any]]:
        return []


class FakeSession:
    def __init__(self) -> None:
        self.statements: list[str] = []

    async def execute(self, statement: Any) -> FakeResult:
        self.statements.append(str(statement))
        return FakeResult()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sql",
    [
        "SELECT created_at FROM users",
        "SELECT 'delete' AS word FROM t",
        "SELECT count(*) FROM t WHERE name = 'update'",
        "WITH x AS (SELECT 1) SELECT * FROM x",
        "SELECT * FROM t -- delete from t",
        "SELECT 1;",
    ],
)
async def test_readonly_sql_is_allowed(sql: str) -> None:
    session = FakeSession()
    tool = DatabaseQueryTool()

    result = await tool.execute(sql=sql, session=session)

    assert result == []
    assert session.statements


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM t",
        "UPDATE t SET a = 1",
        "CREATE TABLE x (id int)",
        "SELECT 1; DROP TABLE t",
        "SELECT * INTO x FROM t",
        "/*x*/ UPDATE t SET a = 1",
        "SELECT 1; SELECT 2",
        "ALTER TABLE t ADD COLUMN x int",
        "TRUNCATE TABLE t",
        "GRANT SELECT ON t TO public",
    ],
)
async def test_write_or_multi_statement_is_rejected(sql: str) -> None:
    tool = DatabaseQueryTool()

    with pytest.raises(ValueError):
        await tool.execute(sql=sql, session=FakeSession())
