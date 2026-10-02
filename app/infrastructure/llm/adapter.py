"""LLM 适配器：把 ModelRouter 暴露为 ``ainvoke`` 接口，供 RAG / Agent 复用。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.infrastructure.llm.model_router import ModelRouter


class RouterLLM:
    """适配 RAG 与通用 Agent 所需的文本完成接口。"""

    def __init__(self, router: ModelRouter, model_preference: str | None = None) -> None:
        self._router = router
        self._model_preference = model_preference

    async def acomplete(
        self,
        messages: Sequence[dict[str, str]],
        **kwargs: Any,
    ) -> str:
        """ReAct/Planner/Reflection 使用的别名。"""
        return await self.ainvoke(messages, **kwargs)

    async def ainvoke(
        self,
        messages: Sequence[dict[str, Any]],
        **kwargs: Any,
    ) -> str:
        payload = [dict(message) for message in messages]
        response = await self._router.chat(
            payload,
            model_preference=self._model_preference,
            **kwargs,
        )
        return response.content
