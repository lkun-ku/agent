# ruff: noqa: E501
"""适配层：SQLite 状态机真相源、退款幂等台账、人工任务。

写操作统一走 `_tx()`；状态流转必须命中 ALLOWED_TRANSITIONS，禁止内存里另存一份状态。
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, cast

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

# 表结构保持最小：上游快照、售后单、台账、人工任务、审计、计数器。
SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  user_id TEXT PRIMARY KEY, risk_level TEXT, refund_rate_30d REAL, credit_score INTEGER DEFAULT 80);
CREATE TABLE IF NOT EXISTS orders(
  order_id TEXT PRIMARY KEY, user_id TEXT, paid_amount REAL, refundable_amount REAL,
  order_status TEXT, delivered_at TEXT, goods_amount REAL, freight_amount REAL,
  tax_amount REAL, discount_amount REAL);
CREATE TABLE IF NOT EXISTS refund_requests(
  refund_id TEXT PRIMARY KEY, order_id TEXT, user_id TEXT, idempotency_key TEXT,
  return_id TEXT, action_code TEXT, status_code TEXT, raw_json TEXT,
  refundable_cents INTEGER, requested_cents INTEGER, scenario TEXT, expected_action TEXT,
  reason_code TEXT, reason_name TEXT);
CREATE TABLE IF NOT EXISTS return_orders(
  return_id TEXT PRIMARY KEY, refund_id TEXT, order_id TEXT, user_id TEXT, session_id TEXT,
  status TEXT, workflow_status TEXT, reason TEXT, reason_code TEXT, plan TEXT,
  requested_amount REAL, approved_amount REAL, refunded_amount REAL DEFAULT 0,
  action_code TEXT, queue TEXT, trust_score INTEGER, risk_tier TEXT,
  risk_json TEXT, evidence_json TEXT, reply TEXT, handoff_json TEXT,
  return_required INTEGER, return_status TEXT);
CREATE TABLE IF NOT EXISTS refund_ledger(
  idem_key TEXT PRIMARY KEY, return_id TEXT, amount REAL, status TEXT);
CREATE TABLE IF NOT EXISTS review_tasks(
  return_id TEXT, queue TEXT, payload_json TEXT, decision_json TEXT,
  status TEXT, reviewer TEXT, note TEXT, id INTEGER PRIMARY KEY AUTOINCREMENT);
CREATE TABLE IF NOT EXISTS audit_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT, return_id TEXT, actor TEXT, action TEXT, detail_json TEXT);
CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT);
CREATE INDEX IF NOT EXISTS idx_requests_order ON refund_requests(order_id);
CREATE INDEX IF NOT EXISTS idx_requests_idem ON refund_requests(idempotency_key);
CREATE INDEX IF NOT EXISTS idx_returns_status ON return_orders(status);
"""


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        with self.lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    def close(self) -> None:
        with self.lock:
            self.conn.close()

    def _one(self, sql: str, params: tuple = ()) -> dict[str, Any] | None:
        row = self.conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def _all(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def _tx(self, sql: str, params: tuple = ()) -> None:
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                self.conn.execute(sql, params)
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

    def seed(self, dataset: Dataset) -> None:
        """只导入 users/orders/refund_requests，不预生成售后单。"""
        with self.lock:
            for rec in dataset.records:
                self.conn.execute(
                    "INSERT OR IGNORE INTO users VALUES(?,?,?,?)",
                    (rec.user_id, rec.user_risk_level, rec.user_refund_rate_30d, 80),
                )
                self.conn.execute(
                    "INSERT OR IGNORE INTO orders VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (
                        rec.order_id,
                        rec.user_id,
                        rec.paid,
                        rec.refundable,
                        rec.order_status.value,
                        rec.delivered_at.isoformat() if rec.delivered_at else None,
                        rec.goods_fee / 100,
                        rec.freight_fee / 100,
                        rec.tax_fee / 100,
                        rec.discount_fee / 100,
                    ),
                )
                self.conn.execute(
                    "INSERT OR IGNORE INTO refund_requests VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
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
            self.conn.commit()

    # ── 上游单据 / 售后单 ────────────────────────────────
    def request_handled(self, refund_id: str) -> bool:
        row = self._one("SELECT return_id FROM refund_requests WHERE refund_id=?", (refund_id,))
        return bool(row and row["return_id"])

    def find_existing(self, rec: Record) -> str | None:
        """幂等键/同订单命中已受理单：返回原单，禁止二次退款。"""
        own = self._one("SELECT return_id FROM refund_requests WHERE refund_id=?", (rec.refund_id,))
        if own and own["return_id"]:
            return own["return_id"]
        rows = self._all(
            "SELECT r.return_id FROM refund_requests r WHERE r.idempotency_key=? OR r.order_id=?",
            (rec.idempotency_key, rec.order_id),
        )
        for row in rows:
            if row["return_id"]:
                return row["return_id"]
        open_case = self._one(
            "SELECT return_id FROM return_orders WHERE order_id=? AND status NOT IN ('closed','rejected','refunded') "
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
            "WHERE (? <> '' AND refund_id=?) OR (? <> '' AND order_id=?) "
            "ORDER BY refund_id LIMIT 1",
            (refund_id or "", refund_id or "", order_id or "", order_id or ""),
        )
        raw = loads(row["raw_json"]) if row else None
        if not isinstance(raw, dict) or not raw:
            return None
        return parse_record(raw)

    def mark_request(self, refund_id: str, return_id: str, action_code: str) -> None:
        self._tx(
            "UPDATE refund_requests SET return_id=?, action_code=?, status_code='CLOSED' WHERE refund_id=?",
            (return_id, action_code, refund_id),
        )

    def next_return_id(self) -> str:
        with self.lock:
            row = self.conn.execute("SELECT v FROM kv WHERE k='return_seq'").fetchone()
            seq = int(row[0]) + 1 if row else 1
            self.conn.execute("INSERT OR REPLACE INTO kv VALUES('return_seq',?)", (str(seq),))
            self.conn.commit()
        return f"R{now().strftime('%Y%m%d')}{seq:07d}"

    def create_return(self, return_id: str, rec: Record) -> None:
        plan = "refund_only" if rec.refund_type.value != "RETURN_AND_REFUND" else "return_refund"
        self._tx(
            "INSERT INTO return_orders(return_id,refund_id,order_id,user_id,session_id,status,workflow_status,"
            "reason,reason_code,plan,requested_amount,approved_amount,evidence_json,return_required,return_status) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
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
                rec.requested,
                0.0,
                json.dumps(list(rec.evidence), ensure_ascii=False),
                int(rec.return_required),
                rec.return_status.value,
            ),
        )

    def return_row(self, return_id: str | None) -> ReturnOrderRow | None:
        return cast(
            "ReturnOrderRow | None",
            self._one("SELECT * FROM return_orders WHERE return_id=?", (return_id or "",)),
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
        parts = [(k, v) for k, v in fields.items() if k in self._RETURN_COLS]
        if not parts:
            return
        sql = (
            "UPDATE return_orders SET "
            + ",".join(f"{k}=?" for k, _ in parts)
            + " WHERE return_id=?"
        )
        self._tx(sql, tuple(v for _, v in parts) + (return_id,))

    def transition(
        self,
        return_id: str,
        target: WorkflowStatus,
        expect: WorkflowStatus | None = None,
    ) -> None:
        """状态机唯一写入口；非法流转直接抛错。"""
        row = self.return_row(return_id)
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
        self._tx(
            "UPDATE return_orders SET status=?, workflow_status=? WHERE return_id=?",
            (target_status.value, target_status.value, return_id),
        )
        with self.lock:
            self.conn.execute(
                "INSERT INTO audit_log(return_id,actor,action,detail_json) VALUES(?,?,?,?)",
                (
                    return_id,
                    "agent",
                    "transition",
                    json.dumps({"from": current.value, "to": target.value}),
                ),
            )
            self.conn.commit()

    # ── 退款幂等台账 ────────────────────────────────────
    def claim_refund(self, return_id: str, amount: float) -> bool:
        key = f"{return_id}:refund"
        with self.lock:
            cur = self.conn.execute(
                "INSERT OR IGNORE INTO refund_ledger VALUES(?,?,?,?)",
                (key, return_id, amount, "reserved"),
            )
            self.conn.commit()
            return cur.rowcount == 1

    def refund(self, return_id: str, amount: float) -> None:
        """可替换的退款网关；REFUND_FAIL=1 用来回归渠道失败路径。"""
        if os.getenv("REFUND_FAIL") == "1":
            raise RuntimeError("渠道退款失败")
        with self.lock:
            self.conn.execute(
                "UPDATE return_orders SET refunded_amount=? WHERE return_id=?", (amount, return_id)
            )
            self.conn.execute(
                "UPDATE refund_ledger SET status='consumed' WHERE idem_key=?",
                (f"{return_id}:refund",),
            )
            self.conn.commit()

    def release_refund(self, return_id: str) -> None:
        with self.lock:
            self.conn.execute(
                "DELETE FROM refund_ledger WHERE idem_key=? AND status='reserved'",
                (f"{return_id}:refund",),
            )
            self.conn.commit()

    # ── 人工任务 / 统计 ──────────────────────────────────
    def save_task(
        self, return_id: str, queue: str, payload: dict[str, object], pending: bool = True
    ) -> None:
        with self.lock:
            self.conn.execute(
                "DELETE FROM review_tasks WHERE return_id=? AND status='pending'", (return_id,)
            )
            self.conn.execute(
                "INSERT INTO review_tasks(return_id,queue,payload_json,decision_json,status,reviewer,note) "
                "VALUES(?,?,?,?,?,?,?)",
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
            self.conn.commit()

    def pending_task(self, return_id: str | None) -> PendingTask | None:
        row = cast(
            "dict[str, Any] | None",
            self._one(
                "SELECT * FROM review_tasks WHERE return_id=? AND status='pending' ORDER BY id DESC LIMIT 1",
                (return_id or "",),
            ),
        )
        if not row:
            return None
        kind = (
            "external"
            if row["queue"] == "platform_dispute"
            else "evidence"
            if row["queue"] == "evidence"
            else "manual_review"
        )
        return PendingTask(
            kind=kind,
            queue=row["queue"],
            payload=json.loads(row["payload_json"] or "{}"),
        )

    def resolve_task(self, return_id: str, action: str, reviewer: str, note: str) -> None:
        self._tx(
            "UPDATE review_tasks SET status='resolved', decision_json=?, reviewer=?, note=? "
            "WHERE return_id=? AND status='pending'",
            (json.dumps({"action": action}, ensure_ascii=False), reviewer, note, return_id),
        )

    def open_tasks(self) -> list[OpenTask]:
        rows = self._all(
            "SELECT t.return_id,t.queue,t.payload_json,r.reason,r.requested_amount,r.action_code "
            "FROM review_tasks t JOIN return_orders r ON r.return_id=t.return_id WHERE t.status='pending'"
        )
        return [
            OpenTask(
                return_id=r["return_id"],
                queue=r["queue"],
                queue_label=QUEUE_LABELS.get(r["queue"], r["queue"]),
                reason=r["reason"],
                reason_label=REASON_LABELS.get(r["reason"], r["reason"]),
                requested_amount=r["requested_amount"],
                action=r["action_code"],
            )
            for r in rows
        ]

    def user_stats(self, user_id: str) -> Stats:
        orders = self._one("SELECT COUNT(*) c FROM orders WHERE user_id=?", (user_id,))
        returns = self._one(
            "SELECT COUNT(*) c, SUM(CASE WHEN reason='missing_parts' THEN 1 ELSE 0 END) m, "
            "SUM(CASE WHEN plan='refund_only' THEN 1 ELSE 0 END) ro FROM return_orders WHERE user_id=?",
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
            for r in rows
            if r["action_code"]
            in {"AUTO_APPROVE_AND_REFUND", "AUTO_APPROVE_NO_RETURN", "PARTIAL_REFUND_FREIGHT_ONLY"}
        )
        manual = sum(1 for r in rows if r["status"] == "manual_review")
        rejected = sum(1 for r in rows if r["status"] == "rejected")
        refunded = sum(
            1 for r in rows if r["status"] in {"refunded", "closed"} and r["refunded_amount"] > 0
        )
        return {
            "total_cases": total,
            "auto_handled": auto,
            "manual_reviewed": manual,
            "risk_held": sum(1 for r in rows if r["action_code"] == "RISK_HOLD_FOR_REVIEW"),
            "rejected_cases": rejected,
            "high_risk": sum(1 for r in rows if r["action_code"] == "RISK_HOLD_FOR_REVIEW"),
            "refunded_cases": refunded,
            "refunded_amount": round(self.refunded_amount(), 2),
            "automation_rate": auto / total if total else 0.0,
            "estimated_manual_cost_saved": round(auto * 6.5, 2),
            "review_queue_size": len(self.open_tasks()),
            "action_counts": {},
            "dataset": {"records": total},
        }


__all__ = ["SCHEMA", "Store"]
