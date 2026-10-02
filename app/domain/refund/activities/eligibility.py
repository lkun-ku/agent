"""活动层 3：可退性校验。16 个 CheckCode 是动作裁决的输入。

纯函数；金额硬约束在这里拦截，不允许进入渠道调用。
"""

from __future__ import annotations

from decimal import Decimal

from app.domain.refund.common import paid_cents, to_cents
from app.domain.refund.contracts import (
    CONFIG,
    AppConfig,
    CheckCode,
    CheckResult,
    OrderStatus,
    Record,
    RefundType,
    ReturnStatus,
)


def failed_codes(checks: list[CheckResult]) -> set[CheckCode]:
    return {c.code for c in checks if not c.passed}


def tax_adjusted(rec: Record) -> bool:
    return (
        rec.tax_fee > 0
        and rec.refundable_fee == rec.paid_fee - rec.tax_fee
        and rec.refund_fee > rec.refundable_fee
    )


def check_eligibility(rec: Record, config: AppConfig = CONFIG) -> list[CheckResult]:
    """11 项业务校验 + 金额自检；失败码交给 dispatch 决定动作。"""
    cfg = config.thresholds
    paid_ok = rec.paid_fee > 0 and bool(rec.payment_no)
    closed = rec.order_status is OrderStatus.CLOSED
    refunded = rec.order_status is OrderStatus.REFUNDED or (
        rec.refundable_fee == 0 and rec.previous_refund_id
    )
    exceeded = rec.refund_fee > rec.refundable_fee and not tax_adjusted(rec)
    limit = cfg.auto_refund_max_amount
    timeout = rec.channel_error_code == "CHANNEL_TIMEOUT"
    error = bool(rec.channel_error_code) and not timeout
    pending = rec.return_required and rec.return_status in (
        ReturnStatus.WAIT_BUYER_SEND,
        ReturnStatus.IN_TRANSIT,
    )
    expected_paid = paid_cents(rec.goods_fee, rec.freight_fee, rec.tax_fee, rec.discount_fee)
    unpaid = rec.paid_fee == 0 and not rec.previous_refund_id
    pairs = [
        (CheckCode.ORDER_NOT_PAID, paid_ok, "支付流水/实付校验"),
        (CheckCode.ORDER_CLOSED, not closed, "订单状态校验"),
        (CheckCode.ALREADY_REFUNDED, not refunded, "历史退款校验"),
        (CheckCode.TAX_EXCLUDED, not tax_adjusted(rec), "跨境税费不退"),
        (CheckCode.AMOUNT_EXCEEDED, not exceeded, "申请额不超过可退"),
        (CheckCode.HIGH_AMOUNT, rec.refundable_fee <= to_cents(Decimal(str(limit))), "免审上限"),
        (CheckCode.PLATFORM_INTERVENE, not rec.platform_intervened, "平台介入"),
        (CheckCode.CHANNEL_TIMEOUT, not timeout, "渠道超时"),
        (CheckCode.CHANNEL_ERROR, not error, "渠道异常"),
        (CheckCode.RETURN_PENDING, not pending, "退货待入库"),
        (CheckCode.FREIGHT_ONLY, rec.refund_type is not RefundType.FREIGHT_ONLY, "仅退运费"),
        (
            CheckCode.VIRTUAL_NO_RETURN,
            rec.order_status is not OrderStatus.DELIVERED_VIRTUAL,
            "虚拟商品",
        ),
        (CheckCode.PAID_EQUATION_MISMATCH, unpaid or expected_paid == rec.paid_fee, "实付公式"),
        (
            CheckCode.REFUNDABLE_MISMATCH,
            unpaid and rec.refundable_fee == 0 or rec.refundable_fee <= rec.paid_fee,
            "可退上限",
        ),
        (CheckCode.REFUND_OVER_PAID, unpaid or rec.refund_fee <= rec.paid_fee, "申请额不超过实付"),
    ]
    return [CheckResult(code, ok, note) for code, ok, note in pairs]


__all__ = ["check_eligibility", "failed_codes", "tax_adjusted"]
