"""RAG 闭环 E2E：上传文档 -> 向量入库 -> Agent 调知识检索工具回答。

前置：
- PostgreSQL 可用（默认 5433，可用环境变量 DATABASE_URL 覆盖）
- Redis / Milvus 已启动
- .env 已配置 DeepSeek Key 与 AGENT_ENABLED=true
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

import asyncpg
import httpx

ROOT = Path(__file__).resolve().parents[1]
PORT = int(os.environ.get("E2E_PORT", "8000"))
BASE = f"http://127.0.0.1:{PORT}"
DB = "postgresql://postgres:postgres@localhost:5433/agent_db"
CONTENT = (
    "星河计划（Project Aurora）的代号是 Aurora-7。"
    "项目负责人是林舟。上线时间是 2026 年 12 月 20 日。"
)


def wait_ready(timeout: float = 120.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            response = httpx.get(f"{BASE}/api/v1/health/ready", timeout=3)
            if response.status_code == 200 and response.json().get("database") == "up":
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


async def db_rows() -> list[tuple[int, str | None]]:
    conn = await asyncpg.connect(DB, ssl=False)
    try:
        rows = await conn.fetch(
            "select chunk_index, vector_id from document_chunks order by chunk_index"
        )
        return [(row["chunk_index"], row["vector_id"]) for row in rows]
    finally:
        await conn.close()


async def db_trace_count() -> int:
    conn = await asyncpg.connect(DB, ssl=False)
    try:
        return int(await conn.fetchval("select count(*) from trace_logs"))
    finally:
        await conn.close()


def ltm_rows(session_id: str) -> list[str]:
    from pymilvus import Collection, connections

    connections.connect(alias="default", host="localhost", port="19530")
    collection = Collection("agent_memory")
    collection.load()
    rows = collection.query(
        expr=f'session_id == "{session_id}"',
        output_fields=["text"],
    )
    return [str(row["text"]) for row in rows]


def main() -> None:
    (ROOT / "logs").mkdir(exist_ok=True)
    env = os.environ.copy()
    env["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@localhost:5433/agent_db"
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"

    log = (ROOT / "logs" / "e2e_rag_server.log").open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=ROOT,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    try:
        if not wait_ready():
            print("SERVER_NOT_READY")
            return

        files = {"file": ("plan.txt", CONTENT.encode("utf-8"), "text/plain")}
        upload = httpx.post(f"{BASE}/api/v1/documents/upload", files=files, timeout=180)
        print("UPLOAD", upload.status_code, upload.json())

        rows = asyncio.run(db_rows())
        print("CHUNKS", rows)
        print("VECTOR_FILLED", all(vid for _, vid in rows) and bool(rows))

        question = "星河计划的代号是什么？只回答代号。"
        started = time.perf_counter()
        answer = httpx.post(
            f"{BASE}/api/v1/chat",
            json={
                "messages": [{"role": "user", "content": question}],
                "conversation_id": "rag-e2e",
            },
            timeout=180,
        )
        elapsed = (time.perf_counter() - started) * 1000
        if answer.status_code == 200:
            print("ASK", answer.status_code, f"{elapsed:.0f}ms", repr(answer.json().get("content")))
        else:
            print("ASK_ERROR", answer.status_code, f"{elapsed:.0f}ms", answer.text[:300])

        memory_turn = httpx.post(
            f"{BASE}/api/v1/chat",
            json={
                "messages": [
                    {"role": "user", "content": "请记住我的偏好是回答要简洁。"}
                ],
                "conversation_id": "rag-memory",
            },
            timeout=180,
        )
        if memory_turn.status_code == 200:
            print("MEMORY_TURN", memory_turn.status_code, repr(memory_turn.json().get("content")))
        else:
            print("MEMORY_ERROR", memory_turn.status_code, memory_turn.text[:300])

        time.sleep(1)
        print("LTM", ltm_rows("rag-memory"))
        print("TRACE_ROWS", asyncio.run(db_trace_count()))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
        log.close()


if __name__ == "__main__":
    main()
