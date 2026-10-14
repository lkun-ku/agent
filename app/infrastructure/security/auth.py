"""API 鉴权依赖；内部服务可配置关闭，生产必须开启。"""

from __future__ import annotations

import secrets
from typing import Any

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from loguru import logger

from app.config import get_settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(
    settings: Any = Depends(get_settings),
    api_key: str | None = Security(_api_key_header),
) -> None:
    """校验内部 API Key；未启用或未配置时放行，便于本地开发。"""
    if not settings.api_auth_enabled:
        return
    if not settings.api_key:
        logger.warning("API 鉴权已启用但未配置 API_KEY，请求将被拒绝")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API 鉴权已启用但服务未配置 API Key",
        )
    if not api_key or not secrets.compare_digest(api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )


__all__ = ["require_api_key"]
