"""端到端检查：DeepSeek + Agent 编排 + 真实短期/长期记忆 + 工具调用。

用法：
    .\\.venv\\Scripts\\python.exe scripts\\e2e_check.py

前置：Redis / Milvus 已启动，.env 已配置 OPENAI_API_KEY / OPENAI_API_BASE / AGENT_ENABLED=true。
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
PORT = int(os.environ.get("E2E_PORT", "8000"))
BASE = f"http://127.0.0.1:{PORT}"
LOG = ROOT / "logs" / "e2e_server.log"


def wait_health(timeout: float = 60.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(f"{BASE}/api/v1/health", timeout=2).status_code == 200:
                return True
        except Exception:
            time.sleep(1)
    return False


def main() -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"

    log = LOG.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=ROOT,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    try:
        if not wait_health():
            print("SERVER_NOT_READY")
            return

        questions = [
            "我叫测试用户，请记住我的名字，我的偏好是回答要简洁。",
            "我叫什么？请只回答名字。",
            "我的偏好是什么？请只回答偏好。",
            "1+2 等于几？请用工具计算并只给结果。",
        ]
        for question in questions:
            started = time.perf_counter()
            response = httpx.post(
                f"{BASE}/api/v1/chat",
                json={
                    "messages": [{"role": "user", "content": question}],
                    "conversation_id": "e2e",
                },
                timeout=180,
            )
            elapsed = (time.perf_counter() - started) * 1000
            data = response.json()
            print(
                f"status={response.status_code} ms={elapsed:.0f} "
                f"content={data.get('content')!r} trace={data.get('trace_id')}"
            )

        # 流式接口（复用单例客户端）
        started = time.perf_counter()
        chunks: list[str] = []
        stream_status = 0
        with httpx.stream(
            "POST",
            f"{BASE}/api/v1/chat/stream",
            json={"messages": [{"role": "user", "content": "用一句话介绍你自己"}]},
            timeout=120,
        ) as stream_response:
            stream_status = stream_response.status_code
            for line in stream_response.iter_lines():
                if line.startswith("data:"):
                    chunks.append(line)
        elapsed = (time.perf_counter() - started) * 1000
        print(
            f"stream status={stream_status} ms={elapsed:.0f} "
            f"chunks={len(chunks)} last={chunks[-1] if chunks else None}"
        )
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
        log.close()


if __name__ == "__main__":
    main()
