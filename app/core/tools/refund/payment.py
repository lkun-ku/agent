"""支付网关适配器：本地模拟与通用 HTTP 真实网关。"""

from __future__ import annotations

import os
from decimal import Decimal
from typing import Any

import httpx
from loguru import logger

from app.config import get_settings


class SimulatedPaymentGateway:
    """只验证调用语义，不产生真实资金流水。"""

    def refund(self, return_id: str, amount: Decimal | float) -> None:
        if amount <= 0:
            raise ValueError("退款金额必须大于 0")
        if os.getenv("REFUND_FAIL") == "1":
            raise RuntimeError("模拟渠道退款失败")


class HttpPaymentGateway:
    """通用 HTTP 退款网关适配器。

    请求契约：

    ```json
    POST <payment_gateway_url>
    Authorization: Bearer <token>
    {"return_id": "...", "amount": 12.34}
    ```
    """

    def __init__(self, settings: Any | None = None) -> None:
        self._settings = settings or get_settings()
        if not self._settings.payment_gateway_url:
            raise RuntimeError("HTTP 网关模式必须配置 PAYMENT_GATEWAY_URL")
        if not self._settings.payment_gateway_token:
            raise RuntimeError("HTTP 网关模式必须配置 PAYMENT_GATEWAY_TOKEN")

    def refund(self, return_id: str, amount: Decimal | float) -> None:
        amount_decimal = Decimal(str(amount))
        if amount_decimal <= 0:
            raise ValueError("退款金额必须大于 0")
        cents = amount_decimal * 100
        if cents != cents.to_integral_value():
            raise ValueError("退款金额存在小于分的精度")
        try:
            response = httpx.post(
                str(self._settings.payment_gateway_url),
                headers={
                    "Authorization": f"Bearer {self._settings.payment_gateway_token}",
                    "Content-Type": "application/json",
                },
                json={"return_id": return_id, "amount": float(amount_decimal)},
                timeout=self._settings.payment_gateway_timeout,
            )
            response.raise_for_status()
        except Exception as exc:
            logger.error(
                "HTTP 支付网关退款失败 return_id={} amount={}: {}",
                return_id,
                amount_decimal,
                exc,
            )
            raise RuntimeError("支付网关退款失败") from exc


def create_payment_gateway(settings: Any | None = None) -> Any:
    """按配置创建支付网关；生产必须切换为真实实现。"""
    resolved = settings or get_settings()
    if resolved.payment_gateway_mode == "http":
        return HttpPaymentGateway(resolved)
    if resolved.payment_gateway_mode == "simulated":
        return SimulatedPaymentGateway()
    raise ValueError(
        f"未知支付网关模式 {resolved.payment_gateway_mode!r}；仅支持 simulated/http"
    )


__all__ = ["HttpPaymentGateway", "SimulatedPaymentGateway", "create_payment_gateway"]
