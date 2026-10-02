"""活动层 2：风控评估。20 条规则逐条打分，输出 Verdict。

规则是纯函数：输入 Signals + Thresholds，输出 RuleHit 或 None；不计分、不落库。
已确认口径：R19/R20 去重、C 档 ≤200 自动、D 档仍需举证/人工。
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from app.domain.refund.common import now, yuan
from app.domain.refund.contracts import (
    CAP_ACCOUNT_AGE,
    CAP_ADDRESS_DETAIL,
    CAP_BUYER_RISK,
    CAP_CATEGORY,
    CAP_COUPON_POLICY,
    CAP_DELIVERY_TIME,
    CAP_DEVICE,
    CAP_EVIDENCE,
    CAP_HISTORY,
    CAP_OPENED,
    CAP_PROMISE,
    CONFIG,
    NO_FAULT_REASONS,
    QUALITY_REASONS,
    AppConfig,
    Record,
    RefundPlan,
    RefundType,
    ReturnReason,
    RiskTier,
    RuleHit,
    RuleSpec,
    Signals,
    Stats,
    Thresholds,
    Verdict,
)

RULES: list[RuleSpec] = []
RuleCallable = Callable[[Signals, Thresholds], "RuleHit | None"]
RuleDecorator = Callable[[RuleCallable], RuleCallable]


def rule(code: str, requires: Iterable[str] = ()) -> RuleDecorator:
    """注册一条风控规则。"""

    def deco(fn: RuleCallable) -> RuleCallable:
        RULES.append(RuleSpec(code, fn, frozenset(requires)))
        return fn

    return deco


def hit(
    code: str,
    title: str,
    weight: int,
    detail: str,
    **flags: Any,
) -> RuleHit:
    """构造规则命中结果。"""
    return RuleHit(code, title, weight, detail, **flags)


def capabilities_of(rec: Record, history_known: bool) -> frozenset[str]:
    """根据当前可获取的数据返回规则能力位。"""
    caps = {"amounts", "order_status", "buyer_risk", "evidence"}
    if rec.delivered_at:
        caps.add(CAP_DELIVERY_TIME)
    if history_known:
        caps.add(CAP_HISTORY)
    return frozenset(caps)


@rule("R01", {CAP_ACCOUNT_AGE})
def r01(s: Signals, cfg: Thresholds) -> RuleHit | None:
    # 当前数据无注册时间，能力位缺失时不会执行
    age = (s.now - (s.rec.delivered_at or s.now)).days
    return (
        hit(
            "R01",
            "新账号低单量即申请退款",
            -15 if s.rec.requested >= 200 else -10,
            f"账号注册 {age} 天",
        )
        if age <= cfg.new_account_days
        else None
    )


@rule("R02", {CAP_HISTORY})
def r02(s: Signals, cfg: Thresholds) -> RuleHit | None:
    n = s.stats.return_count
    if n >= cfg.high_freq_return_count_severe:
        return hit(
            "R02", "高频退货", -30, f"近 {cfg.stat_window_days} 天 {n} 次", requires_manual=True
        )
    if n >= cfg.high_freq_return_count:
        return hit("R02", "退货频次偏高", -20, f"近 {cfg.stat_window_days} 天 {n} 次")
    return None


@rule("R03", {CAP_HISTORY})
def r03(s: Signals, cfg: Thresholds) -> RuleHit | None:
    if (
        s.stats.order_count >= cfg.return_rate_min_orders
        and s.stats.return_rate >= cfg.return_rate_high
    ):
        return hit("R03", "退货率异常", -20, f"退货率 {s.stats.return_rate:.0%}")
    return None


@rule("R04")
def r04(s: Signals, cfg: Thresholds) -> RuleHit | None:
    amount = yuan(s.rec.goods_fee + s.rec.freight_fee + s.rec.tax_fee)
    if amount >= cfg.high_value_amount and s.rec.reason.value in NO_FAULT_REASONS:
        return hit(
            "R04", "高客单价无理由退货", -12, f"订单金额 {amount:.2f}", requires_evidence=True
        )
    return None


@rule("R05", {CAP_HISTORY})
def r05(s: Signals, cfg: Thresholds) -> RuleHit | None:
    if (
        s.rec.refund_type is RefundType.REFUND_ONLY
        and s.stats.refund_only_count >= cfg.refund_only_abuse_count
    ):
        return hit("R05", "仅退款不退货滥用", -20, f"历史 {s.stats.refund_only_count} 次仅退款")
    return None


@rule("R06", {CAP_EVIDENCE})
def r06(s: Signals, cfg: Thresholds) -> RuleHit | None:
    if s.rec.reason.value in QUALITY_REASONS and not s.rec.evidence:
        return hit("R06", "商家责任理由未举证", -8, "质量类理由无凭证", requires_evidence=True)
    return None


@rule("R07", {CAP_HISTORY})
def r07(s: Signals, cfg: Thresholds) -> RuleHit | None:
    if (
        s.rec.reason is ReturnReason.MISSING_PARTS
        and s.stats.missing_claim_count >= cfg.missing_claim_repeat
    ):
        return hit(
            "R07",
            "少件/空包投诉反复出现",
            -22,
            "历史少件投诉",
            requires_evidence=True,
            requires_manual=True,
        )
    return None


@rule("R08", {CAP_ADDRESS_DETAIL})
def r08(s: Signals, cfg: Thresholds) -> RuleHit | None:
    return (
        hit(
            "R08",
            "同收货地址多账号聚集",
            -20,
            f"{s.address_account_count} 个账号",
            requires_manual=True,
        )
        if s.address_account_count >= cfg.address_cluster_accounts
        else None
    )


@rule("R09", {CAP_DEVICE})
def r09(s: Signals, cfg: Thresholds) -> RuleHit | None:
    return (
        hit(
            "R09", "同设备多账号聚集", -18, f"{s.device_account_count} 个账号", requires_manual=True
        )
        if s.device_account_count >= cfg.device_cluster_accounts
        else None
    )


@rule("R10", {CAP_CATEGORY, CAP_OPENED})
def r10(s: Signals, cfg: Thresholds) -> RuleHit | None:
    return (
        hit(
            "R10",
            "不可二次销售类目已拆封",
            -25,
            "类目/拆封命中",
            requires_evidence=True,
            requires_manual=True,
        )
        if False
        else None
    )


@rule("R11", {CAP_DELIVERY_TIME})
def r11(s: Signals, cfg: Thresholds) -> RuleHit | None:
    d = s.days_since_delivery
    return (
        hit("R11", "超出售后申请时效", -15, f"签收后 {d:.1f} 天", requires_manual=True)
        if d and d > cfg.return_window_days
        else None
    )


@rule("R12", {CAP_DELIVERY_TIME})
def r12(s: Signals, cfg: Thresholds) -> RuleHit | None:
    h = s.hours_since_delivery
    return (
        hit("R12", "签收后极短时间内申请退款", -10, f"签收后 {h:.1f} 小时")
        if h is not None
        and 0 <= h <= cfg.fast_return_hours
        and s.rec.requested >= cfg.fast_return_min_amount
        else None
    )


@rule("R13")
def r13(s: Signals, cfg: Thresholds) -> RuleHit | None:
    return (
        hit("R13", "申请退款金额超过实付", -30, "申请额大于实付", requires_manual=True)
        if s.rec.requested > s.rec.paid + 0.01
        else None
    )


@rule("R14")
def r14(s: Signals, cfg: Thresholds) -> RuleHit | None:
    # 未接入黑名单源时恒不命中；接入后只需提供 blacklisted 信号
    return (
        hit("R14", "历史确认欺诈账号", -100, "黑名单", hard_block=True) if False else None
    )


@rule("R15", {CAP_COUPON_POLICY})
def r15(s: Signals, cfg: Thresholds) -> RuleHit | None:
    return (
        hit("R15", "不可退优惠券仍要求全额退款", -12, "券政策命中", requires_manual=True)
        if False
        else None
    )


@rule("R16", {CAP_PROMISE})
def r16(s: Signals, cfg: Thresholds) -> RuleHit | None:
    return hit("R16", "客服已有明确承诺", 40, s.promise_note) if s.has_promise else None


@rule("R17", {CAP_HISTORY})
def r17(s: Signals, cfg: Thresholds) -> RuleHit | None:
    return (
        hit("R17", "高信用长期客户", 15, "长期零仅退款")
        if s.stats.order_count >= cfg.good_credit_min_orders and s.stats.refund_only_count == 0
        else None
    )


@rule("R18", {CAP_HISTORY})
def r18(s: Signals, cfg: Thresholds) -> RuleHit | None:
    return (
        hit("R18", "中高价值商品多次退货", -8, "多次退货")
        if s.stats.return_count >= 3 and yuan(s.rec.goods_fee) >= 300
        else None
    )


@rule("R19", {CAP_BUYER_RISK})
def r19(s: Signals, cfg: Thresholds) -> RuleHit | None:
    rate = s.rec.user_refund_rate_30d
    if rate >= cfg.buyer_refund_rate_high:
        return hit(
            "R19", "近 30 天退款率超过高风险阈值", -25, f"退款率 {rate:.0%}", requires_manual=True
        )
    if rate >= cfg.buyer_refund_rate_watch:
        return hit("R19", "近 30 天退款率偏高（抽检）", -10, f"退款率 {rate:.0%}")
    return None


@rule("R20", {CAP_BUYER_RISK})
def r20(s: Signals, cfg: Thresholds) -> RuleHit | None:
    level = s.rec.user_risk_level.upper()
    if level == "HIGH":
        return hit("R20", "买家风险等级为高", -30, "HIGH", requires_manual=True, risk_hold=True)
    if level == "MEDIUM":
        return hit("R20", "买家风险等级为中", -8, "MEDIUM")
    return None


def _user_message(plan: RefundPlan, amount: float) -> str:
    return {
        RefundPlan.REJECT: "本次退款暂不支持自助处理，可补充凭证或转人工申诉。",
        RefundPlan.EVIDENCE_REQUIRED: "请补充商品问题照片或开箱视频。",
        RefundPlan.PARTIAL_REFUND: f"可提供 {amount:.2f} 元折价补偿。",
        RefundPlan.RETURN_REFUND: "已通过审核，请寄回商品，验收后原路退款。",
    }.get(plan, f"已通过审核，{amount:.2f} 元将原路退回。")


def assess(
    rec: Record,
    stats: Stats | None = None,
    config: AppConfig = CONFIG,
    history_known: bool = False,
) -> Verdict:
    """规则打分；输出只影响建议/人工标记，不直接改状态。"""
    cfg, st = config.thresholds, stats or Stats()
    s = Signals(rec, st, history_known, capabilities_of(rec, history_known), now=now())
    hits, skipped = [], []
    for spec in RULES:
        if not s.supports(spec.requires):
            skipped.append(spec.code)
            continue
        h = spec(s, cfg)
        if h:
            hits.append(h)
    # R19/R20 描述同一买家信号，只保留一条
    if any(h.code == "R19" for h in hits) and any(h.code == "R20" for h in hits):
        drop = "R19" if any(h.code == "R20" and h.risk_hold for h in hits) else "R20"
        hits = [h for h in hits if h.code != drop]
    trust = max(0, min(100, 100 + sum(h.weight for h in hits)))
    hard = any(h.hard_block for h in hits)
    tiers = config.tiers
    tier = (
        RiskTier.D
        if hard or trust < tiers.c_min
        else RiskTier.C
        if trust < tiers.b_min
        else RiskTier.B
        if trust < tiers.a_min
        else RiskTier.A
    )
    settled = min(rec.requested, rec.refundable)
    if any(h.requires_manual for h in hits) and tier in (RiskTier.A, RiskTier.B):
        tier = RiskTier.C
    if hard:
        plan, amount = RefundPlan.REJECT, 0.0
    elif tier is RiskTier.D:
        plan, amount = RefundPlan.EVIDENCE_REQUIRED, 0.0
    elif tier is RiskTier.C:
        plan, amount = (
            (RefundPlan.PARTIAL_REFUND, round(settled * tiers.partial_refund_ratio, 2))
            if rec.reason.value in NO_FAULT_REASONS and settled <= tiers.low_cost_partial_max
            else (RefundPlan.RETURN_REFUND, 0.0)
        )
    elif tier is RiskTier.B:
        plan, amount = (
            (RefundPlan.REFUND_ONLY, settled)
            if settled <= tiers.auto_refund_max_b
            else (RefundPlan.RETURN_REFUND, settled)
        )
    else:
        plan, amount = (
            (RefundPlan.REFUND_ONLY, settled)
            if settled <= tiers.auto_refund_max_a
            else (RefundPlan.RETURN_REFUND, settled)
        )
    c_over_cap = tier is RiskTier.C and settled > tiers.c_tier_auto_max
    requires_manual = (
        hard or tier is RiskTier.D or c_over_cap or any(h.requires_manual for h in hits)
    )
    requires_evidence = (
        tier in (RiskTier.C, RiskTier.D)
        and any(h.requires_evidence for h in hits)
        and not rec.evidence
    )
    risk_hold = any(h.risk_hold for h in hits)
    rationale = [f"{h.code} {h.title}({h.weight:+d})" for h in hits] or ["未命中风险规则"]
    if skipped:
        rationale.append("跳过：" + "、".join(dict.fromkeys(skipped)))
    rationale.append(f"信任分 {trust}/100，档位 {tier.value}")
    return Verdict(
        trust,
        tier,
        hits,
        list(dict.fromkeys(skipped)),
        plan,
        amount,
        requires_manual,
        requires_evidence,
        risk_hold,
        hard,
        _user_message(plan, amount),
        rationale,
    )


__all__ = ["RULES", "assess", "capabilities_of", "hit", "rule"]
