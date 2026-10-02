"""工具内部适配：把退款编排结果映射为 Agent 可消费的稳定结构。"""

from __future__ import annotations

from app.core.tools.refund.nodes import AUTO_ACTIONS, REJECT_ACTIONS
from app.core.tools.refund.schemas import AgentRequest, AgentResponse, TaskView
from app.core.tools.refund.service import RefundService
from app.domain.refund.activities.ingest import parse_record
from app.domain.refund.contracts import ActionCode, CaseView, Record


class AgentService:
    """退款工具的业务适配器；不依赖 HTTP、回调或独立服务。"""

    def __init__(self, refund: RefundService):
        self.refund = refund

    def submit(self, request: AgentRequest) -> AgentResponse:
        request.validate()
        rec = self._resolve(request)
        view = self.refund.submit_record(rec)
        return self._response(request.request_id, view)

    def get(self, case_id: str) -> AgentResponse:
        return self._response("", self.refund.get_case(case_id))

    def tasks(self) -> list[TaskView]:
        return [
            TaskView(
                case_id=item["return_id"],
                queue=item["queue"],
                queue_label=item["queue_label"],
                reason=item["reason"],
                reason_label=item["reason_label"],
                amount=float(item["requested_amount"]),
                action=item["action"] or "",
            )
            for item in self.refund.list_review_queue()
        ]

    def resolve(
        self,
        case_id: str,
        action: str,
        *,
        reviewer: str = "cs_agent",
        note: str = "",
        amount: float | None = None,
    ) -> AgentResponse:
        view = self.refund.resume_review(
            case_id, action, reviewer=reviewer, note=note, amount=amount
        )
        return self._response("", view)

    def evidence(self, case_id: str, urls: list[str]) -> AgentResponse:
        view = self.refund.provide_evidence(case_id, urls)
        return self._response("", view)

    def _resolve(self, request: AgentRequest) -> Record:
        if request.record:
            rec = parse_record(request.record)
            self.refund.register(rec)
            return rec
        if request.refund_id:
            found = self.refund.records.get(request.refund_id)
            if found is None:
                raise KeyError(f"未找到退款单 {request.refund_id}")
            return found
        found = next(
            (
                record
                for record in self.refund.records.values()
                if record.order_id == request.order_id
            ),
            None,
        )
        if found is None:
            raise KeyError(f"未找到订单 {request.order_id}")
        return found

    def _response(self, request_id: str, view: CaseView) -> AgentResponse:
        code = view.action_code
        action = ActionCode(code)
        if view.pending:
            kind = view.pending.get("kind")
            status = (
                "need_evidence"
                if kind == "evidence"
                else "disputed"
                if kind == "external"
                else "need_human"
            )
        elif action in AUTO_ACTIONS:
            status = "auto_completed"
        elif view.status == "rejected" or action in REJECT_ACTIONS:
            status = "rejected"
        elif view.status in {"await_shipment", "in_transit", "arrived", "inspecting"}:
            status = "waiting_return"
        elif view.status in {"closed", "refunded"}:
            status = "completed"
        elif action is ActionCode.HOLD_UNTIL_RETURN_RECEIVED:
            status = "waiting_return"
        elif action is ActionCode.DISPUTE_EVIDENCE_FLOW:
            status = "disputed"
        else:
            status = "processing"
        handoff = {
            "to_human": bool(view.pending) or action is ActionCode.DISPUTE_EVIDENCE_FLOW,
            "queue": view.queue,
            "queue_label": view.queue_label,
        }
        row = self.refund.store.return_row(view.return_id) if view.return_id else {}
        return AgentResponse(
            request_id=request_id,
            case_id=view.return_id or "",
            refund_id=view.refund_id,
            order_id=(row or {}).get("order_id", ""),
            status=status,
            action=code,
            action_label=view.action_label,
            amount=view.amount,
            reply=view.reply,
            reason=view.reason,
            reason_label=view.reason_label,
            queue=view.queue,
            queue_label=view.queue_label,
            pending=view.pending,
            handoff=handoff,
        )


__all__ = ["AgentService"]
