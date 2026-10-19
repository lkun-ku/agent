"""多模型路由器：优先级调度、加权选择与自动降级。"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Any

from loguru import logger
from openai import APIConnectionError, APIError, AsyncOpenAI, RateLimitError
from pydantic import BaseModel

from app.infrastructure.llm.circuit_breaker import CircuitBreaker


class LLMResponse(BaseModel):
    """统一 LLM 响应结构。"""

    content: str = ""
    model_id: str = ""
    usage: dict[str, Any] | None = None


def build_thinking_extra(enabled: bool) -> dict[str, Any]:
    """构造 DeepSeek 思考模式开关（顶层参数，需经 ``extra_body`` 透传）。

    该模式默认开启，开启后 ``temperature`` 不生效且小 ``max_tokens`` 会被思维链
    占满导致 ``content`` 为空，因此需要显式下发关闭。
    """
    return {"thinking": {"type": "enabled" if enabled else "disabled"}}


@dataclass
class ModelConfig:
    """单路模型配置。"""

    model_id: str
    api_key: str
    base_url: str | None = None
    priority: int = 0
    weight: float = 1.0
    thinking: bool | None = None


class ModelRouter:
    """多模型路由器：支持优先级调度、负载均衡（同优先级加权随机）、自动降级。"""

    def __init__(
        self,
        model_configs: list[ModelConfig],
        *,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        max_retries: int = 1,
        retry_base_delay: float = 0.5,
        retry_max_delay: float = 5.0,
    ) -> None:
        if not model_configs:
            raise ValueError("model_configs 不能为空")
        self._max_retries = max(0, min(max_retries, 3))
        self._retry_base_delay = max(0.0, retry_base_delay)
        self._retry_max_delay = max(self._retry_base_delay, retry_max_delay)

        self._configs = sorted(model_configs, key=lambda c: c.priority)
        self._configs_by_id: dict[str, ModelConfig] = {c.model_id: c for c in self._configs}
        self._breakers: dict[str, CircuitBreaker] = {}
        for cfg in self._configs:
            self._breakers[cfg.model_id] = CircuitBreaker(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                name=f"llm:{cfg.model_id}",
            )
        self._clients: dict[str, AsyncOpenAI] = {}
        for cfg in self._configs:
            kwargs: dict[str, Any] = {"api_key": cfg.api_key}
            if cfg.base_url:
                kwargs["base_url"] = cfg.base_url
            self._clients[cfg.model_id] = AsyncOpenAI(**kwargs)

    def _select_candidates(
        self,
        model_preference: str | None,
    ) -> list[ModelConfig]:
        """按优先级分组，在同优先级内按权重随机排序，形成候选列表。"""
        if model_preference:
            exact = [c for c in self._configs if c.model_id == model_preference]
            if exact:
                return exact

        by_prio: dict[int, list[ModelConfig]] = {}
        for cfg in self._configs:
            by_prio.setdefault(cfg.priority, []).append(cfg)

        ordered: list[ModelConfig] = []
        for prio in sorted(by_prio.keys()):
            group = by_prio[prio]
            # 同优先级内按权重做随机排序（权重越大越容易被排到前面）
            scored = [
                (cfg, random.random() ** (1.0 / max(cfg.weight, 0.01)))
                for cfg in group
            ]
            scored.sort(key=lambda x: -x[1])
            ordered.extend(cfg for cfg, _ in scored)
        return ordered or list(self._configs)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model_preference: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """智能路由到合适模型；失败时按候选顺序自动降级。"""
        candidates = self._select_candidates(model_preference)
        last_error: Exception | None = None

        retryable = (TimeoutError, APIConnectionError, RateLimitError)
        for cfg in candidates:
            breaker = self._breakers[cfg.model_id]
            for attempt in range(self._max_retries + 1):
                try:
                    return await breaker.call(
                        self._try_model,
                        cfg.model_id,
                        messages,
                        **kwargs,
                    )
                except RuntimeError as exc:
                    # 熔断打开或调用被拒绝：不再原地重试，直接换候选。
                    last_error = exc
                    logger.warning("模型 [{}] 被熔断跳过: {}", cfg.model_id, exc)
                    break
                except retryable as exc:
                    last_error = exc
                    if attempt >= self._max_retries:
                        logger.warning(
                            "模型 [{}] 重试耗尽，尝试降级: {}",
                            cfg.model_id,
                            exc,
                        )
                        break
                    delay = min(
                        self._retry_base_delay * (2**attempt),
                        self._retry_max_delay,
                    )
                    logger.warning(
                        "模型 [{}] 瞬时失败，第 {}/{} 次重试，等待 {:.2f}s: {}",
                        cfg.model_id,
                        attempt + 1,
                        self._max_retries,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)
                except APIError as exc:
                    # 4xx 等非瞬时错误不重试，避免无效放大。
                    last_error = exc
                    logger.warning("模型 [{}] 非瞬时错误，跳过: {}", cfg.model_id, exc)
                    break
                except Exception as exc:
                    last_error = exc
                    logger.exception("模型 [{}] 未预期错误: {}", cfg.model_id, exc)
                    break

        msg = "所有候选模型均不可用"
        if last_error:
            raise RuntimeError(msg) from last_error
        raise RuntimeError(msg)

    async def _try_model(
        self,
        model_id: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> LLMResponse:
        """尝试调用指定模型（经熔断器包装，不在此处重复熔断逻辑）。"""
        client = self._clients[model_id]
        temperature = kwargs.pop("temperature", 0.7)
        max_tokens = kwargs.pop("max_tokens", None)
        extra_body: dict[str, Any] = dict(kwargs.pop("extra_body", None) or {})

        cfg = self._configs_by_id.get(model_id)
        if cfg is not None and cfg.thinking is not None:
            extra_body.update(build_thinking_extra(cfg.thinking))

        params: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        if extra_body:
            params["extra_body"] = extra_body
        params.update(kwargs)

        try:
            resp = await client.chat.completions.create(**params)
        except Exception:
            logger.exception("OpenAI 兼容接口调用失败 model_id={}", model_id)
            raise

        choice = resp.choices[0] if resp.choices else None
        content = (choice.message.content or "").strip() if choice else ""
        if not content:
            raise ValueError("模型返回空内容")
        usage = None
        if resp.usage:
            usage = {
                "prompt_tokens": resp.usage.prompt_tokens,
                "completion_tokens": resp.usage.completion_tokens,
                "total_tokens": resp.usage.total_tokens,
            }

        return LLMResponse(
            content=content,
            model_id=model_id,
            usage=usage,
        )
