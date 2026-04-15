"""内置只读数据库查询工具（SQLAlchemy 异步会话）。"""

from __future__ import annotations

import re
from typing import Any

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tools.base import BaseTool, ToolParameter

_COMMENT = re.compile(r"(?:--[^\n]*)|(?:/\*.*?\*/)", re.S)
_STRING = re.compile(r"'(?:''|[^'])*'")
_WRITE = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke|merge|call|copy|vacuum)\b",
    re.I,
)


class DatabaseQueryTool(BaseTool):
    """执行受控的只读 SQL（默认仅允许 SELECT）。"""

    def __init__(self, session_factory: Any | None = None) -> None:
        """
        :param session_factory: 可选，返回 AsyncSession 的异步上下文工厂；
            若为 None，execute 时需传入 session 参数。
        """
        super().__init__()
        self.name = "database_query"
        self.description = "在只读模式下执行 SQL 查询并返回行列表（禁止写操作）。"
        self.parameters = [
            ToolParameter(
                name="sql",
                type="string",
                description="只读 SQL，必须以 SELECT 开头",
                required=True,
            )
        ]
        self._session_factory = session_factory

    def _validate_sql(self, sql: str) -> str:
        """词法级只读校验：剥离字面量/注释 → 单语句 → 首关键字 → 禁写 → 禁 INTO。"""
        s = sql.strip().rstrip(";").strip()
        # 先替换字符串字面量，再去注释，避免注释符出现在字符串里被误处理
        probe = _COMMENT.sub(" ", _STRING.sub("''", s))

        if not probe.strip():
            raise ValueError("SQL 不能为空")
        if ";" in probe:
            raise ValueError("仅允许单条 SQL")
        if not re.match(r"^(select|with)\b", probe, re.I):
            raise ValueError("仅允许 SELECT 查询")

        matched = _WRITE.search(probe)
        if matched:
            raise ValueError(f"查询包含禁止关键字: {matched.group(1)}")
        if re.search(r"\binto\b", probe, re.I):
            raise ValueError("禁止 SELECT INTO")
        return s

    async def execute(self, **kwargs: Any) -> Any:
        """执行查询；可传入 session=AsyncSession 覆盖默认工厂。"""
        sql = str(kwargs.get("sql", "")).strip()
        if not sql:
            raise ValueError("参数 sql 不能为空")
        safe_sql = self._validate_sql(sql)

        session: AsyncSession | None = kwargs.get("session")
        if session is None and self._session_factory is None:
            raise RuntimeError("未提供 session 且未配置 session_factory")

        async def _run(sess: AsyncSession) -> list[dict[str, Any]]:
            result = await sess.execute(text(safe_sql))
            rows = result.mappings().all()
            # 转为可序列化字典列表
            return [dict(r) for r in rows]

        if session is not None:
            out = await _run(session)
            logger.info("database_query 返回 {} 行", len(out))
            return out

        async with self._session_factory() as sess:  # type: ignore[misc]
            out = await _run(sess)
            logger.info("database_query 返回 {} 行", len(out))
            return out
