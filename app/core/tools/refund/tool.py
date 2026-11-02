"""退款工具：Agent 识别退款意图后直接调用的唯一入口。"""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from loguru import logger

from app.config import get_settings
from app.core.tools.base import BaseTool, ToolParameter
from app.core.tools.refund.agent_service import AgentService
from app.core.tools.refund.schemas import AgentRequest
from app.core.tools.refund.service import RefundService
from app.core.tools.refund.store import PostgresRefundStore
from app.core.tools.schemas import RefundToolResult, ToolHandoff
from app.infrastructure.observability.metrics import (
    ACTIVE_TOOL_INVOCATIONS,
    TOOL_DURATION,
)


class RefundTool(BaseTool):
    """把退款工作流暴露为 Agent 工具，不单独提供 HTTP 服务。"""

    def __init__(
        self,
        service: AgentService | None = None,
        service_factory: Callable[[], AgentService] | None = None,
    ) -> None:
        super().__init__()
        self.name = "refund"
        self.description = (
            "受理退款/退货/仅退款申请，校验订单并给出退款结论、金额和后续动作。"
        )
        self.parameters = [
            ToolParameter(
                name="order_id",
                type="string",
                description="订单号；用户已提供时必须传入",
                required=False,
            ),
            ToolParameter(
                name="refund_id",
                type="string",
                description="已有退款单号（可选）",
                required=False,
            ),
            ToolParameter(
                name="reason",
                type="string",
                description="用户退款原因或原话",
                required=False,
            ),
            ToolParameter(
                name="record",
                type="object",
                description="完整退款单快照（可选，字段契约见 domain/refund）",
                required=False,
            ),
        ]
        self._service = service
        self._service_factory = service_factory or self._build_service
        self._lock = threading.Lock()

    def _build_service(self) -> AgentService:
        settings = get_settings()
        store = PostgresRefundStore(settings.database_url)
        refund = RefundService(
            store,
            data_dir=settings.refund_data_dir,
            seed=settings.refund_seed_dataset,
        )
        return AgentService(refund)

    def _get_service(self) -> AgentService:
        if self._service is None:
            with self._lock:
                if self._service is None:
                    self._service = self._service_factory()
        return self._service

    def get_service(self) -> AgentService:
        """返回进程级退款应用服务，供运营后台复用同一连接池。"""
        return self._get_service()

    async def execute(self, **kwargs: Any) -> RefundToolResult:
        raw_order = kwargs.get("order_id")
        raw_refund = kwargs.get("refund_id")
        record = kwargs.get("record")
        if raw_order is not None and not isinstance(raw_order, (str, int)):
            return self._invalid_argument("order_id 必须是字符串或整数")
        if raw_refund is not None and not isinstance(raw_refund, (str, int)):
            return self._invalid_argument("refund_id 必须是字符串或整数")
        if record is not None and not isinstance(record, dict):
            return self._invalid_argument("record 必须是对象")

        order_id = str(raw_order or "").strip()
        refund_id = str(raw_refund or "").strip()
        if not (order_id or refund_id or record):
            return RefundToolResult(
                status="need_info",
                action="NEED_ORDER",
                reply="请提供订单号；我查到订单后会继续判断是否符合退款条件。",
            )

        request = AgentRequest(
            request_id=str(kwargs.get("request_id") or uuid4().hex),
            order_id=order_id,
            refund_id=refund_id,
            record=record if isinstance(record, dict) else None,
        )
        started_at = time.perf_counter()
        ACTIVE_TOOL_INVOCATIONS.inc()
        try:
            response = await asyncio.to_thread(self._get_service().submit, request)
            return RefundToolResult.model_validate(response.to_dict())
        except KeyError as exc:
            logger.info("退款工具未找到单据: {}", exc)
            return self._not_found()
        except Exception as exc:  # noqa: BLE001
            logger.exception("退款工具执行失败: {}", exc)
            return self._service_error()
        finally:
            ACTIVE_TOOL_INVOCATIONS.dec()
            TOOL_DURATION.labels(tool=self.name).observe(
                time.perf_counter() - started_at
            )

    @staticmethod
    def _not_found() -> RefundToolResult:
        return RefundToolResult(
            status="need_info",
            action="NOT_FOUND",
            reply="没有找到对应订单或退款单，请核对订单号后重试。",
        )

    @staticmethod
    def _service_error() -> RefundToolResult:
        return RefundToolResult(
            status="error",
            action="ERROR",
            reply="退款处理暂时不可用，请稍后重试或转人工。",
            handoff=ToolHandoff(to_human=True, queue="refund_error"),
        )

    @staticmethod
    def _invalid_argument(message: str) -> RefundToolResult:
        return RefundToolResult(
            status="error",
            action="INVALID_ARGUMENT",
            reply=f"退款参数无效：{message}。",
        )

    def close(self) -> None:
        if self._service is not None:
            self._service.refund.close()
            self._service = None


__all__ = ["RefundTool"]
