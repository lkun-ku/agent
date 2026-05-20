"""BM25 建索引基线：逐条 add_document（每次重算全量 IDF）vs 一次性批量构建。

用法：
    .\\.venv\\Scripts\\python.exe scripts\\bench_bm25.py
    .\\.venv\\Scripts\\python.exe scripts\\bench_bm25.py --sizes 500 1000 2000 --repeat 3

说明：
- 语料用「词{0..19999}」随机组合，保证词表随文档数增长（贴近真实长尾词）。
- 批量构建只在本脚本内模拟，不改业务代码；两种实现产出的 search 结果会做一致性校验。
"""

from __future__ import annotations

import argparse
import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from loguru import logger  # noqa: E402

logger.remove()

from app.core.rag.retriever import _BM25Index  # noqa: E402


def make_docs(n: int, tokens_per_doc: int = 40, seed: int = 42) -> list[tuple[str, str]]:
    rnd = random.Random(seed)
    docs: list[tuple[str, str]] = []
    for i in range(n):
        words = [f"词{rnd.randrange(20000)}" for _ in range(tokens_per_doc)]
        docs.append((f"doc-{i}", " ".join(words)))
    return docs


def build_incremental(docs: list[tuple[str, str]]) -> _BM25Index:
    """现状：每插一条都重算全量 IDF。"""
    idx = _BM25Index()
    for did, text in docs:
        idx.add_document(did, text)
    return idx


def build_batch(docs: list[tuple[str, str]]) -> _BM25Index:
    """改后：直接调用 _BM25Index.build（一次统计 df/avgdl，统一算 IDF）。"""
    idx = _BM25Index()
    idx.build(dict(docs))
    return idx


def timeit(fn, docs: list[tuple[str, str]], repeat: int) -> tuple[float, float, float]:
    samples: list[float] = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn(docs)
        samples.append(time.perf_counter() - t0)
    return statistics.median(samples), min(samples), max(samples)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", nargs="+", type=int, default=[200, 400, 800])
    parser.add_argument("--repeat", type=int, default=3)
    args = parser.parse_args()

    print("=" * 72)
    print("BM25 建索引基线（词表随文档数增长，40 token/篇）")
    print("=" * 72)
    print(f"{'docs':>6} | {'incremental(s)':>15} | {'batch(s)':>10} | {'speedup':>8} | {'ms/doc':>8}")
    print("-" * 72)

    for n in args.sizes:
        docs = make_docs(n)
        inc_med, _, _ = timeit(build_incremental, docs, args.repeat)
        bat_med, _, _ = timeit(build_batch, docs, args.repeat)
        speedup = inc_med / bat_med if bat_med else float("inf")
        print(f"{n:>6} | {inc_med:>15.3f} | {bat_med:>10.3f} | {speedup:>7.1f}x | {inc_med / n * 1000:>8.2f}")

    # 一致性校验：两种构建方式对同一 query 的结果应一致
    docs = make_docs(300)
    a = build_incremental(docs)
    b = build_batch(docs)
    q = docs[0][1].split()[0]
    ra = a.search(q, 5)
    rb = b.search(q, 5)
    print("-" * 72)
    print(f"一致性校验 query={q!r} incremental={ra[:2]} batch={rb[:2]} match={ra == rb}")


if __name__ == "__main__":
    main()
