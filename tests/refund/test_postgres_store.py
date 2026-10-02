"""PostgreSQL 适配器的真实集成回归；无 PG 时跳过。"""

from __future__ import annotations

import socket
from pathlib import Path

import psycopg2
import pytest

from app.config import get_settings
from app.core.tools.refund.service import RefundService
from app.core.tools.refund.store import PostgresRefundStore

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "refund"


def _pg_available() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=0.5):
            return True
    except OSError:
        return False


def _reset_refund_schema() -> None:
    dsn = get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://")
    with psycopg2.connect(dsn) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "TRUNCATE refund.return_orders, refund.refund_requests, "
                "refund.refund_ledger, refund.review_tasks, refund.audit_log, "
                "refund.orders, refund.users, refund.kv CASCADE"
            )


@pytest.mark.integration
@pytest.mark.skipif(not _pg_available(), reason="PostgreSQL 未启动")
def test_postgres_store_process_batch() -> None:
    store = PostgresRefundStore(get_settings().database_url)
    _reset_refund_schema()
    service = RefundService(store, data_dir=DATA)
    try:
        result = service.process_batch()
        assert result["total"] == 14
        assert result["auto_refunded"] == 3
        assert result["auto_rejected"] == 3
        assert result["held_inbound"] == 1
        assert result["manual_queued"] == 6
        assert result["deduped"] == 1
        assert result["refunded_amount"] == 201.0
        assert len(service.list_review_queue()) == 6
    finally:
        service.close()
