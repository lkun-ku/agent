"""数据库 schema 查看工具：让 Agent 先看表结构再写 SQL。"""

from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger
from sqlalchemy import text

from app.core.tools.base import BaseTool, ToolParameter


class SchemaInspectTool(BaseTool):
    """列出 public 下的表，或查看指定表的字段与类型。"""

    def __init__(self, session_factory: Any) -> None:
        super().__init__()
        self.name = "schema_inspect"
        self.description = (
            "查看数据库表结构。写 SQL 前先调用：不传 table 列出所有表，"
            "传 table 查看该表的字段与类型。"
        )
        self._session_factory = session_factory
        self.parameters = [
            ToolParameter(
                name="table",
                type="string",
                required=False,
                description="表名；留空则列出全部表",
            )
        ]

    async def execute(self, **kwargs: Any) -> str:
        table = str(kwargs.get("table", "")).strip()
        try:
            async with self._session_factory() as session:
                if not table:
                    result = await session.execute(
                        text(
                            "select table_name from information_schema.tables "
                            "where table_schema = 'public' order by table_name"
                        )
                    )
                    tables = [str(row[0]) for row in result]
                    return json.dumps({"tables": tables}, ensure_ascii=False)

                result = await session.execute(
                    text(
                        "select column_name, data_type "
                        "from information_schema.columns "
                        "where table_schema = 'public' and table_name = :table "
                        "order by ordinal_position"
                    ),
                    {"table": table},
                )
                columns = [
                    {"name": str(row[0]), "type": str(row[1])} for row in result
                ]
                if not columns:
                    return f"未找到表：{table}"

                samples: dict[str, list[str]] = {}
                if re.fullmatch(r"[A-Za-z0-9_]+", table):
                    for column in columns:
                        name = column["name"]
                        ctype = column["type"].lower()
                        if "character" not in ctype and "text" not in ctype:
                            continue
                        if not re.fullmatch(r"[A-Za-z0-9_]+", name):
                            continue
                        try:
                            sample_result = await session.execute(
                                text(
                                    f'select distinct "{name}" from "{table}" '
                                    f'where "{name}" is not null limit 9'
                                )
                            )
                            values = [str(row[0]) for row in sample_result]
                        except Exception:  # noqa: BLE001
                            continue
                        if 0 < len(values) <= 8:
                            samples[name] = values

                payload: dict[str, Any] = {"table": table, "columns": columns}
                if samples:
                    payload["samples"] = samples
                return json.dumps(payload, ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001
            logger.warning("schema_inspect 失败: {}", exc)
            return f"schema_inspect 失败: {exc}"
