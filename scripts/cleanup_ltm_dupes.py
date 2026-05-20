"""清理长期记忆中的重复条目（仅限指定会话，默认 dry-run）。

用法：
    .\\.venv\\Scripts\\python.exe scripts\\cleanup_ltm_dupes.py
    .\\.venv\\Scripts\\python.exe scripts\\cleanup_ltm_dupes.py --apply
"""

from __future__ import annotations

import argparse
from collections import defaultdict

from pymilvus import Collection, connections


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", default="agent_memory")
    parser.add_argument("--sessions", default="rag-memory,e2e")
    parser.add_argument("--drop-questions", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    sessions = [s.strip() for s in args.sessions.split(",") if s.strip()]
    expr = "session_id in [" + ", ".join(f'"{s}"' for s in sessions) + "]"

    connections.connect(alias="default", host="localhost", port="19530")
    collection = Collection(args.collection)
    collection.load()
    rows = collection.query(expr=expr, output_fields=["id", "text", "session_id"])

    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in rows:
        groups[(str(row["session_id"]), str(row["text"]))].append(str(row["id"]))

    duplicates = {key: ids for key, ids in groups.items() if len(ids) > 1}
    print(f"total_rows={len(rows)} groups={len(groups)} duplicate_groups={len(duplicates)}")
    for (session_id, text), ids in duplicates.items():
        print(f"  {len(ids)}x session={session_id} text={text[:40]!r}")

    question_ids: set[str] = set()
    if args.drop_questions:
        markers = ("什么", "吗", "怎么", "如何", "哪", "？", "?")
        question_ids = {
            str(row["id"])
            for row in rows
            if any(marker in str(row["text"]) for marker in markers)
        }
        print(f"question_rows={len(question_ids)}")

    if not args.apply:
        print("dry-run：加 --apply 才会删除")
        return

    to_delete: set[str] = set(question_ids)
    for ids in duplicates.values():
        to_delete.update(ids[1:])

    removed = 0
    if to_delete:
        delete_expr = "id in [" + ", ".join(f'"{i}"' for i in sorted(to_delete)) + "]"
        collection.delete(delete_expr)
        removed = len(to_delete)
        collection.flush()
    print(f"deleted={removed}")


if __name__ == "__main__":
    main()
