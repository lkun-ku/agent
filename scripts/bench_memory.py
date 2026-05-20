"""短期记忆基线：每次 add_message 的全量读取 + 全量 tokenize 成本。

用法：
    .\\.venv\\Scripts\\python.exe scripts\\bench_memory.py
    .\\.venv\\Scripts\\python.exe scripts\\bench_memory.py --turns 200 --chars 300

对比：
- current：现有实现，每条消息都 LRANGE 全量 + 对全部历史 encode，之后才判断是否超窗；
- optimized：模拟「窗口短路 + 增量 token 计数」，只在真的超窗时才做全量统计。

说明：用内存 FakeRedis / FakeLLM，不依赖外部服务；LLM 摘要返回固定串，
      因此这里只测 CPU 与串行开销，真实 LLM 的往返延迟需另测。
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from loguru import logger  # noqa: E402

logger.remove()  # 关闭业务日志，避免干扰计时与输出

from app.core.memory.short_term import ShortTermMemory  # noqa: E402
from app.models.enums import MessageRole  # noqa: E402
from app.models.schemas import Message  # noqa: E402


class FakeRedis:
    """只实现 ShortTermMemory 用到的四个命令。"""

    def __init__(self) -> None:
        self._data: dict[str, list[str]] = {}

    async def rpush(self, key: str, value: str) -> None:
        self._data.setdefault(key, []).append(value)

    async def llen(self, key: str) -> int:
        return len(self._data.get(key, []))

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        data = self._data.get(key, [])
        if end == -1:
            end = len(data) - 1
        return data[start : end + 1]

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)


class FakeLLM:
    async def ainvoke(self, prompt: str) -> str:
        return "（摘要）用户关注检索与延迟。"


class IncrementalSTM(ShortTermMemory):
    """模拟优化：维护消息数与 token 计数，避免每次全量统计。"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._count = 0
        self._tokens = 0

    async def add_message(self, session_id: str, message: Message) -> None:
        key = self._key(session_id)
        await self._redis.rpush(key, self._serialize(message))
        self._count += 1
        self._tokens += self._count_tokens(message.content)

        if self._count > self.window_size or self._tokens > self.max_tokens:
            await self._compress_if_needed(session_id)
            history = await self.get_history(session_id)
            self._count = len(history)
            self._tokens = sum(self._count_tokens(m.content) for m in history)


def make_message(i: int, chars: int) -> Message:
    body = (f"第{i}轮：我们在讨论向量检索的召回率与延迟权衡，需要保留关键结论与待办。" * 20)[:chars]
    return Message(role=MessageRole.USER, content=body)


async def run(cls, turns: int, chars: int) -> tuple[list[float], int]:
    stm = cls(FakeRedis(), FakeLLM(), window_size=20, max_tokens=4000)
    latencies: list[float] = []
    for i in range(turns):
        t0 = time.perf_counter()
        await stm.add_message("bench", make_message(i, chars))
        latencies.append((time.perf_counter() - t0) * 1000)
    history = await stm.get_history("bench")
    return latencies, len(history)


def summarize(name: str, latencies: list[float]) -> None:
    ordered = sorted(latencies)
    p95 = ordered[max(0, int(round(0.95 * (len(ordered) - 1))))]
    print(
        f"{name:<12} mean={statistics.mean(latencies):>7.2f} ms | "
        f"p95={p95:>7.2f} ms | max={max(latencies):>7.2f} ms"
    )
    return p95


async def main_async(turns: int, chars: int) -> None:
    print("=" * 78)
    print(f"短期记忆基线：{turns} 轮 / 每条 {chars} 字符 / window=20 / max_tokens=4000")
    print("=" * 78)

    current, h1 = await run(ShortTermMemory, turns, chars)
    optimize, h2 = await run(IncrementalSTM, turns, chars)

    p95_current = summarize("current", current)
    p95_opt = summarize("optimized", optimize)

    print("-" * 78)
    print(f"最终历史条数：current={h1} optimized={h2}")
    if p95_opt:
        print(f"p95 改善：{p95_current / p95_opt:.1f}x（{p95_current:.2f} ms → {p95_opt:.2f} ms）")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--turns", type=int, default=200)
    parser.add_argument("--chars", type=int, default=300)
    args = parser.parse_args()
    asyncio.run(main_async(args.turns, args.chars))


if __name__ == "__main__":
    main()
