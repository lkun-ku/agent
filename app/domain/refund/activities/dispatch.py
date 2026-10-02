"""活动层 4：动作裁决。唯一优先级表，15 选 1。

新增场景只允许在这里加一行；节点/服务不得另写业务 if。
"""

from __future__ import annotations

from app.domain.refund.activities.eligibility import check_eligibility, failed_codes
from app.domain.refund.activities.risk import assess
from app.domain.refund.contracts import (
    CONFIG,
    ActionCode,
    AppConfig,
    CheckCode,
    CheckResult,
    Dataset,
    Disposition,
    Record,
    Stats,
    StepOutcome,
    Verdict,
)


def decide(
    rec: Record, checks: list[CheckResult], verdict: Verdict, existing: bool = False
) -> Disposition:
    """唯一动作优先级表；从上到下第一个命中即返回。"""
    codes = failed_codes(checks)
    settled = rec.refund_fee if rec.refund_fee <= rec.refundable_fee else rec.refundable_fee
    if existing:
        return Disposition(ActionCode.DEDUPE_RETURN_EXISTING, "幂等键/同订单命中已受理单")
    if CheckCode.ORDER_NOT_PAID in codes or CheckCode.ORDER_CLOSED in codes:
        return Disposition(ActionCode.REJECT_ORDER_NOT_REFUNDABLE, "订单不可退")
    if CheckCode.ALREADY_REFUNDED in codes:
        return Disposition(ActionCode.REJECT_ALREADY_REFUNDED, "订单已退款")
    if CheckCode.CHANNEL_TIMEOUT in codes:
        return Disposition(ActionCode.QUERY_THEN_RECONCILE, "只查不发", queue="reconciliation")
    if CheckCode.CHANNEL_ERROR in codes:
        return Disposition(
            ActionCode.MANUAL_REVIEW_AND_RECON,
            "支付对账",
            queue="payment_recon",
            approved_cents=settled,
        )
    if CheckCode.PLATFORM_INTERVENE in codes:
        return Disposition(ActionCode.DISPUTE_EVIDENCE_FLOW, "平台介入", queue="platform_dispute")
    if CheckCode.TAX_EXCLUDED in codes:
        return Disposition(
            ActionCode.ADJUST_TAX_EXCLUDED,
            "税费不退",
            queue="amount_adjust",
            approved_cents=rec.refundable_fee,
        )
    if CheckCode.AMOUNT_EXCEEDED in codes:
        return Disposition(ActionCode.REJECT_AMOUNT_EXCEEDED, "超出可退金额")
    if CheckCode.HIGH_AMOUNT in codes:
        return Disposition(
            ActionCode.MANUAL_APPROVAL, "超免审上限", queue="approval", approved_cents=settled
        )
    if verdict.hard_block:
        return Disposition(ActionCode.RISK_REJECT, "风控硬规则")
    if verdict.risk_hold:
        return Disposition(
            ActionCode.RISK_HOLD_FOR_REVIEW, "买家高风险冻结", queue="risk", approved_cents=settled
        )
    if CheckCode.RETURN_PENDING in codes:
        return Disposition(ActionCode.HOLD_UNTIL_RETURN_RECEIVED, "等退货入库")
    if CheckCode.FREIGHT_ONLY in codes:
        return Disposition(
            ActionCode.PARTIAL_REFUND_FREIGHT_ONLY,
            "仅退运费",
            approved_cents=min(rec.refund_fee, rec.freight_fee),
        )
    if CheckCode.VIRTUAL_NO_RETURN in codes:
        return Disposition(ActionCode.AUTO_APPROVE_NO_RETURN, "虚拟免退货", approved_cents=settled)
    if verdict.requires_manual:
        return Disposition(
            ActionCode.MANUAL_APPROVAL, "风控要求人工", queue="after_sales", approved_cents=settled
        )
    return Disposition(ActionCode.AUTO_APPROVE_AND_REFUND, "自动通过", approved_cents=settled)


def run_steps(rec: Record, config: AppConfig = CONFIG, stats: Stats | None = None) -> StepOutcome:
    """纯步骤：不落库、不起编排，可离线回归。"""
    checks = check_eligibility(rec, config)
    verdict = assess(rec, stats, config, history_known=stats is not None)
    return StepOutcome(rec, checks, verdict, decide(rec, checks, verdict))


def run_dataset(ds: Dataset) -> list[StepOutcome]:
    """纯步骤也模拟幂等去重：同一幂等键/订单的第二条单据返回原单动作。"""
    seen: dict[str, str] = {}
    results: list[StepOutcome] = []
    for rec in ds.records:
        outcome = run_steps(rec)
        key = rec.idempotency_key or rec.order_id
        if key in seen:
            outcome = StepOutcome(
                rec,
                outcome.checks,
                outcome.verdict,
                Disposition(
                    ActionCode.DEDUPE_RETURN_EXISTING, f"幂等键 {key} 已由 {seen[key]} 受理"
                ),
            )
        else:
            seen[key] = rec.refund_id
        results.append(outcome)
    return results


__all__ = ["decide", "run_dataset", "run_steps"]
