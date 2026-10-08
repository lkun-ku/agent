"""文档索引生命周期服务：ETL → PostgreSQL → Milvus。

上传与知识库目录同步共用同一套“先落库、再向量化、失败可回滚”的流程，
避免两条入口各自维护稳定 ID、事务和清理逻辑。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.etl import ETLPipeline
from app.infrastructure.database.models import Document, DocumentChunk


@dataclass
class DocumentIndexingResult:
    """索引服务的稳定出参。"""

    doc: Document
    chunk_rows: list[DocumentChunk]
    chunk_ids: list[str]
    indexed: int
    chunk_count: int


class DocumentIndexingService:
    """统一文档入库服务；一个实例绑定一个已构建的 RAG Pipeline。"""

    def __init__(self, pipeline: Any | None) -> None:
        self._pipeline = pipeline

    async def index_bytes(
        self,
        session: AsyncSession,
        *,
        content: bytes,
        doc_id: str,
        filename: str,
        mime_type: str | None,
        storage_path: str | Path,
        metadata: dict[str, Any],
        etl_filename: str | None = None,
    ) -> DocumentIndexingResult:
        """解析、分块、落库并向量化一份文档。

        - 文本无法解析时抛出 ``ValueError``；
        - 向量库失败不抛出，结果中 ``indexed=0``；
        - 数据库提交失败时回滚并清理已写向量。
        """
        etl_pipeline = ETLPipeline()
        etl = await etl_pipeline.run_bytes(
            content,
            filename=etl_filename or filename,
            mime_type=mime_type,
        )
        if not etl.chunks:
            raise ValueError("未解析出文本内容")

        chunk_ids = [
            str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc_id}:{index}"))
            for index in range(len(etl.chunks))
        ]
        indexed = 0
        try:
            if self._pipeline is not None:
                indexed = await self._pipeline.index_document(
                    doc_id=doc_id,
                    filename=filename,
                    chunks=etl.chunks,
                    chunk_ids=chunk_ids,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("向量入库失败（文档仍会写入数据库）: {}", exc)

        row_meta: dict[str, Any] = {
            **metadata,
            "chunk_count": len(etl.chunks),
            "indexed_chunks": indexed,
        }
        doc = Document(
            id=doc_id,
            filename=filename,
            mime_type=mime_type,
            storage_path=str(storage_path),
            status="ready",
            meta=row_meta,
        )
        session.add(doc)

        chunk_rows: list[DocumentChunk] = []
        for index, (chunk_id, chunk_text) in enumerate(
            zip(chunk_ids, etl.chunks, strict=True)
        ):
            chunk_row = DocumentChunk(
                id=chunk_id,
                document_id=doc_id,
                chunk_index=index,
                content=chunk_text[:65000],
                vector_id=chunk_id if indexed else None,
                meta=None,
            )
            session.add(chunk_row)
            chunk_rows.append(chunk_row)

        try:
            await session.commit()
        except Exception:
            await session.rollback()
            if self._pipeline is not None and indexed:
                try:
                    await self._pipeline.delete_chunks(chunk_ids)
                except Exception as cleanup_exc:  # noqa: BLE001
                    logger.error("向量回滚失败，需人工对账: {}", cleanup_exc)
            if self._pipeline is not None:
                self._pipeline.invalidate_keyword_index()
            raise

        if self._pipeline is not None:
            if indexed:
                for chunk_row in chunk_rows:
                    chunk_row.vector_id = chunk_row.id
                doc.meta = {
                    **row_meta,
                    "indexed_chunks": indexed,
                }
                await session.commit()
            self._pipeline.invalidate_keyword_index()

        return DocumentIndexingResult(
            doc=doc,
            chunk_rows=chunk_rows,
            chunk_ids=chunk_ids,
            indexed=indexed,
            chunk_count=len(etl.chunks),
        )


__all__ = ["DocumentIndexingResult", "DocumentIndexingService"]
