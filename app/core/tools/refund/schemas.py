"""客服系统对外契约：请求/响应只暴露业务字段，不暴露内部规则码与权重。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4


@dataclass
class AgentRequest:
    """客服系统发起退款/查询的入参：三选一（record / refund_id / order_id）。"""

    request_id: str = ""
    refund_id: str = ""
    order_id: str = ""
    record: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        for name in ("request_id", "refund_id", "order_id"):
            if not isinstance(getattr(self, name), str):
                raise TypeError(f"{name} 必须是字符串")
        if self.record is not None and not isinstance(self.record, dict):
            raise TypeError("record 必须是对象")

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> AgentRequest:
        return cls(
            request_id=str(payload.get("request_id") or uuid4().hex),
            refund_id=str(payload.get("refund_id") or ""),
            order_id=str(payload.get("order_id") or ""),
            record=payload.get("record") or None,
        )

    def validate(self) -> None:
        if not (self.record or self.refund_id or self.order_id):
            raise ValueError("必须提供 record、refund_id、order_id 之一")


@dataclass
class AgentResponse:
    """客服系统消费的稳定响应；action 是业务动作码，不返回规则命中与信任分。"""

    request_id: str
    case_id: str
    refund_id: str
    order_id: str
    # auto_completed / completed / rejected / waiting_return / need_human
    # need_evidence / disputed / processing
    status: str
    action: str
    action_label: str
    amount: float
    reply: str
    reason: str = ""
    reason_label: str = ""
    queue: str = ""
    queue_label: str = ""
    pending: dict[str, Any] | None = None
    handoff: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValueError("amount 不能为负数")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TaskView:
    case_id: str
    queue: str
    queue_label: str
    reason: str
    reason_label: str
    amount: float
    action: str

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValueError("amount 不能为负数")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = ["AgentRequest", "AgentResponse", "TaskView"]
