"""Agent 编排核心模块：当前生产只保留 ReAct 路径。"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, cast

from app.core.agent.react_agent import AgentResult, ReActAgent

logger = logging.getLogger(__name__)


class OrchestratorConfig(Protocol):
    def get(self, key: str, default: Any = None) -> Any: ...


class ModelRouter(Protocol):
    def get_llm(self, purpose: str) -> Any: ...


class MemoryManager(Protocol):
    async def get_relevant(
        self, session_id: str, query: str, limit: int = 8
    ) -> list[str]: ...


class ToolRegistry(Protocol):
    def list_tool_names(self) -> list[str]: ...

    async def invoke(self, name: str, arguments: dict[str, Any]) -> str: ...


class Tracer(Protocol):
    def new_trace_id(self) -> str: ...

    def start_span(
        self,
        name: str,
        trace_id: str,
        attributes: dict[str, Any] | None = None,
    ) -> Any: ...

    def end_span(self, span: Any, error: BaseException | None = None) -> None: ...


@dataclass
class IntentContext:
    intent: str = "general"
    confidence: float = 1.0
    slots: dict[str, Any] = field(default_factory=dict)
    allowed_tools: list[str] | None = None


@dataclass
class OrchestrationResult:
    answer: str
    mode_used: str
    success: bool
    trace_id: str
    intent: IntentContext
    steps: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    degraded: bool = False


class _LLMAdapter:
    def __init__(self, llm: Any) -> None:
        self._llm = llm

    async def acomplete(
        self, messages: Sequence[dict[str, str]], **kwargs: Any
    ) -> str:
        fn = getattr(self._llm, "acomplete", None)
        if callable(fn):
            return cast("str", await fn(messages, **kwargs))
        raise TypeError("LLM 需实现 acomplete")


class AgentOrchestrator:
    """任务类意图的 ReAct 编排器。"""

    def __init__(
        self,
        config: OrchestratorConfig,
        model_router: ModelRouter,
        memory_manager: MemoryManager | None,
        tool_registry: ToolRegistry,
        tracer: Tracer,
    ) -> None:
        self._config = config
        self._model_router = model_router
        self._memory = memory_manager
        self._tools = tool_registry
        self._tracer = tracer

    def _tool_names(self, intent: IntentContext) -> list[str]:
        all_names = self._tools.list_tool_names()
        if intent.allowed_tools:
            return [name for name in intent.allowed_tools if name in all_names]
        return all_names

    async def run(
        self,
        user_input: str,
        session_id: str,
        intent: IntentContext | None = None,
    ) -> OrchestrationResult:
        intent_ctx = intent or IntentContext()
        trace_id = self._tracer.new_trace_id()
        span = self._tracer.start_span(
            "orchestrator.run",
            trace_id,
            attributes={
                "session_id": session_id,
                "intent": intent_ctx.intent,
            },
        )

        steps: list[dict[str, Any]] = []
        try:
            result = await self._run_react(
                user_input,
                session_id,
                intent_ctx,
                trace_id,
                steps,
            )
            answer = result.final_answer or ""
            response = OrchestrationResult(
                answer=answer,
                mode_used="react",
                success=result.success,
                trace_id=trace_id,
                intent=intent_ctx,
                steps=steps,
                error=result.error if not result.success else None,
            )
            self._tracer.end_span(span, error=None)
            return response
        except Exception as exc:  # noqa: BLE001
            logger.exception("编排器未捕获异常")
            self._tracer.end_span(span, error=exc)
            return OrchestrationResult(
                answer="",
                mode_used="react",
                success=False,
                trace_id=trace_id,
                intent=intent_ctx,
                steps=steps,
                error=str(exc),
            )

    async def _run_react(
        self,
        user_input: str,
        session_id: str,
        intent: IntentContext,
        trace_id: str,
        steps: list[dict[str, Any]],
    ) -> AgentResult:
        llm = _LLMAdapter(self._model_router.get_llm("react"))
        max_steps = int(self._config.get("react_max_steps", 10))

        async def trace_cb(record: dict[str, Any]) -> None:
            steps.append({"ts": time.time(), **record})

        agent = ReActAgent(
            llm=llm,
            tools=self._tools,
            memory=self._memory,
            max_steps=max_steps,
            session_id=session_id,
        )
        context: dict[str, Any] = {
            "session_id": session_id,
            "tool_names": self._tool_names(intent),
            "tool_descriptions": getattr(
                self._tools, "get_tools_description", lambda: ""
            )(),
            "trace_callback": trace_cb,
            "extra_system": f"当前识别意图：{intent.intent}，槽位：{intent.slots}",
        }
        result = await agent.run(user_input, context)
        return result


__all__ = [
    "AgentOrchestrator",
    "IntentContext",
    "OrchestrationResult",
]
