"""RAG prompt 预算基线：top-k 上下文全量拼接 vs 每块 token 上限。

用法：
    .\\.venv\\Scripts\\python.exe scripts\\bench_prompt.py
    .\\.venv\\Scripts\\python.exe scripts\\bench_prompt.py --contexts 10 --chars 600 --budget 300

说明：
- 直接调用 RAGGenerator._build_messages 构造真实 prompt，用 cl100k_base 计数；
- “预算版”只在脚本内对上下文做截断，不改业务代码；
- 这里只测 token，不调用 LLM；质量是否下降需另做小样本人工/自动比对。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tiktoken  # noqa: E402
from loguru import logger  # noqa: E402

logger.remove()

from app.core.rag.generator import RAGGenerator  # noqa: E402
from app.models.schemas import RetrievalResult  # noqa: E402


def count_prompt_tokens(messages: list[dict[str, str]], enc) -> int:
    return sum(len(enc.encode(m["content"])) for m in messages)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contexts", type=int, default=10)
    parser.add_argument("--chars", type=int, default=600)
    parser.add_argument("--budget", type=int, default=300)
    args = parser.parse_args()

    enc = tiktoken.get_encoding("cl100k_base")
    base = (
        "向量数据库支持多种索引类型，包括扁平索引、倒排文件索引和分层可导航小世界图，"
        "检索时需要权衡召回率、延迟与内存占用。"
    )
    contexts = [
        RetrievalResult(
            id=f"c{i}",
            content=f"第{i}段：" + (base * 12)[: args.chars],
            score=1.0 - i * 0.01,
        )
        for i in range(args.contexts)
    ]

    generator = RAGGenerator(
        llm=None,
        max_context_tokens=args.budget,
        max_prompt_tokens=3500,
    )
    query = "请总结这些资料并给出结论"

    full_msgs = generator._build_messages(query, contexts, [])
    full_tokens = count_prompt_tokens(full_msgs, enc)

    budgeted = generator._select_contexts(contexts)
    small_msgs = generator._build_messages(query, budgeted, [])
    small_tokens = count_prompt_tokens(small_msgs, enc)

    print("=" * 74)
    print(f"RAG prompt 预算：{args.contexts} 块 / 每块 {args.chars} 字 / 预算 {args.budget} token")
    print("=" * 74)
    print(f"{'版本':<12} | {'prompt tokens':>14} | {'相对变化':>10}")
    print("-" * 74)
    print(f"{'全量拼接':<12} | {full_tokens:>14,} | {'基线':>10}")
    print(f"{'每块预算':<12} | {small_tokens:>14,} | {f'{(small_tokens / full_tokens - 1) * 100:+.1f}%':>10}")
    print("-" * 74)
    print(f"节省：{full_tokens - small_tokens:,} token（{(1 - small_tokens / full_tokens) * 100:.1f}%）")
    print("注意：截断可能损失长块尾部信息，需用 10 条小样本验证召回/faithfulness 不降。")


if __name__ == "__main__":
    main()
