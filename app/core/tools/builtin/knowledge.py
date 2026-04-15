"""知识检索工具：封装 RAG 检索与生成，供 Agent 调用。"""

from __future__ import annotations

import json
from typing import Any

from app.core.tools.base import BaseTool, ToolParameter


class KnowledgeSearchTool(BaseTool):
    """检索企业知识库并生成带引用的回答。"""

    def __init__(self, retriever: Any, generator: Any, top_k: int = 5) -> None:
        super().__init__()
        self.name = "knowledge_search"
        self.description = "在企业知识库中检索并回答，适合文档、手册、制度类问题。"
        self.parameters = [
            ToolParameter(
                name="query",
                type="string",
                required=True,
                description="要检索的问题",
            )
        ]
        self._retriever = retriever
        self._generator = generator
        self._top_k = max(1, top_k)

    async def execute(self, **kwargs: Any) -> str:
        query = str(kwargs.get("query", "")).strip()
        if not query:
            raise ValueError("参数 query 不能为空")

        contexts = await self._retriever.retrieve(
            query,
            top_k=self._top_k,
            mode="vector",
        )
        if not contexts:
            return "知识库未检索到相关内容。"

        response = await self._generator.generate(query, contexts, [])
        return json.dumps(
            {
                "answer": response.answer,
                "citations": [c.model_dump() for c in response.citations],
                "invalid_citations": response.invalid_citations,
            },
            ensure_ascii=False,
        )
