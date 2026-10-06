"""ModelRouter 进程级工厂：复用 OpenAI client 与熔断器状态。"""

from __future__ import annotations

import threading

from loguru import logger

from app.config import get_settings
from app.infrastructure.llm.model_router import ModelConfig, ModelRouter

_router: ModelRouter | None = None
_lock = threading.Lock()


def build_model_router() -> ModelRouter:
    """按配置新建 ModelRouter；供工厂和特殊场景显式使用。"""
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("未配置 OPENAI_API_KEY，无法构建 ModelRouter")
    return ModelRouter(
        [
            ModelConfig(
                model_id=settings.openai_model,
                api_key=settings.openai_api_key,
                base_url=settings.openai_api_base or None,
                priority=0,
                weight=1.0,
                thinking=settings.openai_thinking,
            )
        ],
        max_retries=settings.llm_max_retries,
        retry_base_delay=settings.llm_retry_base_delay,
        retry_max_delay=settings.llm_retry_max_delay,
    )


def get_model_router() -> ModelRouter:
    """获取进程级 ModelRouter；熔断器状态在请求间保持。"""
    global _router
    if _router is None:
        with _lock:
            if _router is None:
                _router = build_model_router()
                logger.info("ModelRouter 已初始化（进程级复用）")
    return _router


def reset_model_router() -> None:
    """重置进程级 ModelRouter；供配置变更和测试使用。"""
    global _router
    with _lock:
        _router = None
        logger.info("ModelRouter 已重置")


__all__ = ["build_model_router", "get_model_router", "reset_model_router"]
