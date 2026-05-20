# -*- coding: utf-8 -*-
"""NL2SQL 评测：用 ground-truth SQL 算期望值，跑 AnalysisService，统计执行准确率。

用法：
    .\\.venv\\Scripts\\python.exe scripts\\eval_nl2sql.py --limit 10
    .\\.venv\\Scripts\\python.exe scripts\\eval_nl2sql.py --offset 10 --limit 10
    .\\.venv\\Scripts\\python.exe scripts\\eval_nl2sql.py --ids q06,q19
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from decimal import Decimal
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.routes.chat import get_model_router  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.infrastructure.database import session as db_session  # noqa: E402
from app.infrastructure.trace.tracer import Tracer  # noqa: E402
from app.services.analysis_service import AnalysisService  # noqa: E402

NUMBER_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
TOOL_ACTIONS = {"database_query", "schema_inspect"}


def extract_numbers(text: str) -> list[float]:
    values: list[float] = []
    for raw in NUMBER_RE.findall(text or ""):
        try:
            values.append(float(raw.replace(",", "")))
        except ValueError:
            continue
    return values


def score(expected: object, answer: str, tolerance: float) -> bool:
    """数值按容差匹配；字符串按忽略大小写的包含匹配。"""
    if expected is None:
        return False
    if isinstance(expected, (int, float, Decimal)):
        target = float(expected)
        numbers = extract_numbers(answer)
        if abs(target) < 1e-9:
            return any(abs(value) < 1e-9 for value in numbers)
        return any(
            abs(value - target) <= max(abs(target) * tolerance, 1e-9)
            for value in numbers
        )
    return str(expected).lower() in (answer or "").lower()


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((p / 100) * (len(ordered) - 1)))))
    return ordered[index]


async def main_async(args: argparse.Namespace) -> None:
    dataset = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    if args.ids:
        wanted = {item.strip() for item in args.ids.split(",") if item.strip()}
        dataset = [item for item in dataset if item["id"] in wanted]
    dataset = dataset[args.offset :]
    if args.limit:
        dataset = dataset[: args.limit]

    settings = get_settings()
    engine = db_session.init_engine(settings.database_url)
    db_session.configure_session(engine)

    dsn = settings.database_url.replace("+asyncpg", "")
    conn = await asyncpg.connect(dsn, ssl=False)
    service = AnalysisService(
        get_model_router(),
        db_session.async_session_factory,
        Tracer(),
    )

    rows: list[dict] = []
    try:
        for item in dataset:
            expected = await conn.fetchval(item["sql"])
            started = time.perf_counter()
            response = await service.run(item["question"], session_id="eval")
            elapsed_ms = (time.perf_counter() - started) * 1000

            actions = [
                step.get("action")
                for step in response.steps
                if isinstance(step, dict) and step.get("action")
            ]
            ok = response.success and score(
                expected,
                response.answer,
                float(item.get("tolerance", 0.01)),
            )
            rows.append(
                {
                    "id": item["id"],
                    "question": item["question"],
                    "expected": expected,
                    "answer": response.answer,
                    "ok": ok,
                    "ms": round(elapsed_ms, 1),
                    "steps": len(response.steps),
                    "actions": actions,
                    "holdout": bool(item.get("holdout")),
                    "error": response.error,
                }
            )
            print(
                f"{item['id']} ok={ok} ms={elapsed_ms:.0f} steps={len(response.steps)} "
                f"expected={expected!r} answer={response.answer[:60]!r}",
                flush=True,
            )
    finally:
        await conn.close()
        await engine.dispose()

    total = len(rows)
    passed = sum(1 for row in rows if row["ok"])
    holdout = [row for row in rows if row["holdout"]]
    holdout_pass = sum(1 for row in holdout if row["ok"])
    tool_used = sum(1 for row in rows if TOOL_ACTIONS & set(row["actions"]))
    steps = [row["steps"] for row in rows]
    latencies = [row["ms"] for row in rows]

    print("=" * 72)
    print(
        f"TOTAL={total} PASS={passed} ACC={passed / total * 100:.1f}% | "
        f"HOLDOUT={holdout_pass}/{len(holdout)} | "
        f"TOOL_USE={tool_used / total * 100:.1f}% | "
        f"AVG_STEPS={sum(steps) / total:.2f} | P95={percentile(latencies, 95):.0f}ms"
    )
    for row in rows:
        if not row["ok"]:
            print(
                f"FAIL {row['id']} expected={row['expected']!r} "
                f"answer={row['answer'][:120]!r} error={row['error']}"
            )

    report = {
        "total": total,
        "passed": passed,
        "accuracy": round(passed / total, 4) if total else 0.0,
        "holdout_passed": holdout_pass,
        "holdout_total": len(holdout),
        "tool_use_rate": round(tool_used / total, 4) if total else 0.0,
        "avg_steps": round(sum(steps) / total, 2) if total else 0.0,
        "p95_ms": round(percentile(latencies, 95), 1),
        "rows": rows,
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"report={report_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="data/eval_nl2sql.json")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--ids", default="")
    parser.add_argument("--report", default="logs/eval_nl2sql_report.json")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
