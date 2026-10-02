"""工作流执行节点表：动作码 -> 节点，显式、可回放、可单独验收。

编排层不再写一大段 if/else；每个节点只负责状态流转、退款台账、人工任务，
并返回 ExecutionResult 供 trace 逐阶段检验。
"""

from __future__ import annotations

from collections.abc import Callable

from app.core.tools.refund.ports import RefundStore
from app.domain.refund.common import yuan
from app.domain.refund.contracts import (
    ActionCode,
    Disposition,
    ExecutionResult,
    Record,
    ReturnStatus,
    WorkflowStatus,
)

AUTO_ACTIONS = {
    ActionCode.AUTO_APPROVE_AND_REFUND,
    ActionCode.AUTO_APPROVE_NO_RETURN,
    ActionCode.PARTIAL_REFUND_FREIGHT_ONLY,
}
REJECT_ACTIONS = {
    ActionCode.REJECT_AMOUNT_EXCEEDED,
    ActionCode.REJECT_ALREADY_REFUNDED,
    ActionCode.REJECT_ORDER_NOT_REFUNDABLE,
    ActionCode.RISK_REJECT,
}
MANUAL_ACTIONS = {
    ActionCode.ADJUST_TAX_EXCLUDED,
    ActionCode.MANUAL_APPROVAL,
    ActionCode.MANUAL_REVIEW_AND_RECON,
    ActionCode.QUERY_THEN_RECONCILE,
    ActionCode.RISK_HOLD_FOR_REVIEW,
}

Node = Callable[[RefundStore, Record, Disposition, str], ExecutionResult]


def _to(
    store: RefundStore,
    return_id: str,
    target: WorkflowStatus,
) -> str:
    """按当前状态流转一步，返回落库后的状态名。"""
    store.transition(
        return_id,
        target,
        WorkflowStatus(store.status_of(return_id)),
    )
    return target.value


def execute_auto(
    store: RefundStore,
    rec: Record,
    d: Disposition,
    return_id: str,
) -> ExecutionResult:
    """自动退款：approved → refunding → 抢台账 → 渠道 → refunded → closed。"""
    amount = yuan(d.approved_cents) if d.approved_cents else rec.settled
    path = [
        _to(store, return_id, WorkflowStatus.APPROVED),
        _to(store, return_id, WorkflowStatus.REFUNDING),
    ]
    if not store.claim_refund(return_id, amount):
        return ExecutionResult("auto_refund", path, 0.0, "", "台账已占用，未重复发起")
    try:
        store.refund(return_id, amount)
    except Exception:
        # 只有明确失败才释放占位；超时/未知结果不释放，转争议由人工核对渠道流水
        store.release_refund(return_id)
        path.append(_to(store, return_id, WorkflowStatus.DISPUTE))
        return ExecutionResult("auto_refund", path, 0.0, "", "渠道明确失败，转争议")
    path += [
        _to(store, return_id, WorkflowStatus.REFUNDED),
        _to(store, return_id, WorkflowStatus.CLOSED),
    ]
    return ExecutionResult("auto_refund", path, amount, "")


def execute_hold(
    store: RefundStore,
    rec: Record,
    d: Disposition,
    return_id: str,
) -> ExecutionResult:
    """挂起等入库：按退货状态逐级流转，不打款。"""
    path = [_to(store, return_id, WorkflowStatus.APPROVED)]
    if rec.return_status is not ReturnStatus.NONE:
        path.append(_to(store, return_id, WorkflowStatus.AWAIT_SHIPMENT))
    if rec.return_status in (ReturnStatus.IN_TRANSIT, ReturnStatus.RECEIVED):
        path.append(_to(store, return_id, WorkflowStatus.IN_TRANSIT))
    if rec.return_status is ReturnStatus.RECEIVED:
        path.append(_to(store, return_id, WorkflowStatus.ARRIVED))
    return ExecutionResult("hold", path, 0.0, "")


def execute_reject(
    store: RefundStore,
    rec: Record,
    d: Disposition,
    return_id: str,
) -> ExecutionResult:
    """自动驳回：risk_review → rejected。"""
    return ExecutionResult(
        "reject",
        [_to(store, return_id, WorkflowStatus.REJECTED)],
        0.0,
        "",
    )


def execute_dispute(
    store: RefundStore,
    rec: Record,
    d: Disposition,
    return_id: str,
) -> ExecutionResult:
    """平台纠纷：dispute + 外部工单任务（无 interrupt）。"""
    path = [_to(store, return_id, WorkflowStatus.DISPUTE)]
    queue = d.queue or "platform_dispute"
    store.save_task(return_id, queue, {"reason": rec.reason.value})
    return ExecutionResult("dispute", path, 0.0, queue)


def execute_manual(
    store: RefundStore,
    rec: Record,
    d: Disposition,
    return_id: str,
) -> ExecutionResult:
    """人工/举证/对账：manual_review + review_tasks，由客服 agent 写回结论。"""
    path = [_to(store, return_id, WorkflowStatus.MANUAL_REVIEW)]
    queue = d.queue or "after_sales"
    store.save_task(
        return_id,
        queue,
        {"amount": rec.requested, "reason": rec.reason_label, "action": d.action.value},
    )
    return ExecutionResult("manual", path, 0.0, queue)


def execute_dedupe(
    store: RefundStore,
    rec: Record,
    d: Disposition,
    return_id: str,
) -> ExecutionResult:
    """去重：返回原单，不执行任何节点副作用。"""
    return ExecutionResult("dedupe", [], 0.0, "", "返回原单")


NODE_MAP: dict[ActionCode, Node] = {
    **{a: execute_auto for a in AUTO_ACTIONS},
    **{a: execute_reject for a in REJECT_ACTIONS},
    **{a: execute_manual for a in MANUAL_ACTIONS},
    ActionCode.HOLD_UNTIL_RETURN_RECEIVED: execute_hold,
    ActionCode.DISPUTE_EVIDENCE_FLOW: execute_dispute,
    ActionCode.DEDUPE_RETURN_EXISTING: execute_dedupe,
}

__all__ = ["AUTO_ACTIONS", "MANUAL_ACTIONS", "NODE_MAP", "REJECT_ACTIONS"]
