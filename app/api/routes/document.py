"""文档管理 API：上传与列表。"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.rag.pipeline import get_pipeline
from app.etl import ETLPipeline
from app.infrastructure.database.models import Document, DocumentChunk
from app.infrastructure.database.session import get_async_session
from app.models.schemas import DocumentInfo, DocumentUploadResponse

router = APIRouter(tags=["documents"])

# 解析器当前仅支持纯文本与 PDF
_ALLOWED_SUFFIXES = {".txt", ".pdf", ".md", ".markdown", ".csv", ".json", ".log"}


def _sanitize_filename(raw: str | None) -> str:
    """取文件名最后一段，防止 ``../`` 路径穿越与空文件名。"""
    name = (raw or "").replace("\\", "/").split("/")[-1]
    name = name.replace("\x00", "").strip()
    if not name or name in {".", ".."}:
        return "unnamed"
    return name[:200]


def _is_supported(name: str, mime: str | None) -> bool:
    """后缀白名单或纯文本 MIME 视为支持。"""
    if Path(name).suffix.lower() in _ALLOWED_SUFFIXES:
        return True
    return bool(mime and mime.startswith("text/") and mime != "text/html")


def _safe_unlink(path: Path) -> None:
    """尽量删除已落盘的临时文件，失败只记录日志。"""
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("清理上传文件失败 path={} err={}", path, exc)


async def _find_same_document(
    session: AsyncSession,
    filename: str,
    digest: str,
) -> Document | None:
    """按文件名 + 内容 sha256 查找已存在文档（用于幂等上传）。"""
    result = await session.execute(select(Document).where(Document.filename == filename))
    for doc in result.scalars().all():
        if (doc.meta or {}).get("sha256") == digest:
            return doc
    return None


@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(..., description="上传的文件（TXT / PDF / 纯文本类）"),
    session: AsyncSession = Depends(get_async_session),
) -> DocumentUploadResponse:
    """上传文档并执行 ETL 分块后写入数据库。

    校验顺序：文件名安全 → 类型白名单 → 体积上限 → 非空 → 落盘 → 解析 → 入库，
    任一步失败都会清理已落盘文件并返回明确状态码。
    """
    settings = get_settings()
    safe_name = _sanitize_filename(file.filename)
    mime = file.content_type

    if not _is_supported(safe_name, mime):
        raise HTTPException(
            status_code=415,
            detail=f"不支持的文件类型: {safe_name}，仅支持 TXT / PDF / 纯文本类文件",
        )

    max_bytes = max(1, settings.max_upload_mb) * 1024 * 1024
    try:
        # 只多读 1 字节：超过上限立即拒绝，避免把超大文件整体读进内存。
        raw = await file.read(max_bytes + 1)
    except Exception as exc:
        logger.exception("读取上传文件失败: {}", exc)
        raise HTTPException(status_code=400, detail=f"读取上传内容失败: {exc!s}") from exc

    if not raw:
        raise HTTPException(status_code=422, detail="文件内容为空")
    if len(raw) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"文件过大（{len(raw) / 1024 / 1024:.1f}MB），上限 {settings.max_upload_mb}MB",
        )

    # 内容去重：同名且 sha256 一致的文档直接复用，避免重复入库产生冗余向量
    digest = hashlib.sha256(raw).hexdigest()
    existing = await _find_same_document(session, safe_name, digest)
    if existing is not None:
        meta = existing.meta or {}
        return DocumentUploadResponse(
            document_id=existing.id,
            filename=safe_name,
            status="ready",
            chunk_count=int(meta.get("chunk_count") or 0),
            indexed_chunks=int(meta.get("indexed_chunks") or 0),
            message="文档内容未变化，已跳过重复入库",
        )

    upload_root = Path(settings.upload_dir)
    doc_id = str(uuid.uuid4())
    dest = upload_root / f"{doc_id}_{safe_name}"

    try:
        upload_root.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(dest.write_bytes, raw)
    except Exception as exc:
        logger.exception("保存上传文件失败: {}", exc)
        raise HTTPException(status_code=500, detail=f"保存文件失败: {exc!s}") from exc

    pipeline = ETLPipeline()
    try:
        etl = await pipeline.run_bytes(raw, filename=safe_name, mime_type=mime)
    except Exception as exc:
        _safe_unlink(dest)
        logger.exception("ETL 失败: {}", exc)
        raise HTTPException(status_code=422, detail=f"文档解析失败: {exc!s}") from exc

    if not etl.chunks:
        _safe_unlink(dest)
        raise HTTPException(status_code=422, detail="未能从文档中解析出任何文本内容")

    # 先写向量库（失败不影响文档落库，仅标记未索引）
    chunk_ids = [str(uuid.uuid4()) for _ in etl.chunks]
    indexed = 0
    rag_pipeline: Any | None = None
    try:
        rag_pipeline = await get_pipeline()
        if rag_pipeline is not None:
            indexed = await rag_pipeline.index_document(
                doc_id=doc_id,
                filename=safe_name,
                chunks=etl.chunks,
                chunk_ids=chunk_ids,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("向量入库失败（文档仍会写入数据库）: {}", exc)

    doc = Document(
        id=doc_id,
        filename=safe_name,
        mime_type=mime,
        storage_path=str(dest),
        status="ready",
        meta={
            "chunk_count": len(etl.chunks),
            "indexed_chunks": indexed,
            "sha256": digest,
        },
    )
    session.add(doc)

    for i, (chunk_id, chunk_text) in enumerate(zip(chunk_ids, etl.chunks, strict=True)):
        chunk = DocumentChunk(
            id=chunk_id,
            document_id=doc_id,
            chunk_index=i,
            content=chunk_text[:65000],
            vector_id=chunk_id if indexed else None,
            meta=None,
        )
        session.add(chunk)

    try:
        await session.commit()
    except Exception as exc:
        await session.rollback()
        _safe_unlink(dest)
        # 数据库回滚时同步清理已写入的向量，避免“库无记录、向量残留”的孤儿数据。
        if rag_pipeline is not None and indexed:
            try:
                await rag_pipeline.delete_chunks(chunk_ids)
            except Exception as cleanup_exc:  # noqa: BLE001
                logger.error("向量回滚失败，需人工对账: {}", cleanup_exc)
        if rag_pipeline is not None:
            rag_pipeline.invalidate_keyword_index()
        logger.exception("文档入库失败: {}", exc)
        raise HTTPException(status_code=500, detail=f"文档入库失败: {exc!s}") from exc

    if rag_pipeline is not None and indexed:
        rag_pipeline.invalidate_keyword_index()

    message = "上传、分块并入库成功" if indexed else "上传并分块成功（向量入库失败，暂不可检索）"
    return DocumentUploadResponse(
        document_id=doc_id,
        filename=safe_name,
        status="ready",
        chunk_count=len(etl.chunks),
        indexed_chunks=indexed,
        message=message,
    )


@router.post("/documents/sync-knowledge")
async def sync_knowledge_directory(
    force: bool = False,
    prune: bool = True,
) -> dict[str, Any]:
    """扫描知识库源目录（``KNOWLEDGE_DIR``），增量入库 / 更新 / 清理。

    - 新增或内容变化的文件：重新解析、分块并写入向量库；
    - 目录中已删除的文件：清理其向量与数据库记录（``prune=false`` 可跳过）；
    - 内容未变化的文件：跳过（仅做哈希比对，秒级完成）。
    """
    from app.core.rag.ingest import sync_knowledge_dir

    report = await sync_knowledge_dir(force=force, prune=prune)
    return {
        "summary": report.summary(),
        "added": report.added,
        "updated": report.updated,
        "skipped": report.skipped,
        "deleted": report.deleted,
        "errors": report.errors,
    }


@router.get("/documents", response_model=list[DocumentInfo])
async def list_documents(
    session: AsyncSession = Depends(get_async_session),
) -> list[DocumentInfo]:
    """列出已入库文档元数据。"""
    try:
        result = await session.execute(select(Document).order_by(Document.created_at.desc()))
        rows = result.scalars().all()
        out: list[DocumentInfo] = []
        for d in rows:
            out.append(
                DocumentInfo(
                    id=d.id,
                    filename=d.filename,
                    mime_type=d.mime_type,
                    status=d.status,
                    created_at=d.created_at.isoformat() if d.created_at else None,
                )
            )
        return out
    except Exception as exc:
        logger.exception("查询文档列表失败: {}", exc)
        raise HTTPException(status_code=500, detail=f"查询失败: {exc!s}") from exc
