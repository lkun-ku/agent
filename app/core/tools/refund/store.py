# ruff: noqa: E501
"""生产适配器：PostgreSQL 状态机真相源、台账与人工任务。

表放在独立 schema ``refund``，与知识库表隔离；SQL 语义保持外部工作流不变。
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from typing import Any, Literal, cast

from psycopg2.extensions import connection as PGConnection
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

from app.core.tools.refund.ports import PaymentGateway
from app.core.tools.refund.rows import OpenTask, PendingTask, ReturnOrderRow
from app.domain.refund.activities.ingest import parse_record
from app.domain.refund.common import loads, now
from app.domain.refund.contracts import (
    ALLOWED_TRANSITIONS,
    QUEUE_LABELS,
    REASON_LABELS,
    Dataset,
    Record,
    Stats,
    WorkflowStatus,
)


class PostgresRefundStore:
    """RefundStore 的生产实现；所有写操作走事务。"""

    def __init__(
        self,
        dsn: str,
        *,
        gateway: PaymentGateway | None = None,
        minconn: int = 1,
        maxconn: int = 5,
    ) -> None:
        resolved_gateway: PaymentGateway
        if gateway is None:
            from app.core.tools.refund.payment import create_payment_gateway

            resolved_gateway = create_payment_gateway()
        else:
            resolved_gateway = gateway
        self.gateway = resolved_gateway
        self.dsn = (
            dsn.replace("postgresql+asyncpg://", "postgresql://")
            .replace("postgresql+psycopg2://", "postgresql://")
            .replace("postgres://", "postgresql://")
        )
        self.pool = ThreadedConnectionPool(minconn, maxconn, dsn=self.dsn)
        self._require_schema()

    def _require_schema(self) -> None:
        row = self._one("SELECT to_regclass('refund.return_orders') AS t")
        if not row or not row["t"]:
            raise RuntimeError(
                "退款 schema 未初始化，请先执行 migrations/001_refund_init.sql"
            )

    @contextmanager
    def _conn(self) -> Iterator[PGConnection]:
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SET search_path TO refund, public")
            yield conn
        finally:
            self.pool.putconn(conn)

    def close(self) -> None:
        self.pool.closeall()

    def _one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self._conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
            conn.commit()
            return dict(row) if row else None

    def _all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self._conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
            conn.commit()
            return [dict(row) for row in rows]

    def _tx(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        with self._conn() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def seed(self, dataset: Dataset) -> None:
        with self._conn() as conn:
            try:
                with conn.cursor() as cur:
                    for rec in dataset.records:
                        cur.execute(
                            "INSERT INTO users(user_id,risk_level,refund_rate_30d,credit_score) "
                            "VALUES(%s,%s,%s,80) ON CONFLICT (user_id) DO NOTHING",
                            (rec.user_id, rec.user_risk_level, rec.user_refund_rate_30d),
                        )
                        cur.execute(
                            "INSERT INTO orders VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                            "ON CONFLICT (order_id) DO NOTHING",
                            (
                                rec.order_id,
                                rec.user_id,
                                Decimal(rec.paid),
                                Decimal(rec.refundable),
                                rec.order_status.value,
                                rec.delivered_at.isoformat() if rec.delivered_at else None,
                                Decimal(rec.goods_fee) / 100,
                                Decimal(rec.freight_fee) / 100,
                                Decimal(rec.tax_fee) / 100,
                                Decimal(rec.discount_fee) / 100,
                            ),
                        )
                        cur.execute(
                            "INSERT INTO refund_requests VALUES("
                            "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s"
                            ") ON CONFLICT (refund_id) DO NOTHING",
                            (
                                rec.refund_id,
                                rec.order_id,
                                rec.user_id,
                                rec.idempotency_key,
                                None,
                                None,
                                "PENDING",
                                json.dumps(rec.raw, ensure_ascii=False),
                                rec.refundable_fee,
                                rec.refund_fee,
                                rec.scenario,
                                rec.expected_action.value,
                                rec.reason_code,
                                rec.reason_label,
                            ),
                        )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def request_handled(self, refund_id: str) -> bool:
        row = self._one(
            "SELECT return_id FROM refund_requests WHERE refund_id=%s",
            (refund_id,),
        )
        return bool(row and row["return_id"])

    def find_existing(self, rec: Record) -> str | None:
        own = self._one(
            "SELECT return_id FROM refund_requests WHERE refund_id=%s",
            (rec.refund_id,),
        )
        if own and own["return_id"]:
            return cast("str", own["return_id"])
        rows = self._all(
            "SELECT return_id FROM refund_requests WHERE idempotency_key=%s OR order_id=%s",
            (rec.idempotency_key, rec.order_id),
        )
        for row in rows:
            if row["return_id"]:
                return cast("str", row["return_id"])
        open_case = self._one(
            "SELECT return_id FROM return_orders "
            "WHERE order_id=%s AND status NOT IN ('closed','rejected','refunded') "
            "ORDER BY return_id LIMIT 1",
            (rec.order_id,),
        )
        return open_case["return_id"] if open_case else None

    def load_record(
        self,
        *,
        refund_id: str | None = None,
        order_id: str | None = None,
    ) -> Record | None:
        if not refund_id and not order_id:
            return None
        row = self._one(
            "SELECT raw_json FROM refund_requests "
            "WHERE (%s <> '' AND refund_id=%s) OR (%s <> '' AND order_id=%s) "
            "ORDER BY refund_id LIMIT 1",
            (
                refund_id or "",
                refund_id or "",
                order_id or "",
                order_id or "",
            ),
        )
        raw = loads(row.get("raw_json")) if row else None
        if not isinstance(raw, dict) or not raw:
            return None
        return parse_record(raw)

    def mark_request(self, refund_id: str, return_id: str, action_code: str) -> None:
        self._tx(
            "UPDATE refund_requests SET return_id=%s, action_code=%s, "
            "status_code='CLOSED' WHERE refund_id=%s",
            (return_id, action_code, refund_id),
        )

    def next_return_id(self) -> str:
        with self._conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT v FROM kv WHERE k='return_seq' FOR UPDATE")
                row = cast("dict[str, Any] | None", cur.fetchone())
                seq = int(row["v"]) + 1 if row else 1
                cur.execute(
                    "INSERT INTO kv(k,v) VALUES('return_seq',%s) "
                    "ON CONFLICT (k) DO UPDATE SET v=EXCLUDED.v",
                    (str(seq),),
                )
            conn.commit()
        return f"R{now().strftime('%Y%m%d')}{seq:07d}"

    def create_return(self, return_id: str, rec: Record) -> None:
        plan = "refund_only" if rec.refund_type.value != "RETURN_AND_REFUND" else "return_refund"
        self._tx(
            "INSERT INTO return_orders("
            "return_id,refund_id,order_id,user_id,session_id,status,workflow_status,"
            "reason,reason_code,plan,requested_amount,approved_amount,evidence_json,"
            "return_required,return_status) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                return_id,
                rec.refund_id,
                rec.order_id,
                rec.user_id,
                f"batch-{rec.refund_id}",
                "risk_review",
                "risk_review",
                rec.reason.value,
                rec.reason_code,
                plan,
                Decimal(rec.requested),
                0,
                json.dumps(list(rec.evidence), ensure_ascii=False),
                int(rec.return_required),
                rec.return_status.value,
            ),
        )

    def return_row(self, return_id: str | None) -> ReturnOrderRow | None:
        return cast(
            "ReturnOrderRow | None",
            self._one(
                "SELECT * FROM return_orders WHERE return_id=%s",
                (return_id or "",),
            ),
        )

    def status_of(self, return_id: str) -> str:
        row = self.return_row(return_id)
        return row["status"] if row else ""

    _RETURN_COLS = {
        "action_code",
        "queue",
        "approved_amount",
        "refunded_amount",
        "risk_tier",
        "trust_score",
        "risk_json",
        "evidence_json",
        "reply",
        "handoff_json",
        "workflow_status",
        "status",
    }

    def update_return(self, return_id: str, **fields: Any) -> None:
        parts = [(key, value) for key, value in fields.items() if key in self._RETURN_COLS]
        if not parts:
            return
        sql = (
            "UPDATE return_orders SET "
            + ",".join(f"{key}=%s" for key, _ in parts)
            + " WHERE return_id=%s"
        )
        self._tx(sql, tuple(value for _, value in parts) + (return_id,))

    def transition(
        self,
        return_id: str,
        target: WorkflowStatus,
        expect: WorkflowStatus | None = None,
    ) -> None:
        with self._conn() as conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        "SELECT * FROM return_orders WHERE return_id=%s FOR UPDATE",
                        (return_id,),
                    )
                    row = cur.fetchone()
                    if not row:
                        raise KeyError(return_id)
                    current = WorkflowStatus(row["status"])
                    target_status = WorkflowStatus(target)
                    if expect is not None and current is not WorkflowStatus(expect):
                        raise ValueError(
                            f"{return_id} 当前 {current.value}，期望 {WorkflowStatus(expect).value}"
                        )
                    if target_status not in ALLOWED_TRANSITIONS.get(current, set()):
                        raise ValueError(f"非法状态流转 {current.value} -> {target_status.value}")
                    cur.execute(
                        "UPDATE return_orders SET status=%s, workflow_status=%s WHERE return_id=%s",
                        (target_status.value, target_status.value, return_id),
                    )
                    cur.execute(
                        "INSERT INTO audit_log(return_id,actor,action,detail_json) "
                        "VALUES(%s,%s,%s,%s)",
                        (
                            return_id,
                            "agent",
                            "transition",
                            json.dumps({"from": current.value, "to": target_status.value}),
                        ),
                    )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def claim_refund(self, return_id: str, amount: Decimal | float) -> bool:
        key = f"{return_id}:refund"
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO refund_ledger VALUES(%s,%s,%s,'reserved') "
                    "ON CONFLICT (idem_key) DO NOTHING",
                    (key, return_id, Decimal(amount)),
                )
                claimed = bool(cur.rowcount == 1)
            conn.commit()
            return claimed

    def refund(self, return_id: str, amount: Decimal | float) -> None:
        """先调支付 Port，成功后再写本地台账；失败不落账。"""
        self.gateway.refund(return_id, amount)
        with self._conn() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE return_orders SET refunded_amount=%s WHERE return_id=%s",
                        (Decimal(amount), return_id),
                    )
                    cur.execute(
                        "UPDATE refund_ledger SET status='consumed' WHERE idem_key=%s",
                        (f"{return_id}:refund",),
                    )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def release_refund(self, return_id: str) -> None:
        self._tx(
            "DELETE FROM refund_ledger WHERE idem_key=%s AND status='reserved'",
            (f"{return_id}:refund",),
        )

    def save_task(
        self,
        return_id: str,
        queue: str,
        payload: dict[str, object],
        pending: bool = True,
    ) -> None:
        with self._conn() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM review_tasks WHERE return_id=%s AND status='pending'",
                        (return_id,),
                    )
                    cur.execute(
                        "INSERT INTO review_tasks("
                        "return_id,queue,payload_json,decision_json,status,reviewer,note) "
                        "VALUES(%s,%s,%s,%s,%s,%s,%s)",
                        (
                            return_id,
                            queue,
                            json.dumps(payload, ensure_ascii=False),
                            "{}",
                            "pending" if pending else "resolved",
                            "",
                            "",
                        ),
                    )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def pending_task(self, return_id: str | None) -> PendingTask | None:
        row = self._one(
            "SELECT * FROM review_tasks WHERE return_id=%s AND status='pending' "
            "ORDER BY id DESC LIMIT 1",
            (return_id or "",),
        )
        if not row:
            return None
        queue = row["queue"]
        kind: Literal["external", "evidence", "manual_review"] = (
            "external"
            if queue == "platform_dispute"
            else "evidence"
            if queue == "evidence"
            else "manual_review"
        )
        return PendingTask(
            kind=kind,
            queue=queue,
            payload=json.loads(row["payload_json"] or "{}"),
        )

    def resolve_task(self, return_id: str, action: str, reviewer: str, note: str) -> None:
        self._tx(
            "UPDATE review_tasks SET status='resolved', decision_json=%s, "
            "reviewer=%s, note=%s WHERE return_id=%s AND status='pending'",
            (
                json.dumps({"action": action}, ensure_ascii=False),
                reviewer,
                note,
                return_id,
            ),
        )

    def open_tasks(self) -> list[OpenTask]:
        rows = self._all(
            "SELECT t.return_id,t.queue,t.payload_json,r.reason,r.requested_amount,"
            "r.action_code FROM review_tasks t "
            "JOIN return_orders r ON r.return_id=t.return_id "
            "WHERE t.status='pending'"
        )
        return [
            OpenTask(
                return_id=row["return_id"],
                queue=row["queue"],
                queue_label=QUEUE_LABELS.get(row["queue"], row["queue"]),
                reason=row["reason"],
                reason_label=REASON_LABELS.get(row["reason"], row["reason"]),
                requested_amount=row["requested_amount"],
                action=row["action_code"],
            )
            for row in rows
        ]

    def user_stats(self, user_id: str) -> Stats:
        orders = self._one(
            "SELECT COUNT(*) c FROM orders WHERE user_id=%s",
            (user_id,),
        )
        returns = self._one(
            "SELECT COUNT(*) c, "
            "SUM(CASE WHEN reason='missing_parts' THEN 1 ELSE 0 END) m, "
            "SUM(CASE WHEN plan='refund_only' THEN 1 ELSE 0 END) ro "
            "FROM return_orders WHERE user_id=%s",
            (user_id,),
        )
        return Stats(
            order_count=int(orders["c"] if orders else 0),
            return_count=int((returns or {}).get("c") or 0),
            refund_only_count=int((returns or {}).get("ro") or 0),
            missing_claim_count=int((returns or {}).get("m") or 0),
        )

    def refunded_amount(self) -> float:
        row = self._one(
            "SELECT COALESCE(SUM(amount),0) s FROM refund_ledger WHERE status='consumed'"
        )
        return float(row["s"] if row else 0.0)

    def stats(self) -> dict[str, object]:
        rows = self._all("SELECT status, action_code, refunded_amount FROM return_orders")
        total = len(rows)
        auto = sum(
            1
            for row in rows
            if row["action_code"]
            in {
                "AUTO_APPROVE_AND_REFUND",
                "AUTO_APPROVE_NO_RETURN",
                "PARTIAL_REFUND_FREIGHT_ONLY",
            }
        )
        manual = sum(1 for row in rows if row["status"] == "manual_review")
        rejected = sum(1 for row in rows if row["status"] == "rejected")
        refunded = sum(
            1
            for row in rows
            if row["status"] in {"refunded", "closed"} and (row["refunded_amount"] or 0) > 0
        )
        return {
            "total_cases": total,
            "auto_handled": auto,
            "manual_reviewed": manual,
            "risk_held": sum(1 for row in rows if row["action_code"] == "RISK_HOLD_FOR_REVIEW"),
            "rejected_cases": rejected,
            "high_risk": sum(1 for row in rows if row["action_code"] == "RISK_HOLD_FOR_REVIEW"),
            "refunded_cases": refunded,
            "refunded_amount": round(self.refunded_amount(), 2),
            "automation_rate": auto / total if total else 0.0,
            "estimated_manual_cost_saved": round(auto * 6.5, 2),
            "review_queue_size": len(self.open_tasks()),
            "action_counts": {},
            "dataset": {"records": total},
        }
