# 说明：本文件是 CLI 胶水层。argparse.Namespace 的属性恒为 Any，且 pymilvus / redis
# 未提供完整类型存根，Any/Unknown 告警无法通过注解消除，故按规则豁免（行为不变）。
# pyright: reportAny=false, reportExplicitAny=false, reportMissingTypeStubs=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false, reportUnnecessaryComparison=false

"""命令行工具集：统一入口 ``python main.py <命令>``。

子命令一览::

    serve                  启动 API 服务（默认命令，可省略）
    init-db                创建数据库表（幂等）
    sync                   增量同步 knowledge/ 知识库目录
    doctor                 环境自检：配置 / 数据库 / Redis / Milvus / 模型
    check                  RAG 校验：上传目录文档 + 按问题清单提问判分
    ask "问题"             单条提问（走完整 RAG 链路）
    documents              列出已入库文档
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

if __package__ in (None, ""):  # 允许 python app/cli.py 直接运行
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

ALLOWED_SUFFIXES = {".txt", ".pdf", ".md", ".markdown", ".csv", ".json", ".log"}


def _bool(value: Any) -> bool:
    """argparse.Namespace 属性为 Any，统一收窄为 bool。"""
    return bool(value)


def _text(value: Any) -> str:
    """把 argparse 属性安全地转为 str。"""
    return cast("str", value)


def _int(value: Any) -> int:
    """把 argparse 属性安全地转为 int。"""
    return cast("int", value)


# ---------------------------------------------------------------------------
# serve
# ---------------------------------------------------------------------------
def _serve(args: argparse.Namespace) -> None:
    import uvicorn

    from app.config import get_settings

    settings = get_settings()
    host = _text(args.host) if args.host is not None else settings.host
    port = _int(args.port) if args.port is not None else settings.port
    reload_enabled = _bool(args.reload)

    local = f"http://127.0.0.1:{port}"
    print()
    print(f"  本机访问   {local}")
    print(f"  聊天演示   {local}/ui")
    print(f"  API 文档   {local}/docs")
    print(f"  健康检查   {local}/api/v1/health")
    if host == "0.0.0.0":
        print("  监听地址为 0.0.0.0（所有网卡），浏览器请用 127.0.0.1 或 localhost 打开")
    print()

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload_enabled,
        log_level=(settings.log_level or "INFO").lower(),
    )


# ---------------------------------------------------------------------------
# init-db
# ---------------------------------------------------------------------------
def _init_db(_args: argparse.Namespace) -> None:
    from app.config import get_settings
    from app.infrastructure.database.models import Base
    from app.infrastructure.database.session import init_engine

    async def _create() -> list[str]:
        engine = init_engine(get_settings().database_url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            tables = sorted(Base.metadata.tables)
        await engine.dispose()
        return tables

    tables = asyncio.run(_create())
    print("数据库表初始化完成：", ", ".join(tables))


# ---------------------------------------------------------------------------
# sync
# ---------------------------------------------------------------------------
def _sync(args: argparse.Namespace) -> None:
    from app.core.rag.ingest import sync_knowledge_dir

    report = asyncio.run(
        sync_knowledge_dir(force=_bool(args.force), prune=not _bool(args.no_prune))
    )
    print("summary:", report.summary())
    for key in ("added", "updated", "deleted", "skipped", "errors"):
        items = cast("list[str]", getattr(report, key))
        if items:
            print(f"{key}: {items}")
    if report.errors:
        sys.exit(1)


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------
def _doctor(args: argparse.Namespace) -> None:
    results: list[tuple[str, bool, str]] = []

    def record(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))

    from app.config import get_settings

    settings = get_settings()

    record(
        "配置",
        bool(settings.openai_api_key),
        f"key={'已配置' if settings.openai_api_key else '未配置'} "
        + f"model={settings.openai_model} base={settings.openai_api_base}",
    )

    async def checks() -> None:
        # PostgreSQL
        try:
            from app.infrastructure.database.session import init_engine

            engine = init_engine(settings.database_url)
            from sqlalchemy import text

            async with engine.begin() as conn:
                _ = await conn.execute(text("SELECT 1"))
            await engine.dispose()
            record("PostgreSQL", True, "连接正常")
        except Exception as exc:  # noqa: BLE001
            record("PostgreSQL", False, str(exc)[:100])

        # Redis
        try:
            import redis.asyncio as aioredis

            client: Any = aioredis.Redis.from_url(
                settings.redis_url, socket_connect_timeout=3
            )
            _ = await client.ping()
            await client.aclose()
            record("Redis", True, settings.redis_url)
        except Exception as exc:  # noqa: BLE001
            record("Redis", False, str(exc)[:100])

        # Milvus（pymilvus 无类型存根，调用点显式忽略类型检查）
        try:
            from pymilvus import connections, utility

            connections.connect(
                alias="doctor",
                host=settings.milvus_host,
                port=str(settings.milvus_port),
            )
            names: Any = utility.list_collections(using="doctor")
            connections.disconnect("doctor")
            record("Milvus", True, f"{len(names)} 个集合")
        except Exception as exc:  # noqa: BLE001
            record("Milvus", False, str(exc)[:100])

    asyncio.run(checks())

    if _bool(args.model):
        try:
            from app.infrastructure.embeddings import get_embedder

            embedder = get_embedder(
                settings.embedding_model, settings.embedding_local_only
            )
            record(
                "嵌入模型",
                True,
                f"{settings.embedding_model} dim={embedder.dimension}",
            )
        except Exception as exc:  # noqa: BLE001
            record("嵌入模型", False, str(exc)[:100])

    if _bool(args.llm):
        try:
            from app.infrastructure.llm.model_router import ModelConfig, ModelRouter

            router = ModelRouter(
                [
                    ModelConfig(
                        model_id=settings.openai_model,
                        api_key=settings.openai_api_key,
                        base_url=settings.openai_api_base or None,
                        thinking=False,
                    )
                ]
            )
            resp = asyncio.run(
                router.chat([{"role": "user", "content": "回复 OK"}], max_tokens=8)
            )
            record("LLM 连通", bool(resp.content), f"model={resp.model_id}")
        except Exception as exc:  # noqa: BLE001
            record("LLM 连通", False, str(exc)[:100])

    ok = all(passed for _, passed, _ in results)
    for name, passed, detail in results:
        print(f"[{'OK' if passed else 'FAIL'}] {name}: {detail}")
    sys.exit(0 if ok else 1)


# ---------------------------------------------------------------------------
# check / ask / documents（基于 HTTP，需服务已启动）
# ---------------------------------------------------------------------------
def _client(base: str) -> httpx.Client:
    return httpx.Client(trust_env=False, timeout=300, base_url=base)


def _collect_files(folder: Path, exclude: Path | None) -> list[Path]:
    files = [
        f
        for f in sorted(folder.rglob("*"))
        if f.is_file()
        and not f.name.startswith("_")
        and f.suffix.lower() in ALLOWED_SUFFIXES
        and (exclude is None or f.resolve() != exclude.resolve())
    ]
    return files


def _run_check(args: argparse.Namespace) -> int:
    client = _client(_text(args.base))

    if not _bool(args.skip_upload):
        folder = Path(_text(args.dir))
        if not folder.exists():
            print(f"[WARN] 目录不存在：{folder.resolve()}")
        else:
            files = _collect_files(folder, Path(_text(args.questions)).resolve())
            print(f"[upload] 待上传 {len(files)} 个文件")
            failed = False
            for path in files:
                resp = client.post(
                    "/api/v1/documents/upload",
                    files={
                        "file": (path.name, path.read_bytes(), "application/octet-stream")
                    },
                )
                if resp.status_code != 200:
                    print(f"[FAIL] 上传 {path.name}: {resp.status_code} {resp.text[:120]}")
                    failed = True
                    continue
                data = cast("dict[str, Any]", resp.json())
                mark = "OK" if data["indexed_chunks"] == data["chunk_count"] else "WARN"
                print(
                    f"[{mark}] 上传 {path.name}: chunks={data['chunk_count']} "
                    + f"indexed={data['indexed_chunks']}"
                )
            if failed:
                return 1

    qfile = Path(_text(args.questions))
    if not qfile.exists():
        print(f"[ask] 未找到问题清单 {qfile}，跳过提问")
        return 0

    questions = cast(
        "list[dict[str, Any]]", json.loads(qfile.read_text(encoding="utf-8"))
    )
    all_ok = True
    for item in questions:
        question = str(item.get("q", ""))
        expects = [str(x) for x in cast("list[Any]", item.get("expect") or [])]
        resp = client.post(
            "/api/v1/chat",
            json={"messages": [{"role": "user", "content": question}], "temperature": 0.2},
        )
        if resp.status_code != 200:
            print(f"[FAIL] {question}: HTTP {resp.status_code}")
            all_ok = False
            continue
        data = cast("dict[str, Any]", resp.json())
        citations = cast("list[dict[str, Any]]", data.get("citations") or [])
        corpus = str(data.get("content", "")) + " ".join(
            str(c.get("snippet", "")) for c in citations
        )
        hit = [kw for kw in expects if kw in corpus]
        passed = (not expects) or bool(hit)
        print(
            f"[{'PASS' if passed else 'FAIL'}] {question} "
            + f"(citations={len(citations)})"
        )
        print(f"       answer: {str(data.get('content', ''))[:120]}")
        if not passed:
            all_ok = False
    client.close()
    print("ALL PASS" if all_ok else "存在问题")
    return 0 if all_ok else 1


def _check(args: argparse.Namespace) -> int:
    if _bool(args.clean) and not _bool(args.yes):
        print("--clean 会清空知识库（数据库表 + 向量集合），请同时传 --yes 确认")
        return 2
    if _bool(args.clean):
        from pymilvus import connections, utility
        from sqlalchemy import text

        from app.config import get_settings
        from app.infrastructure.database.session import init_engine

        settings = get_settings()

        async def _truncate() -> None:
            engine = init_engine(settings.database_url)
            async with engine.begin() as conn:
                _ = await conn.execute(text("TRUNCATE document_chunks, documents CASCADE"))
            await engine.dispose()

        asyncio.run(_truncate())
        connections.connect(
            alias="check", host=settings.milvus_host, port=str(settings.milvus_port)
        )
        # 两个方法均为同步实现，无需 await
        if utility.has_collection(
            settings.rag_collection_name, using="check"
        ):
            _ = utility.drop_collection(
                settings.rag_collection_name, using="check"
            )
        print("[clean] 知识库已重置")

    return _run_check(args)


def _ask(args: argparse.Namespace) -> None:
    client = _client(_text(args.base))
    resp = client.post(
        "/api/v1/chat",
        json={
            "messages": [{"role": "user", "content": _text(args.question)}],
            "temperature": cast("float", args.temperature),
        },
    )
    if resp.status_code != 200:
        print(f"请求失败 HTTP {resp.status_code}: {resp.text[:200]}")
        sys.exit(1)
    data = cast("dict[str, Any]", resp.json())
    print(str(data.get("content", "")))
    citations = cast("list[dict[str, Any]]", data.get("citations") or [])
    if citations:
        print("\n引用来源:")
        for c in citations:
            print(f"  [{c['index']}] {str(c.get('snippet', ''))[:80]}")
    client.close()


def _documents(_args: argparse.Namespace) -> int:
    from sqlalchemy import select

    from app.config import get_settings
    from app.infrastructure.database.models import Document
    from app.infrastructure.database.session import init_engine

    async def _list() -> list[Document]:
        engine = init_engine(get_settings().database_url)
        from app.infrastructure.database.session import configure_session

        _ = configure_session(engine)
        from app.infrastructure.database.session import async_session_factory

        assert async_session_factory is not None
        async with async_session_factory() as session:
            rows = (
                (await session.execute(select(Document).order_by(Document.created_at)))
                .scalars()
                .all()
            )
            await engine.dispose()
            return list(rows)

    rows = asyncio.run(_list())
    if not rows:
        print("（暂无文档）")
        return 0
    for d in rows:
        meta = d.meta or {}
        print(
            f"- {d.filename} | status={d.status} | chunks={meta.get('chunk_count', '?')}"
            + f" | indexed={meta.get('indexed_chunks', '?')} | {d.created_at:%Y-%m-%d %H:%M}"
        )
    return 0


# ---------------------------------------------------------------------------
# 解析与分发
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="app.main",
        description="企业级 AI Agent 命令行工具",
    )
    sub = parser.add_subparsers(dest="command")

    p_serve = sub.add_parser("serve", help="启动 API 服务")
    _ = p_serve.add_argument("--host", default=None, help="监听地址（默认取 HOST）")
    _ = p_serve.add_argument("--port", type=int, default=None, help="监听端口（默认取 PORT）")
    _ = p_serve.add_argument("--reload", action="store_true", help="开发模式热重载")
    p_serve.set_defaults(func=_serve, needs_config_host=True)

    p_init_db = sub.add_parser("init-db", help="创建数据库表（幂等）")
    p_init_db.set_defaults(func=_init_db)

    p_sync = sub.add_parser("sync", help="增量同步 knowledge/ 知识库目录")
    _ = p_sync.add_argument("--force", action="store_true", help="未变化也重建索引")
    _ = p_sync.add_argument("--no-prune", action="store_true", help="不清理已删除文件")
    p_sync.set_defaults(func=_sync)

    p_doctor = sub.add_parser("doctor", help="环境自检（配置/数据库/Redis/Milvus）")
    _ = p_doctor.add_argument("--model", action="store_true", help="同时加载嵌入模型验证")
    _ = p_doctor.add_argument("--llm", action="store_true", help="同时验证 LLM 连通性")
    p_doctor.set_defaults(func=_doctor)

    p_check = sub.add_parser("check", help="RAG 校验：上传文档 + 按问题清单判分")
    _ = p_check.add_argument("--base", default="http://127.0.0.1:8000", help="服务地址")
    _ = p_check.add_argument("--dir", default="knowledge", help="文档目录")
    _ = p_check.add_argument(
        "--questions", default="knowledge/questions.json", help="问题清单 JSON"
    )
    _ = p_check.add_argument("--clean", action="store_true", help="先重置知识库")
    _ = p_check.add_argument("--yes", action="store_true", help="--clean 的确认")
    _ = p_check.add_argument("--skip-upload", action="store_true", help="只提问")
    p_check.set_defaults(func=_check)

    p_ask = sub.add_parser("ask", help="单条提问（走完整 RAG 链路）")
    _ = p_ask.add_argument("question", help="问题内容")
    _ = p_ask.add_argument("--base", default="http://127.0.0.1:8000", help="服务地址")
    _ = p_ask.add_argument("--temperature", type=float, default=0.7)
    p_ask.set_defaults(func=_ask)

    p_documents = sub.add_parser("documents", help="列出已入库文档")
    p_documents.set_defaults(func=_documents)

    parser.set_defaults(func=_serve, command="serve")
    return parser


def main(argv: list[str] | None = None) -> int:
    """命令行入口；不带子命令时等价于 ``serve``。返回进程退出码。"""
    parser = build_parser()
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        argv = ["serve"]
    args = parser.parse_args(argv)
    handler = cast("Callable[[argparse.Namespace], Any]", args.func)
    code = handler(args)
    return int(code) if isinstance(code, int) else 0


if __name__ == "__main__":
    raise SystemExit(main())
