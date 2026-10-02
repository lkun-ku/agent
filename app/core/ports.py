"""核心端口定义：避免各模块重复声明不兼容的 Protocol。

这里只定义最小职责边界；具体实现由 infrastructure 或 core 适配器提供。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Protocol

from app.core.tools.schemas import ToolResult


class TextCompletionPort(Protocol):
    """返回纯文本的 LLM 端口；ReAct/Planner/Reflection 使用。"""

    async def acomplete(
        self,
        messages: Sequence[dict[str, str]],
        **kwargs: Any,
    ) -> str: ...


class AsyncEmbedderPort(Protocol):
    """异步嵌入端口。"""

    async def aembed_query(self, text: str) -> list[float]: ...

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]: ...


class VectorSearchPort(Protocol):
    """向量检索端口；实现方负责连接管理与字段映射。"""

    async def search(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int = 10,
        *,
        output_fields: list[str] | None = None,
        **search_params: Any,
    ) -> list[dict[str, Any]]: ...


class ToolInvokerPort(Protocol):
    """Agent 工具调用端口。"""

    def list_tool_names(self) -> list[str]: ...

    def get_tools_description(self) -> str: ...

    async def invoke(self, name: str, arguments: dict[str, Any]) -> ToolResult: ...


KeywordProvider = Callable[[], Awaitable[dict[str, str]]]
