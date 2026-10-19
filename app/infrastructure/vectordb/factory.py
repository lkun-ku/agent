"""Milvus 连接工厂：统一 host/port/timeout/凭据配置。"""

from __future__ import annotations

from typing import Any

from app.config import Settings
from app.infrastructure.vectordb.milvus_client import MilvusManager


def create_milvus_manager(
    settings: Settings,
    *,
    alias: str,
) -> MilvusManager:
    """按全局配置创建 MilvusManager；所有入口必须复用该函数。"""
    conn_kwargs: dict[str, Any] = {}
    if settings.milvus_user:
        conn_kwargs["user"] = settings.milvus_user
    if settings.milvus_password:
        conn_kwargs["password"] = settings.milvus_password
    return MilvusManager(
        host=settings.milvus_host,
        port=str(settings.milvus_port),
        alias=alias,
        timeout=settings.milvus_timeout,
        **conn_kwargs,
    )


__all__ = ["create_milvus_manager"]
