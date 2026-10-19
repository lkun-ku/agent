"""健康检查：进程存活、依赖矩阵、指标与版本。"""

from __future__ import annotations

import asyncio
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from loguru import logger
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.infrastructure.database.session import get_async_session
from app.infrastructure.health.probes import probe_milvus, probe_redis
from app.infrastructure.observability.metrics import DEPENDENCY_ERRORS

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """轻量存活探针（不访问外部依赖）。"""
    return {"status": "ok"}


@router.get("/health/ready")
async def health_ready(
    session: AsyncSession = Depends(get_async_session),
) -> JSONResponse:
    """就绪探针：数据库是关键依赖，Redis/Milvus 为可选依赖。"""
    settings = get_settings()
    try:
        await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:
        logger.warning("数据库就绪检查失败: {}", exc)
        DEPENDENCY_ERRORS.labels(component="postgres", operation="ready").inc()
        db_ok = False

    redis_status = "skipped"
    if settings.rag_cache_enabled:
        redis_status = await _check_dependency(
            "redis",
            "ready",
            _check_redis(),
        )

    milvus_status = "skipped"
    if settings.rag_enabled:
        milvus_status = await _check_dependency(
            "milvus",
            "ready",
            _check_milvus(),
        )

    optional_ok = redis_status in {"up", "skipped"} and milvus_status in {
        "up",
        "skipped",
    }
    body: dict[str, Any] = {
        "status": "ready" if db_ok and optional_ok else "degraded",
        "database": "up" if db_ok else "down",
        "redis": redis_status,
        "milvus": milvus_status,
        "app_env": settings.app_env,
    }
    return JSONResponse(content=body, status_code=200 if db_ok else 503)


@router.get("/metrics")
async def metrics() -> Response:
    """Prometheus 抓取端点。"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/version")
async def version_info() -> dict[str, str]:
    """运行版本信息，便于发布核对与回滚。"""
    try:
        app_version = version("enterprise-ai-agent")
    except PackageNotFoundError:  # pragma: no cover - 开发环境可能未安装包
        app_version = "unknown"
    settings = get_settings()
    return {
        "app_name": settings.app_name,
        "app_version": app_version,
        "app_env": settings.app_env,
    }


async def _check_dependency(
    component: str,
    operation: str,
    coro: Any,
) -> str:
    timeout = 3.0
    try:
        await asyncio.wait_for(coro, timeout=timeout)
    except Exception as exc:
        logger.warning("{} 就绪检查失败: {}", component, exc)
        DEPENDENCY_ERRORS.labels(component=component, operation=operation).inc()
        return "down"
    return "up"


async def _check_redis() -> None:
    await probe_redis(get_settings())


async def _check_milvus() -> None:
    await probe_milvus(get_settings())
