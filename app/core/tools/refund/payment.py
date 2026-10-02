"""支付网关适配器：默认模拟，生产替换为 Stripe/Adyen/支付宝等。"""

from __future__ import annotations

import os
from decimal import Decimal


class SimulatedPaymentGateway:
    """只验证调用语义，不产生真实资金流水。

    生产必须注入真实 PaymentGateway 实现；该实现的命名带 Simulated，
    防止被误认为已接入支付渠道。
    """

    def refund(self, return_id: str, amount: Decimal | float) -> None:
        if amount <= 0:
            raise ValueError("退款金额必须大于 0")
        if os.getenv("REFUND_FAIL") == "1":
            raise RuntimeError("模拟渠道退款失败")
