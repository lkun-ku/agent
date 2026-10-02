"""退款测试：PostgreSQL 存在时先执行迁移。"""

from __future__ import annotations

import socket
from pathlib import Path

import psycopg2
import pytest

from app.config import get_settings

ROOT = Path(__file__).resolve().parents[2]


def _pg_available() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=0.5):
            return True
    except OSError:
        return False


@pytest.fixture(scope="session", autouse=True)
def refund_schema() -> None:
    if not _pg_available():
        yield
        return
    dsn = get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://")
    sql = (ROOT / "migrations" / "001_refund_init.sql").read_text(encoding="utf-8")
    with psycopg2.connect(dsn) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql)
    yield
