"""通用 Agent 与当前基础设施之间的适配器。"""

from __future__ import annotations

from typing import Any

from app.core.tools.registry import ToolRegistry
from app.core.tools.schemas import ToolResult
from app.infrastructure.llm.adapter import RouterLLM
from app.infrastructure.trace.tracer import Tracer


class RegistryToolInvoker:
    """把返回 ToolResult 的注册中心适配成 ReAct 需要的文本观察。"""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def list_tool_names(self) -> list[str]:
        return self._registry.list_tool_names()

    def get_tools_description(self) -> str:
        return self._registry.get_tools_description()

    async def invoke(self, name: str, arguments: dict[str, Any]) -> str:
        result: ToolResult = await self._registry.invoke(name, arguments)
        return result.model_dump_json()


class RouterLLMProvider:
    """给 AgentOrchestrator 提供按用途复用的 RouterLLM。"""

    def __init__(self, router: Any, model_preference: str | None = None) -> None:
        self._router = router
        self._model_preference = model_preference

    def get_llm(self, purpose: str) -> RouterLLM:
        """purpose 目前只作为日志语义；模型路由仍由 ModelRouter 决定。"""
        _ = purpose
        return RouterLLM(self._router, self._model_preference)


class TraceAdapter:
    """把当前 Tracer 适配成 Orchestrator 需要的接口。"""

    def __init__(self, tracer: Tracer, trace_id: str) -> None:
        self._tracer = tracer
        self._trace_id = trace_id

    def new_trace_id(self) -> str:
        return self._trace_id

    def start_span(
        self,
        name: str,
        trace_id: str,
        attributes: dict[str, Any] | None = None,
    ) -> Any:
        _ = attributes
        return self._tracer.start_child_span(trace_id, name)

    def end_span(self, span: Any, error: BaseException | None = None) -> None:
        self._tracer.end_span(span, error=str(error) if error else None)


__all__ = ["RegistryToolInvoker", "RouterLLMProvider", "TraceAdapter"]
