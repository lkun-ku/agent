"""Phase 1：单例生命周期、时钟注入、BM25 失效与超时配置回归。"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from app.config import get_settings
from app.core.rag.pipeline import RAGPipeline
from app.core.tools.refund.service import RefundService
from app.domain.refund.activities.ingest import load_dataset
from app.domain.refund.activities.risk import assess
from app.domain.refund.common import SystemClock
from app.infrastructure.database.session import init_engine
from app.infrastructure.llm.factory import get_model_router, reset_model_router
from app.models.enums import RetrievalMode
from app.models.schemas import RetrievalResult

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "refund"


class FakeClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value


def test_model_router_is_process_level_singleton() -> None:
    reset_model_router()
    try:
        first = get_model_router()
        second = get_model_router()
        assert first is second

        model_id = first._configs[0].model_id
        breaker = first._breakers[model_id]
        breaker._record_failure()
        third = get_model_router()
        assert third is first
        assert third._breakers[model_id] is breaker
        assert breaker._failure_count == 1
    finally:
        reset_model_router()


def test_refund_service_uses_injected_clock() -> None:
    from app.domain.refund.contracts import Dataset

    class SeedOnlyStore:
        def __init__(self) -> None:
            self.datasets: list[Any] = []

        def seed(self, dataset: Dataset) -> None:
            self.datasets.append(dataset)

    clock = FakeClock(datetime(2026, 11, 13, 12, 0, 0))
    store = SeedOnlyStore()
    service = RefundService(store, seed=False, clock=clock)  # type: ignore[arg-type]

    record = load_dataset(
        json_path=DATA / "refund_test_dataset_cn.json",
        csv_path=DATA / "refund_test_dataset_cn.csv",
    ).records[0]
    service.register(record)

    assert service.dataset.produced_at == clock.now()
    assert store.datasets[-1].produced_at == clock.now()


def test_risk_assess_uses_clock_not_global_state() -> None:
    record = load_dataset(
        json_path=DATA / "refund_test_dataset_cn.json",
        csv_path=DATA / "refund_test_dataset_cn.csv",
    ).records[0]

    verdict = assess(record, clock=FakeClock(datetime(2026, 11, 13)))
    assert verdict.rationale


class _FakeStore:
    async def search(
        self,
        query: str,
        top_k: int = 4,
        max_distance: float | None = None,
    ) -> list[RetrievalResult]:
        return []


class _FakeGenerator:
    pass


async def _keyword_documents() -> dict[str, str]:
    return {"doc": "退款政策：签收后七天内可申请退款"}


def _hybrid_pipeline() -> RAGPipeline:
    return RAGPipeline(
        _FakeStore(),
        _FakeGenerator(),
        retrieval_mode=RetrievalMode.HYBRID,
        keyword_provider=_keyword_documents,
    )


@pytest.mark.asyncio
async def test_bm25_index_can_be_invalidated() -> None:
    pipeline = _hybrid_pipeline()

    await pipeline._keyword_search("退款政策", top_k=3)
    assert pipeline._keyword_loaded

    pipeline.invalidate_keyword_index()
    assert not pipeline._keyword_loaded
    assert not pipeline._keyword_text


def test_postgres_engine_uses_configured_timeouts_and_pool() -> None:
    settings = get_settings()
    engine = init_engine(
        settings.database_url,
        connect_timeout=2.0,
        command_timeout=15.0,
        pool_size=3,
        max_overflow=4,
    )
    try:
        assert engine.pool.size() == 3
        assert engine.pool._max_overflow == 4
    finally:
        asyncio.run(engine.dispose())


@pytest.mark.asyncio
async def test_knowledge_sync_advisory_lock_helpers_skip_non_postgres() -> None:
    from app.core.rag.ingest import (
        _acquire_knowledge_sync_lock,
        _release_knowledge_sync_lock,
    )

    class FakeDialect:
        name = "sqlite"

    class FakeBind:
        dialect = FakeDialect()

    class FakeSession:
        bind = FakeBind()

    session = FakeSession()
    assert await _acquire_knowledge_sync_lock(session) is False
    await _release_knowledge_sync_lock(session)


def test_system_clock_returns_normalized_local_time() -> None:
    value = SystemClock().now()
    assert value.tzinfo is None
