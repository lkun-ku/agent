"""Phase 4：生产化基线——鉴权、迁移、真实请求仓储与支付适配。"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException

from app.core.tools.refund.payment import (
    HttpPaymentGateway,
    create_payment_gateway,
)
from app.core.tools.refund.service import RefundService
from app.domain.refund.activities.ingest import load_dataset
from app.infrastructure.security.auth import require_api_key

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "refund"


class FakeRequest:
    def __init__(self, values: dict[str, Any]) -> None:
        self.values = values

    def __getattr__(self, name: str) -> Any:
        return self.values[name]


@pytest.mark.asyncio
async def test_api_key_dependency_accepts_matching_key() -> None:
    settings = FakeRequest(
        {"api_auth_enabled": True, "api_key": "secret-key"}
    )
    await require_api_key(settings=settings, api_key="secret-key")


@pytest.mark.asyncio
async def test_api_key_dependency_rejects_invalid_key() -> None:
    settings = FakeRequest({"api_auth_enabled": True, "api_key": "secret-key"})
    with pytest.raises(HTTPException) as exc:
        await require_api_key(settings=settings, api_key="bad")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_api_key_dependency_fails_closed_without_configured_key() -> None:
    settings = FakeRequest({"api_auth_enabled": True, "api_key": None})
    with pytest.raises(HTTPException) as exc:
        await require_api_key(settings=settings, api_key="anything")
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_api_key_dependency_is_disabled_for_local_development() -> None:
    settings = FakeRequest({"api_auth_enabled": False, "api_key": None})
    await require_api_key(settings=settings, api_key=None)


def test_payment_gateway_factory_supports_simulated_and_http() -> None:
    simulated = create_payment_gateway(
        FakeRequest({"payment_gateway_mode": "simulated"})
    )
    assert type(simulated).__name__ == "SimulatedPaymentGateway"

    http = create_payment_gateway(
        FakeRequest(
            {
                "payment_gateway_mode": "http",
                "payment_gateway_url": "https://gateway.example/refund",
                "payment_gateway_token": "token",
                "payment_gateway_timeout": 2.0,
            }
        )
    )
    assert type(http).__name__ == "HttpPaymentGateway"


def test_payment_gateway_factory_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError, match="未知支付网关模式"):
        create_payment_gateway(FakeRequest({"payment_gateway_mode": "crypto"}))


def test_http_payment_gateway_posts_exact_amount(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    class Response:
        def raise_for_status(self) -> None:
            return None

    def fake_post(*args: Any, **kwargs: Any) -> Response:
        calls.append(kwargs)
        return Response()

    monkeypatch.setattr("app.core.tools.refund.payment.httpx.post", fake_post)
    gateway = HttpPaymentGateway(
        FakeRequest(
            {
                "payment_gateway_url": "https://gateway.example/refund",
                "payment_gateway_token": "token",
                "payment_gateway_timeout": 2.0,
            }
        )
    )
    gateway.refund("R0001", Decimal("12.34"))

    assert calls[0]["json"] == {"return_id": "R0001", "amount": 12.34}
    assert calls[0]["headers"]["Authorization"] == "Bearer token"


def test_http_payment_gateway_wraps_transport_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_post(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("network down")

    monkeypatch.setattr("app.core.tools.refund.payment.httpx.post", fake_post)
    gateway = HttpPaymentGateway(
        FakeRequest(
            {
                "payment_gateway_url": "https://gateway.example/refund",
                "payment_gateway_token": "token",
                "payment_gateway_timeout": 2.0,
            }
        )
    )
    with pytest.raises(RuntimeError, match="支付网关退款失败"):
        gateway.refund("R0001", Decimal("1.00"))


def test_refund_record_can_be_restored_from_store(tmp_path: Path) -> None:
    from sqlite_store import Store

    dataset = load_dataset(
        json_path=DATA / "refund_test_dataset_cn.json",
        csv_path=DATA / "refund_test_dataset_cn.csv",
    )
    store = Store(tmp_path / "restore.db")
    service = RefundService(store, seed=False)
    try:
        store.seed(dataset)
        first = dataset.records[0]

        restored_refund = service.find_record(refund_id=first.refund_id)
        restored_order = service.find_record(order_id=first.order_id)

        assert restored_refund is not None
        assert restored_refund.refund_id == first.refund_id
        assert restored_refund.order_id == first.order_id
        assert restored_order is not None
        assert restored_order.refund_id == first.refund_id
        assert service.find_record(refund_id="missing") is None
    finally:
        store.close()


def test_alembic_public_baseline_is_current() -> None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()
    assert heads == ["0001_public_baseline"]


@pytest.mark.integration
def test_alembic_version_is_public_baseline() -> None:

    from app.config import get_settings

    dsn = get_settings().database_url.replace(
        "postgresql+asyncpg://", "postgresql://"
    )
    with __import__("psycopg2").connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version_num FROM alembic_version")
            row = cur.fetchone()
    assert row is not None
    assert row[0] == "0001_public_baseline"
