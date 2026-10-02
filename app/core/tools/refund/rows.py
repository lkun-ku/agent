"""退款存储的数据库行与视图类型。

TypedDict 只描述存储适配器返回的稳定字段；数据库可能包含额外列，
因此全部字段采用 ``total=False``。
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal, TypedDict


class ReturnOrderRow(TypedDict, total=False):
    """``return_orders`` 表的稳定读取视图。"""

    return_id: str
    refund_id: str
    order_id: str
    user_id: str
    session_id: str
    status: str
    workflow_status: str
    reason: str
    reason_code: str
    plan: str
    requested_amount: Decimal | float | int
    approved_amount: Decimal | float | int | None
    refunded_amount: Decimal | float | int | None
    action_code: str | None
    queue: str | None
    trust_score: int | None
    risk_tier: str | None
    risk_json: str | None
    evidence_json: str | None
    reply: str | None
    handoff_json: str | None
    return_required: bool | int | None
    return_status: str | None


class PendingTask(TypedDict):
    """待处理人工任务的稳定视图。"""

    kind: Literal["external", "evidence", "manual_review"]
    queue: str
    payload: dict[str, Any]


class OpenTask(TypedDict):
    """人工队列条目的稳定视图。"""

    return_id: str
    queue: str
    queue_label: str
    reason: str
    reason_label: str
    requested_amount: Decimal | float | int
    action: str | None


__all__ = ["OpenTask", "PendingTask", "ReturnOrderRow"]
