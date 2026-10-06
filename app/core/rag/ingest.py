"""知识库源目录同步：扫描 ``knowledge/`` 目录，增量入库、更新与清理。

规则：
- 仅识别 .txt / .pdf / .md / .markdown / .csv / .log（不含 .json）；
- 以下划线开头的文件跳过（可放说明文档）；
- 以「文件内容 sha256」判断新增 / 更新 / 未变化；
- 目录里被删除或移走的文件，其向量与数据库记录会被一并清理（可关闭）。
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy import delete, select, text

from app.config import get_settings

KNOWLEDGE_SUFFIXES = {".txt", ".pdf", ".md", ".markdown", ".csv", ".log"}

_MIME_BY_SUFFIX = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".csv": "text/csv",
    ".log": "text/plain",
    ".pdf": "application/pdf",
}


@dataclass
class SyncReport:
    """同步结果报告。"""

    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def changed(self) -> int:
        return len(self.added) + len(self.updated) + len(self.deleted)

    def summary(self) -> str:
        return (
            f"新增 {len(self.added)} / 更新 {len(self.updated)} / "
            f"跳过 {len(self.skipped)} / 删除 {len(self.deleted)} / 错误 {len(self.errors)}"
        )


def sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def plan_sync(
    scanned: dict[str, str],
    existing: dict[str, str],
) -> dict[str, str]:
    """纯函数：根据「目录扫描结果」与「库内记录」计算每个文件的动作。

    :param scanned: 相对路径 -> sha256
    :param existing: 相对路径 -> sha256
    :return: 相对路径 -> ``add`` / ``update`` / ``skip`` / ``delete``
    """
    actions: dict[str, str] = {}
    for rel, digest in scanned.items():
        if rel not in existing:
            actions[rel] = "add"
        elif existing[rel] != digest:
            actions[rel] = "update"
        else:
            actions[rel] = "skip"
    for rel in existing:
        if rel not in scanned:
            actions[rel] = "delete"
    return actions


def scan_knowledge_dir() -> dict[str, tuple[Path, str]]:
    """扫描知识库目录，返回 相对路径 -> (绝对路径, sha256)。"""
    settings = get_settings()
    folder = Path(settings.knowledge_dir)
    if not folder.exists():
        folder.mkdir(parents=True, exist_ok=True)
        return {}

    scanned: dict[str, tuple[Path, str]] = {}
    for f in sorted(folder.rglob("*")):
        if not f.is_file():
            continue
        if f.name.startswith("_"):
            continue
        if f.suffix.lower() not in KNOWLEDGE_SUFFIXES:
            continue
        rel = f.relative_to(folder).as_posix()
        scanned[rel] = (f, sha256_bytes(f.read_bytes()))
    return scanned


_sync_lock = asyncio.Lock()


async def sync_knowledge_dir(*, force: bool = False, prune: bool = True) -> SyncReport:
    """增量同步知识库目录；同一进程内禁止并发执行。

    启动自动扫描与 ``POST /documents/sync-knowledge`` 可能同时触发。
    并发同步会导致两轮任务都把同一稳定 ``doc_id`` 当作新增/更新处理，
    最终触发 PostgreSQL 主键冲突，因此这里必须串行化。

    :param force: 为 True 时即使内容未变化也重建索引
    :param prune: 为 True 时清理目录中已不存在的文档（含向量）
    """
    async with _sync_lock:
        return await _sync_knowledge_dir_locked(force=force, prune=prune)


async def _sync_knowledge_dir_locked(
    *, force: bool = False, prune: bool = True
) -> SyncReport:
    """先获取数据库级锁，再执行单进程同步逻辑。"""
    from app.infrastructure.database.session import (
        async_session_factory,
        configure_session,
        init_engine,
    )

    if async_session_factory is None:
        configure_session(init_engine())
    factory = async_session_factory
    if factory is None:  # pragma: no cover - 上一行已保证
        raise RuntimeError("请先初始化数据库会话")

    lock_session = factory()
    lock_acquired = False
    try:
        lock_acquired = await _acquire_knowledge_sync_lock(lock_session)
        if lock_acquired:
            logger.info("已获取知识库同步 advisory lock")
        return await _sync_knowledge_dir_body(force=force, prune=prune)
    finally:
        if lock_acquired:
            try:
                await _release_knowledge_sync_lock(lock_session)
            except Exception as exc:  # noqa: BLE001
                logger.warning("释放知识库同步 advisory lock 失败: {}", exc)
        await lock_session.close()


async def _acquire_knowledge_sync_lock(session: Any) -> bool:
    """获取 PostgreSQL session-level advisory lock；SQLite 等测试库跳过。"""
    if session.bind.dialect.name != "postgresql":
        return False
    await session.execute(
        text("SELECT pg_advisory_lock(hashtext(:lock_key))"),
        {"lock_key": "enterprise_agent:knowledge_sync"},
    )
    return True


async def _release_knowledge_sync_lock(session: Any) -> None:
    if session.bind.dialect.name != "postgresql":
        return
    await session.execute(
        text("SELECT pg_advisory_unlock(hashtext(:lock_key))"),
        {"lock_key": "enterprise_agent:knowledge_sync"},
    )


async def _sync_knowledge_dir_body(
    *, force: bool = False, prune: bool = True
) -> SyncReport:
    from app.infrastructure.database.models import Document, DocumentChunk
    from app.infrastructure.database.session import (
        async_session_factory,
        configure_session,
        init_engine,
    )

    if async_session_factory is None:
        configure_session(init_engine())

    report = SyncReport()
    scanned = scan_knowledge_dir()

    from app.infrastructure.database.session import async_session_factory as session_factory

    if session_factory is None:  # pragma: no cover - 上一行已保证
        raise RuntimeError("请先初始化数据库会话")

    async with session_factory() as session:
        rows = (await session.execute(select(Document))).scalars().all()
        existing: dict[str, str] = {}
        by_rel: dict[str, Document] = {}
        for doc in rows:
            meta = doc.meta or {}
            knowledge = meta.get("knowledge") or {}
            rel = str(knowledge.get("rel") or "")
            if rel:
                existing[rel] = str(knowledge.get("sha256") or "")
                by_rel[rel] = doc

        actions = plan_sync({k: v[1] for k, v in scanned.items()}, existing)

        # 数据脱钩自愈：库里有文档、向量集合却为空/被删时，强制全量回填
        backfill = await _needs_backfill(existing, by_rel)
        if backfill:
            logger.warning("检测到向量缺失或索引不完整，将回填 {} 个知识库文档", len(backfill))
            for rel in backfill:
                actions[rel] = "update"

        if not force and not any(a != "skip" for a in actions.values()):
            report.skipped = sorted(scanned)
            logger.info("知识库目录无变化：{} 个文件", len(scanned))
            return report

        rag = await _get_pipeline_for_sync()

        async def remove_document(doc: Document) -> None:
            chunk_rows = (
                (
                    await session.execute(
                        select(DocumentChunk).where(
                            DocumentChunk.document_id == doc.id
                        )
                    )
                )
                .scalars()
                .all()
            )
            vector_ids = [c.vector_id for c in chunk_rows if c.vector_id]
            if vector_ids:
                try:
                    await rag.delete_chunks(vector_ids)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("清理向量失败 doc={} err={}", doc.id, exc)
            await session.execute(
                delete(DocumentChunk).where(DocumentChunk.document_id == doc.id)
            )
            await session.execute(delete(Document).where(Document.id == doc.id))

        for rel, action in sorted(actions.items()):
            if action == "skip" and not force:
                report.skipped.append(rel)
                continue
            if action == "delete":
                if prune:
                    try:
                        await remove_document(by_rel[rel])
                        report.deleted.append(rel)
                    except Exception as exc:  # noqa: BLE001
                        report.errors.append(f"{rel}: 清理失败 {exc}")
                else:
                    report.skipped.append(rel)
                continue

            try:
                path, digest = scanned[rel]
                # update 与 --force 重灌都需要先清掉旧记录（含向量），
                # 否则稳定 doc_id 会触发主键冲突
                if rel in by_rel:
                    await remove_document(by_rel[rel])

                etl = await _ingest_pipeline().run_bytes(
                    path.read_bytes(),
                    filename=Path(rel).name,
                    mime_type=_MIME_BY_SUFFIX.get(Path(rel).suffix.lower()),
                )
                if not etl.chunks:
                    report.errors.append(f"{rel}: 未解析出文本内容")
                    continue

                rag_pipeline = rag
                # 稳定 ID：同一文档多次同步/重建时主键不变，配合 store 的先删后插实现幂等去重
                doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"knowledge:{rel}"))
                chunk_ids = [
                    str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}:{i}"))
                    for i in range(len(etl.chunks))
                ]

                # 1) 先落库（indexed_chunks 暂记 0），避免「向量写成功、数据库失败」产生孤儿向量
                doc = Document(
                    id=doc_id,
                    filename=rel,
                    mime_type=_MIME_BY_SUFFIX.get(Path(rel).suffix.lower()),
                    storage_path=str(path),
                    status="ready",
                    meta={
                        "knowledge": {"rel": rel, "sha256": digest},
                        "chunk_count": len(etl.chunks),
                        "indexed_chunks": 0,
                    },
                )
                session.add(doc)
                chunk_rows: list[Any] = []
                for index, (chunk_id, chunk_text) in enumerate(
                    zip(chunk_ids, etl.chunks, strict=True)
                ):
                    chunk_row = DocumentChunk(
                        id=chunk_id,
                        document_id=doc_id,
                        chunk_index=index,
                        content=chunk_text[:65000],
                        vector_id=None,
                        meta=None,
                    )
                    session.add(chunk_row)
                    chunk_rows.append(chunk_row)
                await session.commit()

                # 2) 再写向量；失败则保留 indexed_chunks=0，下次同步/启动自动回填
                indexed = 0
                try:
                    indexed = await rag_pipeline.index_document(
                        doc_id=doc_id,
                        filename=rel,
                        chunks=etl.chunks,
                        chunk_ids=chunk_ids,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("向量写入失败 rel={} err={}", rel, exc)

                if indexed:
                    for chunk_row in chunk_rows:
                        chunk_row.vector_id = chunk_row.id
                    meta = dict(doc.meta or {})
                    meta["indexed_chunks"] = indexed
                    doc.meta = meta
                    await session.commit()
                    (report.added if action == "add" else report.updated).append(rel)
                else:
                    report.errors.append(f"{rel}: 向量入库失败（文本已落库，下次同步自动回填）")
            except Exception as exc:  # noqa: BLE001
                await session.rollback()
                logger.exception("同步文件失败 rel={}", rel)
                report.errors.append(f"{rel}: {exc}")

        # 清理（delete）分支没有逐条提交，这里统一提交一次；
        # 无变更时 commit 为空操作。
        await session.commit()

    if report.added or report.updated or report.deleted:
        rag.invalidate_keyword_index()

    logger.info("知识库目录同步完成 {}", report.summary())
    return report


async def _needs_backfill(
    existing: dict[str, str],
    by_rel: dict[str, Any],
) -> list[str]:
    """返回需要回填的文档相对路径。

    两类情况：
    1. 向量集合整体为空/被删（库内却有文档）→ 全量回填；
    2. 单个文档 ``indexed_chunks < chunk_count``（曾索引失败/被清）→ 单独回填。
    """
    if not existing:
        return []

    settings = get_settings()
    from app.infrastructure.vectordb.milvus_client import MilvusManager

    conn: dict[str, Any] = {}
    if settings.milvus_user:
        conn["user"] = settings.milvus_user
    if settings.milvus_password:
        conn["password"] = settings.milvus_password
    manager = MilvusManager(
        host=settings.milvus_host,
        port=str(settings.milvus_port),
        alias="ingest_backfill",
        **conn,
    )
    try:
        count = await manager.collection_count(settings.rag_collection_name)
    except Exception as exc:  # noqa: BLE001
        logger.warning("检查向量集合是否为空失败: {}", exc)
        count = -1

    if count == 0:
        return sorted(existing)

    backfill: list[str] = []
    for rel, doc in by_rel.items():
        meta = doc.meta or {}
        total = int(meta.get("chunk_count") or 0)
        indexed = int(meta.get("indexed_chunks") or 0)
        if total > indexed:
            backfill.append(rel)
    return sorted(backfill)


def _ingest_pipeline() -> Any:
    from app.etl import ETLPipeline

    return ETLPipeline()


async def _get_pipeline_for_sync() -> Any:
    from app.core.rag.pipeline import get_pipeline

    pipeline = await get_pipeline()
    if pipeline is None:
        raise RuntimeError("RAG 未启用（rag_enabled=false），无法同步知识库")
    return pipeline
