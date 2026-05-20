"""分块基线：三种策略在长中文文本上的耗时、块数与 token 分布。

用法：
    .\\.venv\\Scripts\\python.exe scripts\\bench_chunker.py
    .\\.venv\\Scripts\\python.exe scripts\\bench_chunker.py --chars 500000 --repeat 3

关注点：
- fixed 按字符切，其它两种按 token 计 → 同一 chunk_size 的信息量不同；
- recursive 在合并/递归时对同一段文本反复 encode，长文档下成本会放大。
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from loguru import logger  # noqa: E402

logger.remove()

from app.etl.chunker import ChunkStrategy, DocumentChunker  # noqa: E402


def make_text(target_chars: int) -> str:
    sentence = (
        "向量数据库支持多种索引类型，包括扁平索引、倒排文件索引和分层可导航小世界图，"
        "检索时需要权衡召回率、延迟与内存占用。"
    )
    para = sentence * 4
    count = target_chars // len(para) + 1
    return ("\n\n".join([para] * count))[:target_chars]


def pct(values: list[int], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, int(round((p / 100) * (len(ordered) - 1)))))
    return float(ordered[k])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chars", type=int, default=1_000_000)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--chunk-size", type=int, default=512)
    parser.add_argument("--overlap", type=int, default=64)
    args = parser.parse_args()

    text = make_text(args.chars)
    chunker = DocumentChunker(chunk_size=args.chunk_size, chunk_overlap=args.overlap)

    print("=" * 78)
    print(f"分块基线：{len(text):,} 字符 / chunk_size={args.chunk_size} / overlap={args.overlap}")
    print("=" * 78)
    print(f"{'strategy':<10} | {'median(s)':>9} | {'min(s)':>8} | {'chunks':>7} | {'tok p50':>8} | {'tok p95':>8}")
    print("-" * 78)

    for strategy in (ChunkStrategy.FIXED, ChunkStrategy.RECURSIVE, ChunkStrategy.PARAGRAPH):
        samples: list[float] = []
        chunks: list[str] = []
        for _ in range(args.repeat):
            t0 = time.perf_counter()
            chunks = chunker.chunk(text, strategy=strategy)
            samples.append(time.perf_counter() - t0)

        token_counts = [chunker._len(c) for c in chunks]
        print(
            f"{strategy.value:<10} | {statistics.median(samples):>9.3f} | {min(samples):>8.3f} | "
            f"{len(chunks):>7} | {pct(token_counts, 50):>8.0f} | {pct(token_counts, 95):>8.0f}"
        )

    print("-" * 78)
    print("提示：fixed 的块按字符切，token p50 会明显偏离 chunk_size；其它两种按 token 计。")


if __name__ == "__main__":
    main()
