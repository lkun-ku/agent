"""编排层：把活动层的裁决结果映射到状态机、幂等台账与人工任务。

标准工作流顺序：ingest -> eligibility -> risk -> dispatch -> execute/resume。
RefundService 是唯一入站门面；外部客服 agent 只通过 resume_review/provide_evidence 写回。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.tools.refund.nodes import AUTO_ACTIONS, NODE_MAP, REJECT_ACTIONS
from app.core.tools.refund.ports import RefundStore
from app.core.tools.refund.rows import OpenTask, ReturnOrderRow
from app.domain.refund.activities.dispatch import run_steps
from app.domain.refund.activities.ingest import load_dataset
from app.domain.refund.common import Clock, SystemClock, dumps, loads, yuan
from app.domain.refund.contracts import (
    ACTION_LABELS,
    QUEUE_LABELS,
    REASON_LABELS,
    STATUS_LABELS,
    ActionCode,
    CaseView,
    Dataset,
    Record,
    StepOutcome,
    Verdict,
    WorkflowStatus,
)


def reply_of(action: ActionCode, rec: Record, amount: float, queue: str) -> str:
    """对外话术：只说处理方式，不暴露规则编号与权重。"""
    label = ACTION_LABELS[action.value]
    if action in {
        ActionCode.AUTO_APPROVE_AND_REFUND,
        ActionCode.AUTO_APPROVE_NO_RETURN,
        ActionCode.PARTIAL_REFUND_FREIGHT_ONLY,
    }:
        return f"{label}，{amount:.2f} 元将原路退回。"
    if action is ActionCode.HOLD_UNTIL_RETURN_RECEIVED:
        return "商品退回入库后继续处理，暂不退款。"
    if action is ActionCode.DEDUPE_RETURN_EXISTING:
        return "该申请此前已受理，返回原售后单，不会重复退款。"
    if action.name.startswith("REJECT"):
        return f"{label}；如有异议可补充凭证或转人工申诉。"
    return (
        f"已转人工客服（{QUEUE_LABELS.get(queue, queue or '人工队列')}）："
        f"{label}；理由 {rec.reason_label}，申请 {rec.requested:.2f} 元。"
    )


class RefundService:
    """唯一入站门面：自动完成可自动的部分，其余生成转人工任务。"""

    def __init__(
        self,
        store: RefundStore,
        dataset: Dataset | None = None,
        data_dir: str | Path | None = None,
        *,
        seed: bool = True,
        clock: Clock | None = None,
    ):
        self.store = store
        self.clock = clock or SystemClock()
        if dataset is not None:
            self.dataset = dataset
        elif seed:
            self.dataset = load_dataset(data_dir=data_dir or "data/refund")
        else:
            self.dataset = Dataset("", "", "分", self.clock.now(), [])
        if seed:
            self.store.seed(self.dataset)
        # 客服系统可以动态推送新单据；内存索引与 dataset 保持同步，供查询/恢复使用
        self.records: dict[str, Record] = {r.refund_id: r for r in self.dataset.records}

    def close(self) -> None:
        self.store.close()

    def register(self, rec: Record) -> None:

        """登记客服系统新推来的单据；同一 refund_id 幂等覆盖。"""
        if rec.refund_id not in self.records:
            self.dataset.records.append(rec)
        self.records[rec.refund_id] = rec
        self.store.seed(
            Dataset(
                dataset_id=f"runtime-{rec.refund_id}",
                schema_version="runtime",
                amount_unit="分",
                produced_at=self.clock.now(),
                records=[rec],
            )
        )

    def _view(
        self,
        return_id: str | None,
        rec: Record | None = None,
        action: ActionCode | None = None,
        amount: float = 0.0,
        reply: str = "",
        queue: str = "",
        verdict: Verdict | None = None,
        row: ReturnOrderRow | None = None,
    ) -> CaseView:
        row = row or (self.store.return_row(return_id) if return_id else None)
        status = row["status"] if row else ""
        ac = (
            (action or ActionCode(row["action_code"]))
            if row
            else (action or ActionCode.AUTO_APPROVE_AND_REFUND)
        )
        amount = amount or (
            float(
                row["refunded_amount"]
                or row["approved_amount"]
                or row["requested_amount"]
            )
            if row
            else 0.0
        )
        reason = rec.reason.value if rec else (row["reason"] if row else "")
        pending = self.store.pending_task(return_id) if row and return_id else None
        return CaseView(
            return_id=return_id,
            status=status,
            status_label=STATUS_LABELS.get(status, status),
            action_code=ac.value,
            action_label=ACTION_LABELS[ac.value],
            amount=round(float(amount), 2),
            reply=reply or (row["reply"] or "" if row else ""),
            reason=reason,
            reason_label=REASON_LABELS.get(reason, reason or ""),
            queue=queue or (row["queue"] or "" if row else ""),
            queue_label=QUEUE_LABELS.get(queue or (row["queue"] or "" if row else ""), ""),
            refund_id=(rec.refund_id if rec else (row["refund_id"] if row else "")),
            after_sale_no=(rec.after_sale_no if rec else ""),
            risk_tier=verdict.tier.value if verdict else (row["risk_tier"] or "" if row else ""),
            trust_score=(
                verdict.trust_score
                if verdict
                else int(row["trust_score"]) if row["trust_score"] is not None else 100
            )
            if row
            else 100,
            rule_hits=verdict.hit_codes
            if verdict
            else loads(row["risk_json"], {}).get("hits", [])
            if row
            else [],
            pending=dict(pending) if pending else None,
            handoff=loads(row["handoff_json"], {}) if row else {},
            actions=["approve", "reject", "evidence"]
            if pending and pending["kind"] == "manual_review"
            else [],
        )

    def _apply(self, rec: Record, outcome: StepOutcome, return_id: str) -> CaseView:
        """把裁决映射到状态机/台账；只有明确失败才释放幂等占位。"""
        d, v = outcome.disposition, outcome.verdict
        queue = d.queue
        self.store.update_return(
            return_id,
            action_code=d.action.value,
            queue=queue,
            approved_amount=yuan(d.approved_cents) if d.approved_cents else rec.requested,
            risk_tier=v.tier.value,
            trust_score=v.trust_score,
            risk_json=dumps({"hits": v.hit_codes, "skipped": v.skipped_rules}),
        )
        # 显式节点表：动作码决定执行节点，节点返回可回放的状态流转/台账结果
        NODE_MAP[d.action](self.store, rec, d, return_id)
        reply = reply_of(
            d.action, rec, yuan(d.approved_cents) if d.approved_cents else rec.settled, queue
        )
        self.store.update_return(
            return_id, reply=reply, workflow_status=self.store.status_of(return_id)
        )
        self.store.mark_request(rec.refund_id, return_id, d.action.value)
        return self._view(
            return_id,
            rec,
            d.action,
            yuan(d.approved_cents) if d.approved_cents else rec.settled,
            reply,
            queue,
            v,
            row=self.store.return_row(return_id),
        )

    def submit_record(self, rec: Record) -> CaseView:
        self.records.setdefault(rec.refund_id, rec)
        existing = self.store.find_existing(rec)
        if existing:
            self.store.mark_request(
                rec.refund_id, existing, ActionCode.DEDUPE_RETURN_EXISTING.value
            )
            # 去重没有节点副作用；保留原单执行轨迹即可
            return self._view(
                existing,
                rec,
                ActionCode.DEDUPE_RETURN_EXISTING,
                0.0,
                reply_of(ActionCode.DEDUPE_RETURN_EXISTING, rec, 0.0, ""),
            )
        return_id = self.store.next_return_id()
        self.store.create_return(return_id, rec)
        outcome = run_steps(rec, stats=self.store.user_stats(rec.user_id))
        return self._apply(rec, outcome, return_id)

    def submit_refund_id(self, refund_id: str) -> CaseView:
        rec = self.find_record(refund_id=refund_id)
        if rec is None:
            raise KeyError(f"未找到退款单 {refund_id}")
        return self.submit_record(rec)

    def find_record(
        self,
        *,
        refund_id: str | None = None,
        order_id: str | None = None,
    ) -> Record | None:
        """优先使用运行时索引；未 seed 时从 refund_requests 原始快照恢复。"""
        if refund_id:
            rec = self.records.get(refund_id)
            if rec is not None:
                return rec
        if order_id:
            rec = next(
                (item for item in self.records.values() if item.order_id == order_id),
                None,
            )
            if rec is not None:
                return rec
        rec = self.store.load_record(refund_id=refund_id, order_id=order_id)
        if rec is not None:
            self.records[rec.refund_id] = rec
        return rec

    def process_batch(self) -> dict[str, Any]:
        buckets: dict[str, list[Any]] = {
            "auto_refunded": [],
            "auto_rejected": [],
            "held_inbound": [],
            "manual_queued": [],
            "deduped": [],
            "skipped": [],
        }
        for rec in self.dataset.records:
            if self.store.request_handled(rec.refund_id):
                buckets["skipped"].append(rec.refund_id)
                continue
            view = self.submit_record(rec)
            code = view.action_code
            key = (
                "auto_refunded"
                if code in {a.value for a in AUTO_ACTIONS}
                else "auto_rejected"
                if code in {a.value for a in REJECT_ACTIONS}
                else "held_inbound"
                if code == ActionCode.HOLD_UNTIL_RETURN_RECEIVED.value
                else "deduped"
                if code == ActionCode.DEDUPE_RETURN_EXISTING.value
                else "manual_queued"
            )
            buckets[key].append(
                {
                    "refund_id": rec.refund_id,
                    "scenario": rec.scenario,
                    "action": code,
                    "amount": view.amount,
                }
            )
        return {
            "total": len(self.dataset.records),
            "processed": sum(len(v) for v in buckets.values()) - len(buckets["skipped"]),
            "refunded_amount": round(self.store.refunded_amount(), 2),
            "auto_refunded": len(buckets["auto_refunded"]),
            "auto_rejected": len(buckets["auto_rejected"]),
            "held_inbound": len(buckets["held_inbound"]),
            "manual_queued": len(buckets["manual_queued"]),
            "deduped": len(buckets["deduped"]),
            "skipped": len(buckets["skipped"]),
            "details": buckets,
        }

    def resume_review(
        self,
        return_id: str,
        action: str,
        *,
        reviewer: str = "cs_01",
        note: str = "",
        amount: float | None = None,
    ) -> CaseView:
        task = self.store.pending_task(return_id)
        row = self.store.return_row(return_id)
        if not row:
            raise KeyError(return_id)
        if task is None:
            return self._view(return_id)
        if task["kind"] == "external":
            return self._view(return_id)  # 平台纠纷由外部工单驱动
        rec = self.find_record(refund_id=row["refund_id"])
        if action == "approve":
            self.store.resolve_task(return_id, "approve", reviewer, note)
            self.store.transition(return_id, WorkflowStatus.APPROVED, WorkflowStatus.MANUAL_REVIEW)
            if rec and rec.return_required:
                self.store.transition(
                    return_id, WorkflowStatus.AWAIT_SHIPMENT, WorkflowStatus.APPROVED
                )
            else:
                self.store.transition(return_id, WorkflowStatus.REFUNDING, WorkflowStatus.APPROVED)
                amt = (
                    amount
                    if amount is not None
                    else float(row["approved_amount"] or row["requested_amount"])
                )
                if self.store.claim_refund(return_id, amt):
                    self.store.refund(return_id, amt)
                    self.store.transition(
                        return_id, WorkflowStatus.REFUNDED, WorkflowStatus.REFUNDING
                    )
                    self.store.transition(return_id, WorkflowStatus.CLOSED, WorkflowStatus.REFUNDED)
        elif action == "reject":
            self.store.resolve_task(return_id, "reject", reviewer, note)
            self.store.transition(return_id, WorkflowStatus.REJECTED, WorkflowStatus.MANUAL_REVIEW)
        elif action == "evidence":
            self.store.resolve_task(return_id, "evidence", reviewer, note)
            self.store.transition(
                return_id, WorkflowStatus.AWAIT_EVIDENCE, WorkflowStatus.MANUAL_REVIEW
            )
            self.store.save_task(return_id, "evidence", {"reason": "要求补充举证"})
        else:
            raise ValueError("action 必须是 approve / reject / evidence")
        return self._view(return_id)

    def provide_evidence(self, return_id: str, urls: list[str]) -> CaseView:
        if not urls:
            raise ValueError("至少需要一条凭证链接")
        row = self.store.return_row(return_id)
        if not row:
            raise KeyError(return_id)
        self.store.update_return(return_id, evidence_json=dumps(list(urls)))
        self.store.resolve_task(return_id, "provided", "user", "补充举证")
        self.store.transition(return_id, WorkflowStatus.RISK_REVIEW, WorkflowStatus.AWAIT_EVIDENCE)
        rec = self.find_record(refund_id=row["refund_id"])
        if rec is None:
            raise KeyError(f"未找到退款单 {row['refund_id']}")
        rec.raw["evidence"] = list(urls)
        rec.evidence = tuple(urls)  # 举证后重新评估，避免 evidence -> risk 死循环
        outcome = run_steps(rec, stats=self.store.user_stats(row["user_id"]))
        self.store.mark_request(rec.refund_id, return_id, outcome.disposition.action.value)
        return self._apply(rec, outcome, return_id)

    def get_case(self, return_id: str) -> CaseView:
        if not self.store.return_row(return_id):
            raise KeyError(return_id)
        return self._view(return_id)

    def list_review_queue(self) -> list[OpenTask]:
        return self.store.open_tasks()

    def stats(self) -> dict[str, Any]:
        return self.store.stats()


__all__ = ["RefundService", "reply_of"]
