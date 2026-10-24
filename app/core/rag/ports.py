"""RAG Pipeline 端口：索引服务与知识同步只依赖该最小接口。"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class RAGIndexingPipeline(Protocol):
    """文档入库服务所需的 Pipeline 最小接口。"""

    async def index_document(
        self,
        doc_id: str,
        filename: str,
        chunks: list[str],
        chunk_ids: list[str],
    ) -> int:
        """写入文档分块向量，返回成功条数。"""
        ...

    async def delete_chunks(self, ids: list[str]) -> int:
        """删除指定分块向量。"""
        ...

    def invalidate_keyword_index(self) -> None:
        """文档变更后失效进程内 BM25 缓存。"""
        ...


__all__ = ["RAGIndexingPipeline"]
