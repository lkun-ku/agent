"""三态熔断器：保护下游服务免受连续失败冲击。"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import Any, Protocol, TypeVar

from loguru import logger

T = TypeVar("T")


class StateStore(Protocol):
    """熔断状态的共享存储（跨副本 best-effort）。"""

    async def load(self, name: str) -> dict[str, Any] | None:
        """读取某个 breaker 的共享状态；不存在时返回 None。"""
        ...

    async def save(self, name: str, state: dict[str, Any]) -> None:
        """写入某个 breaker 的共享状态。"""
        ...


class CircuitState(StrEnum):
    """熔断器状态：关闭（正常）、打开（拒绝）、半开（试探）。"""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """三态熔断器：Closed → Open → Half-Open。

    - Closed：正常放行，累计失败次数；
    - Open：快速失败，等待恢复超时后进入 Half-Open；
    - Half-Open：允许有限次试探调用，成功则关闭，失败则重新打开。
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max: int = 3,
        name: str = "default",
        state_store: StateStore | None = None,
    ) -> None:
        self.failure_threshold = max(1, failure_threshold)
        self.recovery_timeout = max(0.1, recovery_timeout)
        self.half_open_max = max(1, half_open_max)
        self.name = name
        self._state_store = state_store

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float | None = None
        self._last_failure_epoch: float = 0.0
        self._half_open_attempts = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """当前熔断状态（只读）。"""
        return self._state

    def snapshot(self) -> dict[str, Any]:
        """只读状态快照，供健康检查/运维端点使用。"""
        retry_in = 0.0
        if self._state is CircuitState.OPEN and self._last_failure_time is not None:
            retry_in = max(
                0.0,
                self.recovery_timeout - (time.monotonic() - self._last_failure_time),
            )
        return {
            "name": self.name,
            "state": self._state.value,
            "failures": self._failure_count,
            "threshold": self.failure_threshold,
            "retry_in": round(retry_in, 3),
        }

    async def _sync_from_store(self) -> None:
        """读前同步共享状态；存储不可用时保留本地状态。"""
        if self._state_store is None:
            return
        try:
            data = await self._state_store.load(self.name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("熔断状态读取失败，使用本地状态: {}", exc)
            return
        if not data:
            return

        async with self._lock:
            try:
                self._state = CircuitState(str(data.get("state", "closed")))
            except ValueError:
                self._state = CircuitState.CLOSED
            self._failure_count = max(0, int(data.get("failures", 0)))
            self._half_open_attempts = max(0, int(data.get("half_open_attempts", 0)))
            epoch = float(data.get("last_failure", 0.0) or 0.0)
            self._last_failure_epoch = epoch
            if epoch > 0:
                age = max(0.0, time.time() - epoch)
                self._last_failure_time = time.monotonic() - age
            else:
                self._last_failure_time = None

    async def refresh(self) -> None:
        """主动同步共享状态（供健康检查使用）。"""
        await self._sync_from_store()

    async def _persist_state(self) -> None:
        """状态变化后写回共享存储；失败仅告警。"""
        if self._state_store is None:
            return
        state = {
            "state": self._state.value,
            "failures": self._failure_count,
            "last_failure": self._last_failure_epoch,
            "half_open_attempts": self._half_open_attempts,
        }
        try:
            await self._state_store.save(self.name, state)
        except Exception as exc:  # noqa: BLE001
            logger.warning("熔断状态写入失败，仅保留本地状态: {}", exc)

    def _should_trip(self) -> bool:
        """是否应因失败次数达到阈值而跳闸（打开）。"""
        return self._failure_count >= self.failure_threshold

    def _should_attempt_reset(self) -> bool:
        """Open 状态下是否已过恢复窗口，可进入 Half-Open 试探。"""
        if self._last_failure_time is None:
            return True
        return (time.monotonic() - self._last_failure_time) >= self.recovery_timeout

    def _record_success(self) -> None:
        """记录成功：关闭熔断并清零失败计数。"""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_attempts = 0
        self._last_failure_time = None
        self._last_failure_epoch = 0.0

    def _record_failure(self) -> None:
        """记录失败：更新计数与时间戳，必要时打开熔断。"""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        self._last_failure_epoch = time.time()
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            self._half_open_attempts = 0
            logger.warning(
                "熔断器 [{}] Half-Open 试探失败，重新打开 circuit",
                self.name,
            )
        elif self._should_trip():
            self._state = CircuitState.OPEN
            logger.error(
                "熔断器 [{}] 已达失败阈值 {}，状态切换为 OPEN",
                self.name,
                self.failure_threshold,
            )

    async def call(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """通过熔断器异步调用函数。"""
        await self._sync_from_store()

        async with self._lock:
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_attempts = 0
                    logger.info("熔断器 [{}] 进入 Half-Open 试探", self.name)
                else:
                    raise RuntimeError(
                        f"熔断器 [{self.name}] 处于 OPEN 状态，拒绝调用"
                    )

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_attempts >= self.half_open_max:
                    raise RuntimeError(
                        f"熔断器 [{self.name}] Half-Open 试探次数已达上限"
                    )
                self._half_open_attempts += 1

        try:
            result = await func(*args, **kwargs)
        except Exception as exc:
            async with self._lock:
                self._record_failure()
            await self._persist_state()
            logger.exception("熔断器 [{}] 包裹调用失败: {}", self.name, exc)
            raise

        async with self._lock:
            self._record_success()
        await self._persist_state()

        return result


class RedisStateStore:
    """跨副本共享熔断状态（best-effort，非原子）。"""

    def __init__(self, url: str, *, prefix: str = "breaker:", ttl: int = 300) -> None:
        import redis.asyncio as aioredis

        self._client = aioredis.from_url(url, decode_responses=True)
        self._prefix = prefix
        self._ttl = max(30, ttl)

    async def load(self, name: str) -> dict[str, Any] | None:
        """从 Redis 读取状态；键不存在或内容损坏时返回 None。"""
        raw = await self._client.get(self._prefix + name)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    async def save(self, name: str, state: dict[str, Any]) -> None:
        """带 TTL 写回 Redis，避免长期残留失效状态。"""
        await self._client.setex(
            self._prefix + name,
            self._ttl,
            json.dumps(state),
        )
