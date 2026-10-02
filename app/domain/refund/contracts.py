# ruff: noqa: UP042
"""契约层：工作流输入/输出的标准定义。

只放枚举、标签、阈值配置和 DTO，不含任何 IO 或判定逻辑；
依赖方向：activities / workflow / adapters / interfaces -> contracts -> common。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from app.domain.refund.common import now, yuan


# ── 枚举 ────────────────────────────────────────────────
class ActionCode(str, Enum):
    AUTO_APPROVE_AND_REFUND = "AUTO_APPROVE_AND_REFUND"
    AUTO_APPROVE_NO_RETURN = "AUTO_APPROVE_NO_RETURN"
    PARTIAL_REFUND_FREIGHT_ONLY = "PARTIAL_REFUND_FREIGHT_ONLY"
    ADJUST_TAX_EXCLUDED = "ADJUST_TAX_EXCLUDED"
    HOLD_UNTIL_RETURN_RECEIVED = "HOLD_UNTIL_RETURN_RECEIVED"
    DEDUPE_RETURN_EXISTING = "DEDUPE_RETURN_EXISTING"
    REJECT_AMOUNT_EXCEEDED = "REJECT_AMOUNT_EXCEEDED"
    REJECT_ALREADY_REFUNDED = "REJECT_ALREADY_REFUNDED"
    REJECT_ORDER_NOT_REFUNDABLE = "REJECT_ORDER_NOT_REFUNDABLE"
    MANUAL_APPROVAL = "MANUAL_APPROVAL"
    MANUAL_REVIEW_AND_RECON = "MANUAL_REVIEW_AND_RECON"
    QUERY_THEN_RECONCILE = "QUERY_THEN_RECONCILE"
    RISK_HOLD_FOR_REVIEW = "RISK_HOLD_FOR_REVIEW"
    DISPUTE_EVIDENCE_FLOW = "DISPUTE_EVIDENCE_FLOW"
    RISK_REJECT = "RISK_REJECT"


class WorkflowStatus(str, Enum):
    RISK_REVIEW = "risk_review"
    APPROVED = "approved"
    AWAIT_EVIDENCE = "await_evidence"
    MANUAL_REVIEW = "manual_review"
    REJECTED = "rejected"
    AWAIT_SHIPMENT = "await_shipment"
    IN_TRANSIT = "in_transit"
    ARRIVED = "arrived"
    INSPECTING = "inspecting"
    DISPUTE = "dispute"
    REFUNDING = "refunding"
    REFUNDED = "refunded"
    CLOSED = "closed"


class OrderStatus(str, Enum):
    PAID_UNSHIPPED = "PAID_UNSHIPPED"
    SHIPPED = "SHIPPED"
    RECEIVED = "RECEIVED"
    REFUNDED = "REFUNDED"
    CLOSED = "CLOSED"
    DELIVERED_VIRTUAL = "DELIVERED_VIRTUAL"


class ReturnStatus(str, Enum):
    NONE = "NONE"
    WAIT_BUYER_SEND = "WAIT_BUYER_SEND"
    IN_TRANSIT = "IN_TRANSIT"
    RECEIVED = "RECEIVED"


class RefundType(str, Enum):
    REFUND_ONLY = "REFUND_ONLY"
    RETURN_AND_REFUND = "RETURN_AND_REFUND"
    FREIGHT_ONLY = "FREIGHT_ONLY"


class RefundScope(str, Enum):
    FULL = "FULL"
    PARTIAL = "PARTIAL"


class RefundPlan(str, Enum):
    REFUND_ONLY = "refund_only"
    RETURN_REFUND = "return_refund"
    EXCHANGE = "exchange"
    RESHIP = "reship"
    PARTIAL_REFUND = "partial_refund"
    EVIDENCE_REQUIRED = "evidence_required"
    REJECT = "reject"


class ReturnReason(str, Enum):
    QUALITY = "quality"
    NOT_AS_DESCRIBED = "not_as_described"
    WRONG_ITEM = "wrong_item"
    MISSING_PARTS = "missing_parts"
    NO_LONGER_NEEDED = "no_longer_needed"
    SIZE_ISSUE = "size_issue"
    LATE_DELIVERY = "late_delivery"
    NOT_RECEIVED = "not_received"
    SIGNED_NOT_RECEIVED = "signed_not_received"
    VIRTUAL_NOT_RECEIVED = "virtual_not_received"
    FREIGHT_DISPUTE = "freight_dispute"
    LOGISTICS_STALE = "logistics_stale"
    SELLER_OUT_OF_STOCK = "seller_out_of_stock"
    OTHER = "other"


class RiskTier(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class CheckCode(str, Enum):
    ORDER_NOT_PAID = "ORDER_NOT_PAID"
    ORDER_CLOSED = "ORDER_CLOSED"
    ALREADY_REFUNDED = "ALREADY_REFUNDED"
    AMOUNT_EXCEEDED = "AMOUNT_EXCEEDED"
    TAX_EXCLUDED = "TAX_EXCLUDED"
    HIGH_AMOUNT = "HIGH_AMOUNT"
    PLATFORM_INTERVENE = "PLATFORM_INTERVENE"
    CHANNEL_TIMEOUT = "CHANNEL_TIMEOUT"
    CHANNEL_ERROR = "CHANNEL_ERROR"
    RETURN_PENDING = "RETURN_PENDING"
    FREIGHT_ONLY = "FREIGHT_ONLY"
    VIRTUAL_NO_RETURN = "VIRTUAL_NO_RETURN"
    SLA_OVERDUE = "SLA_OVERDUE"
    PAID_EQUATION_MISMATCH = "PAID_EQUATION_MISMATCH"
    REFUNDABLE_MISMATCH = "REFUNDABLE_MISMATCH"
    REFUND_OVER_PAID = "REFUND_OVER_PAID"


class RefundRequestStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    ABNORMAL = "ABNORMAL"
    SUCCESS = "SUCCESS"
    CLOSED = "CLOSED"


# ── 标签、映射与状态机 ───────────────────────────────────
ACTION_LABELS = {
    "AUTO_APPROVE_AND_REFUND": "审核通过并发起退款",
    "AUTO_APPROVE_NO_RETURN": "免退货自动通过",
    "PARTIAL_REFUND_FREIGHT_ONLY": "仅退运费",
    "ADJUST_TAX_EXCLUDED": "调整金额（税费不退）",
    "HOLD_UNTIL_RETURN_RECEIVED": "挂起等待退货入库",
    "DEDUPE_RETURN_EXISTING": "幂等去重返回原单",
    "REJECT_AMOUNT_EXCEEDED": "驳回（超出可退金额）",
    "REJECT_ALREADY_REFUNDED": "驳回（已退款）",
    "REJECT_ORDER_NOT_REFUNDABLE": "驳回（订单不可退）",
    "MANUAL_APPROVAL": "转人工审批",
    "MANUAL_REVIEW_AND_RECON": "转人工并进入对账",
    "QUERY_THEN_RECONCILE": "先查询后对账",
    "RISK_HOLD_FOR_REVIEW": "风控冻结待复核",
    "DISPUTE_EVIDENCE_FLOW": "转纠纷举证",
    "RISK_REJECT": "风控拒绝",
}
REASON_CODE_MAP = {
    "SEVEN_DAY_NO_REASON": ReturnReason.NO_LONGER_NEEDED,
    "QUALITY_ISSUE": ReturnReason.QUALITY,
    "GOODS_DAMAGED": ReturnReason.QUALITY,
    "NOT_AS_DESCRIBED": ReturnReason.NOT_AS_DESCRIBED,
    "WRONG_ITEM": ReturnReason.WRONG_ITEM,
    "MISSING_PARTS": ReturnReason.MISSING_PARTS,
    "SIZE_ISSUE": ReturnReason.SIZE_ISSUE,
    "NOT_RECEIVED": ReturnReason.NOT_RECEIVED,
    "SIGNED_NOT_RECEIVED": ReturnReason.SIGNED_NOT_RECEIVED,
    "VIRTUAL_NOT_RECEIVED": ReturnReason.VIRTUAL_NOT_RECEIVED,
    "FREIGHT_DISPUTE": ReturnReason.FREIGHT_DISPUTE,
    "LOGISTICS_STALE": ReturnReason.LOGISTICS_STALE,
    "SELLER_OUT_OF_STOCK": ReturnReason.SELLER_OUT_OF_STOCK,
    "OTHER": ReturnReason.OTHER,
}
REASON_LABELS = {
    "quality": "质量问题/破损",
    "not_as_described": "描述不符",
    "wrong_item": "错发/漏发",
    "missing_parts": "少件/配件缺失",
    "no_longer_needed": "不想要了",
    "size_issue": "尺码不合适",
    "late_delivery": "物流超时",
    "not_received": "未收到货",
    "signed_not_received": "已签收未收到",
    "virtual_not_received": "虚拟商品未到账",
    "freight_dispute": "运费争议",
    "logistics_stale": "物流长时间未更新",
    "seller_out_of_stock": "卖家缺货",
    "other": "其他",
}
PLAN_LABELS = {
    "refund_only": "仅退款",
    "return_refund": "退货退款",
    "exchange": "换货",
    "reship": "补发",
    "partial_refund": "部分退款/折价",
    "evidence_required": "补充举证",
    "reject": "拒绝并给出申诉通道",
}
STATUS_LABELS = {
    "risk_review": "风控评估中",
    "approved": "审核通过",
    "await_evidence": "等待举证",
    "manual_review": "人工审核中",
    "rejected": "已拒绝",
    "await_shipment": "待用户寄回",
    "in_transit": "退货在途",
    "arrived": "退货已入库",
    "inspecting": "验收中",
    "dispute": "争议/纠纷",
    "refunding": "退款中",
    "refunded": "已退款",
    "closed": "已关闭",
}
ORDER_STATUS_LABELS = {
    "PAID_UNSHIPPED": "待发货",
    "SHIPPED": "已发货",
    "RECEIVED": "已签收",
    "REFUNDED": "已退款",
    "CLOSED": "已关闭",
    "DELIVERED_VIRTUAL": "虚拟商品已发货",
}
QUEUE_LABELS = {
    "approval": "人工审批",
    "risk": "风控复核",
    "amount_adjust": "金额核对",
    "payment_recon": "支付对账",
    "reconciliation": "渠道对账",
    "platform_dispute": "平台纠纷",
    "payment": "支付核对",
    "evidence": "补充举证",
    "after_sales": "售后专员",
}
QUALITY_REASONS = frozenset(
    {"wrong_item", "not_as_described", "quality", "missing_parts", "signed_not_received"}
)
NO_FAULT_REASONS = frozenset(
    {
        "size_issue",
        "freight_dispute",
        "no_longer_needed",
        "virtual_not_received",
        "late_delivery",
        "other",
        "logistics_stale",
    }
)
ALLOWED_TRANSITIONS = {
    WorkflowStatus.RISK_REVIEW: {
        WorkflowStatus.APPROVED,
        WorkflowStatus.AWAIT_EVIDENCE,
        WorkflowStatus.MANUAL_REVIEW,
        WorkflowStatus.DISPUTE,
        WorkflowStatus.REJECTED,
        WorkflowStatus.CLOSED,
    },
    WorkflowStatus.APPROVED: {
        WorkflowStatus.AWAIT_SHIPMENT,
        WorkflowStatus.REFUNDING,
        WorkflowStatus.CLOSED,
    },
    WorkflowStatus.AWAIT_EVIDENCE: {
        WorkflowStatus.RISK_REVIEW,
        WorkflowStatus.MANUAL_REVIEW,
        WorkflowStatus.REJECTED,
        WorkflowStatus.CLOSED,
    },
    WorkflowStatus.MANUAL_REVIEW: {
        WorkflowStatus.APPROVED,
        WorkflowStatus.AWAIT_EVIDENCE,
        WorkflowStatus.REJECTED,
        WorkflowStatus.CLOSED,
    },
    WorkflowStatus.AWAIT_SHIPMENT: {WorkflowStatus.IN_TRANSIT, WorkflowStatus.CLOSED},
    WorkflowStatus.IN_TRANSIT: {WorkflowStatus.ARRIVED, WorkflowStatus.DISPUTE},
    WorkflowStatus.ARRIVED: {
        WorkflowStatus.INSPECTING,
        WorkflowStatus.REFUNDING,
        WorkflowStatus.DISPUTE,
    },
    WorkflowStatus.INSPECTING: {
        WorkflowStatus.REFUNDING,
        WorkflowStatus.REJECTED,
        WorkflowStatus.DISPUTE,
    },
    WorkflowStatus.DISPUTE: {
        WorkflowStatus.MANUAL_REVIEW,
        WorkflowStatus.REFUNDING,
        WorkflowStatus.REJECTED,
    },
    WorkflowStatus.REFUNDING: {WorkflowStatus.REFUNDED, WorkflowStatus.DISPUTE},
    WorkflowStatus.REFUNDED: {WorkflowStatus.CLOSED},
    WorkflowStatus.REJECTED: {WorkflowStatus.CLOSED},
    WorkflowStatus.CLOSED: set(),
}

# 能力位：规则能不能跑由数据决定，不拿默认值假装真实信号。
CAP_AMOUNTS, CAP_ORDER_STATUS, CAP_BUYER_RISK, CAP_EVIDENCE = (
    "amounts",
    "order_status",
    "buyer_risk",
    "evidence",
)
CAP_ACCOUNT_AGE, CAP_DEVICE, CAP_ADDRESS_DETAIL = "account_age", "device", "address_detail"
CAP_CATEGORY, CAP_COUPON_POLICY, CAP_OPENED = "category", "coupon_policy", "opened"
CAP_DELIVERY_TIME, CAP_HISTORY, CAP_PROMISE = "delivery_time", "history", "promise"


# ── 配置：唯一阈值来源 ───────────────────────────────────
@dataclass(frozen=True)
class Thresholds:
    stat_window_days: int = 90
    new_account_days: int = 7
    new_account_max_orders: int = 3
    high_freq_return_count: int = 4
    high_freq_return_count_severe: int = 6
    return_rate_min_orders: int = 5
    return_rate_high: float = 0.60
    high_value_amount: float = 800.0
    refund_only_abuse_count: int = 2
    missing_claim_repeat: int = 2
    non_resellable_requires_quality: bool = True
    auto_refund_max_amount: float = 5000.0
    freight_only_auto_max: float = 20.0
    virtual_goods_auto_max: float = 50.0
    buyer_refund_rate_watch: float = 0.30
    buyer_refund_rate_high: float = 0.50
    channel_max_retries: int = 3
    address_cluster_accounts: int = 3
    device_cluster_accounts: int = 3
    return_window_days: int = 15
    fast_return_hours: float = 2.0
    fast_return_min_amount: float = 300.0
    good_credit_score: int = 85
    good_credit_min_orders: int = 20


@dataclass(frozen=True)
class TierPolicy:
    a_min: int = 70
    b_min: int = 45
    c_min: int = 20
    auto_refund_max_a: float = 200.0
    auto_refund_max_b: float = 500.0
    c_tier_auto_max: float = 200.0
    low_cost_partial_max: float = 300.0
    partial_refund_ratio: float = 0.15


@dataclass(frozen=True)
class RunLimits:
    max_turns: int = 12
    max_retries: int = 3
    lock_ttl_seconds: int = 10
    checkpoint_retention_days: int = 30


@dataclass(frozen=True)
class AppConfig:
    thresholds: Thresholds = Thresholds()
    tiers: TierPolicy = TierPolicy()
    limits: RunLimits = RunLimits()


CONFIG = AppConfig()


# ── 数据契约 DTO ────────────────────────────────────────
class DatasetError(ValueError):
    """数据不满足契约时尽早失败，绝不把脏数据放进业务库。"""


@dataclass(frozen=True)
class FieldSpec:
    name: str
    dtype: str
    required: bool
    note: str = ""


@dataclass
class Record:
    """一条上游退款申请；金额单位分，时间东八区 naive。"""

    refund_id: str
    order_id: str
    user_id: str
    idempotency_key: str
    order_status: OrderStatus
    payment_no: str
    goods_fee: int
    freight_fee: int
    tax_fee: int
    discount_fee: int
    paid_fee: int
    refundable_fee: int
    refund_fee: int
    refund_type: RefundType
    refund_scope: RefundScope
    reason_code: str
    reason: ReturnReason
    reason_desc: str
    return_required: bool
    return_status: ReturnStatus
    apply_time: datetime
    delivered_at: datetime | None
    sla_deadline: datetime | None
    evidence: tuple[str, ...]
    platform_intervened: bool
    channel_error_code: str
    channel_error_message: str
    retry_count: int
    user_risk_level: str
    user_refund_rate_30d: float
    previous_refund_id: str
    scenario: str
    scenario_name: str
    expected_action: ActionCode
    after_sale_no: str = ""
    item_name: str = ""
    item_count: int = 1
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def paid(self) -> float:
        return yuan(self.paid_fee)

    @property
    def refundable(self) -> float:
        return yuan(self.refundable_fee)

    @property
    def requested(self) -> float:
        return yuan(self.refund_fee)

    @property
    def settled(self) -> float:
        return min(self.requested, self.refundable)

    @property
    def reason_label(self) -> str:
        return REASON_LABELS.get(self.reason.value, self.reason.value)


@dataclass
class Dataset:
    dataset_id: str
    schema_version: str
    amount_unit: str
    produced_at: datetime | None
    records: list[Record]
    integrity_issues: list[str] = field(default_factory=list)

    def by_refund_id(self, refund_id: str) -> Record | None:
        return next((r for r in self.records if r.refund_id == refund_id), None)


@dataclass
class Stats:
    """本地历史统计；新客场景基本为空。"""

    order_count: int = 0
    return_count: int = 0
    refund_only_count: int = 0
    missing_claim_count: int = 0

    @property
    def return_rate(self) -> float:
        return self.return_count / self.order_count if self.order_count else 0.0


@dataclass
class Signals:
    """风控引擎只读输入快照。"""

    rec: Record
    stats: Stats
    history_known: bool
    capabilities: frozenset[str]
    address_account_count: int = 1
    device_account_count: int = 1
    has_promise: bool = False
    promise_note: str = ""
    now: datetime = field(default_factory=now)

    @property
    def requested_amount(self) -> float:
        return self.rec.requested

    @property
    def refundable_amount(self) -> float:
        return self.rec.refundable

    @property
    def hours_since_delivery(self) -> float | None:
        if not self.rec.delivered_at:
            return None
        return (self.now - self.rec.delivered_at).total_seconds() / 3600

    @property
    def days_since_delivery(self) -> float | None:
        h = self.hours_since_delivery
        return h / 24 if h is not None else None

    def supports(self, required: frozenset[str]) -> bool:
        return required <= self.capabilities


@dataclass(frozen=True)
class RuleHit:
    code: str
    title: str
    weight: int
    detail: str
    hard_block: bool = False
    requires_evidence: bool = False
    requires_manual: bool = False
    risk_hold: bool = False
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class RuleSpec:
    """单条风控规则的可执行描述。"""

    code: str
    fn: Callable[[Signals, Thresholds], RuleHit | None]
    requires: frozenset[str]

    def __call__(self, s: Signals, cfg: Thresholds) -> RuleHit | None:
        return self.fn(s, cfg)


@dataclass
class Verdict:
    trust_score: int
    tier: RiskTier
    hits: list[RuleHit]
    skipped_rules: list[str]
    plan: RefundPlan
    approved_amount: float
    requires_manual: bool
    requires_evidence: bool
    risk_hold: bool
    hard_block: bool
    user_message: str
    rationale: list[str]

    @property
    def hit_codes(self) -> list[str]:
        return [h.code for h in self.hits]


@dataclass(frozen=True)
class CheckResult:
    code: CheckCode
    passed: bool
    message: str


@dataclass(frozen=True)
class Disposition:
    action: ActionCode
    reason: str
    note: str = ""
    queue: str = ""
    approved_cents: int = 0


@dataclass
class StepOutcome:
    record: Record
    checks: list[CheckResult]
    verdict: Verdict
    disposition: Disposition


@dataclass(frozen=True)
class ExecutionResult:
    """工作流节点执行结果：用于流程追踪与终端验收。

    transitions 是按发生顺序记录的状态名，ledger_amount 是实际入台账金额。
    """

    node: str
    transitions: list[str] = field(default_factory=list)
    ledger_amount: float = 0.0
    queue: str = ""
    note: str = ""


@dataclass
class CaseView:
    """对外视图：只读展示，不暴露规则编号与权重。"""

    return_id: str | None
    status: str
    status_label: str
    action_code: str
    action_label: str
    amount: float
    reply: str
    reason: str = ""
    reason_label: str = ""
    queue: str = ""
    queue_label: str = ""
    refund_id: str = ""
    after_sale_no: str = ""
    risk_tier: str = ""
    trust_score: int = 100
    rule_hits: list[str] = field(default_factory=list)
    pending: dict[str, Any] | None = None
    handoff: dict[str, Any] = field(default_factory=dict)
    actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── 标签函数 ────────────────────────────────────────────
def reason_label(value: Any) -> str:
    return REASON_LABELS.get(str(value), str(value or ""))


def action_label(value: Any) -> str:
    return ACTION_LABELS.get(str(value), str(value or ""))


def status_label(value: Any) -> str:
    return STATUS_LABELS.get(str(value), str(value or ""))


def plan_label(value: Any) -> str:
    return PLAN_LABELS.get(str(value), str(value or ""))


__all__ = [n for n in globals() if not n.startswith("_")]
