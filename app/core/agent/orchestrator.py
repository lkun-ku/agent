"""
Agent 编排器：根据意图与模式选择 ReAct 或 Plan-and-Execute，串联记忆、工具与追踪。
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from app.core.agent.planner import PlannerAgent
from app.core.agent.react_agent import AgentResult, ReActAgent
from app.core.agent.reflection import ReflectionAgent, ReflectionReport

logger = logging.getLogger(__name__)

OrchestrationMode = Literal["react", "plan_execute"]


# ---------------------------------------------------------------------------
# 依赖抽象（由基础设施层实现，此处仅约定接口）
# ---------------------------------------------------------------------------
class OrchestratorConfig(Protocol):
    """编排器配置：可从 dict 或配置对象读取。"""

    def get(self, key: str, default: Any = None) -> Any:
        ...


class ModelRouter(Protocol):
    """模型路由：按场景返回可调用的 LLM 封装。"""

    def get_llm(self, purpose: str) -> Any:
        """
        purpose 示例：\"react\"、\"planner\"、\"reflection\"
        返回对象需实现 async def acomplete(messages, **kwargs) -> str
        """
        ...


class MemoryManager(Protocol):
    """记忆管理。"""

    async def get_relevant(self, session_id: str, query: str, limit: int = 8) -> list[str]:
        ...

    async def append_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        ...


class ToolRegistry(Protocol):
    """工具注册表：列举与调用。"""

    def list_tool_names(self) -> list[str]:
        ...

    async def invoke(self, name: str, arguments: dict[str, Any]) -> str:
        ...


class Tracer(Protocol):
    """全链路追踪：span + 事件日志。"""

    def new_trace_id(self) -> str:
        ...

    def start_span(self, name: str, trace_id: str, attributes: dict[str, Any] | None = None) -> Any:
        ...

    def end_span(self, span: Any, error: BaseException | None = None) -> None:
        ...

    def log_event(self, trace_id: str, name: str, payload: dict[str, Any]) -> None:
        ...


# ---------------------------------------------------------------------------
# 响应与意图上下文
# ---------------------------------------------------------------------------
@dataclass
class IntentContext:
    """
    意图识别结果（由上游 NLU/分类器注入）。
    编排器据此选择策略、工具子集或是否跳过重推理。
    """

    intent: str = "general"
    confidence: float = 1.0
    slots: dict[str, Any] = field(default_factory=dict)
    preferred_mode: OrchestrationMode | None = None
    allowed_tools: list[str] | None = None


@dataclass
class AgentResponse:
    """编排器对外统一响应。"""

    answer: str
    mode_used: OrchestrationMode
    success: bool
    trace_id: str
    intent: IntentContext
    steps: list[dict[str, Any]] = field(default_factory=list)
    reflection: ReflectionReport | None = None
    error: str | None = None
    degraded: bool = False


class _LLMAdapter:
    """将 ModelRouter 返回的 llm 统一为 acomplete 调用。"""

    def __init__(self, llm: Any) -> None:
        self._llm = llm

    async def acomplete(self, messages: Sequence[dict[str, str]], **kwargs: Any) -> str:
        fn = getattr(self._llm, "acomplete", None)
        if callable(fn):
            return await fn(messages, **kwargs)
        fn2 = getattr(self._llm, "complete", None)
        if callable(fn2):
            # 同步实现时在线程中运行（简化：直接调用）
            import asyncio

            return await asyncio.to_thread(fn2, messages, **kwargs)
        raise TypeError("LLM 需实现 acomplete 或 complete")


class AgentOrchestrator:
    """
    Agent 编排器：
    - 根据 IntentContext 与 mode 选择 ReAct 或 Plan-and-Execute；
    - 管理会话级记忆与工具；
    - 记录全链路 trace；
    - 异常时降级（例如 Plan 失败则回退 ReAct）。
    """

    def __init__(
        self,
        config: OrchestratorConfig,
        model_router: ModelRouter,
        memory_manager: MemoryManager,
        tool_registry: ToolRegistry,
        tracer: Tracer,
    ) -> None:
        self._config = config
        self._model_router = model_router
        self._memory = memory_manager
        self._tools = tool_registry
        self._tracer = tracer
        self._enable_reflection = bool(config.get("enable_reflection", True))
        self._fallback_on_plan_failure = bool(config.get("fallback_react_on_plan_failure", True))

    def _tool_names(self, intent: IntentContext) -> list[str]:
        all_names = self._tools.list_tool_names()
        if intent.allowed_tools:
            return [n for n in intent.allowed_tools if n in all_names]
        return all_names

    async def run(
        self,
        user_input: str,
        session_id: str,
        mode: str = "react",
        intent: IntentContext | None = None,
    ) -> AgentResponse:
        """执行 Agent 编排：集成记忆、工具、追踪与可选反思。"""
        intent_ctx = intent or IntentContext()
        if intent_ctx.preferred_mode:
            mode = intent_ctx.preferred_mode  # 意图优先

        trace_id = self._tracer.new_trace_id()
        span = self._tracer.start_span(
            "orchestrator.run",
            trace_id,
            attributes={"session_id": session_id, "mode": mode, "intent": intent_ctx.intent},
        )

        self._tracer.log_event(
            trace_id,
            "orchestrator.start",
            {"user_input_len": len(user_input), "mode": mode},
        )

        if self._memory is not None:
            try:
                await self._memory.append_turn(
                    session_id,
                    "user",
                    user_input,
                    {"source": "orchestrator"},
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("写入用户轮次失败: %s", e)

        steps: list[dict[str, Any]] = []
        degraded = False
        error_msg: str | None = None
        result: AgentResult | None = None
        mode_used: OrchestrationMode = "react"

        try:
            if mode == "plan_execute":
                mode_used = "plan_execute"
                result = await self._run_plan_execute(
                    user_input,
                    session_id,
                    intent_ctx,
                    trace_id,
                    steps,
                )
                if not result.success and self._fallback_on_plan_failure:
                    self._tracer.log_event(trace_id, "orchestrator.fallback", {"to": "react"})
                    degraded = True
                    result = await self._run_react(
                        user_input,
                        session_id,
                        intent_ctx,
                        trace_id,
                        steps,
                        suffix="[降级] ",
                    )
                    mode_used = "react"
            else:
                result = await self._run_react(
                    user_input,
                    session_id,
                    intent_ctx,
                    trace_id,
                    steps,
                )

            answer = (result.final_answer if result else "") or ""
            success = bool(result and result.success)

            reflection_report: ReflectionReport | None = None
            if self._enable_reflection and answer:
                try:
                    reflection_report, decision = await self._run_reflection(
                        user_input,
                        answer,
                        trace_id,
                        steps,
                    )
                    if decision.get("suggest_retry"):
                        hint = "；".join(reflection_report.suggestions) or "请补充证据并修正结论"
                        self._tracer.log_event(
                            trace_id,
                            "reflection.retry",
                            {"hint": hint, "quality": reflection_report.quality_score},
                        )
                        retry_result = await self._run_react(
                            user_input,
                            session_id,
                            intent_ctx,
                            trace_id,
                            steps,
                            suffix=f"[反思改进] {hint} ",
                        )
                        if retry_result.success and retry_result.final_answer:
                            result = retry_result
                            answer = retry_result.final_answer
                            success = True
                except Exception as e:  # noqa: BLE001
                    logger.warning("反思阶段失败，已跳过: %s", e)
                    self._tracer.log_event(trace_id, "reflection.skipped", {"error": str(e)})

            resp = AgentResponse(
                answer=answer,
                mode_used=mode_used,
                success=success,
                trace_id=trace_id,
                intent=intent_ctx,
                steps=steps,
                reflection=reflection_report,
                error=result.error if result and not success else None,
                degraded=degraded,
            )
            self._tracer.end_span(span, error=None)
            return resp

        except Exception as e:  # noqa: BLE001
            logger.exception("编排器未捕获异常")
            error_msg = str(e)
            self._tracer.log_event(trace_id, "orchestrator.error", {"error": error_msg})
            self._tracer.end_span(span, error=e)
            return AgentResponse(
                answer="",
                mode_used="react",
                success=False,
                trace_id=trace_id,
                intent=intent_ctx,
                steps=steps,
                error=error_msg,
                degraded=degraded,
            )

    async def _run_react(
        self,
        user_input: str,
        session_id: str,
        intent: IntentContext,
        trace_id: str,
        steps: list[dict[str, Any]],
        suffix: str = "",
    ) -> AgentResult:
        llm = _LLMAdapter(self._model_router.get_llm("react"))
        max_steps = int(self._config.get("react_max_steps", 10))

        async def trace_cb(rec: dict[str, Any]) -> None:
            payload = {"ts": time.time(), **rec}
            steps.append(payload)
            self._tracer.log_event(trace_id, "react.step", payload)

        agent = ReActAgent(
            llm=llm,
            tools=self._tools,
            memory=self._memory,
            max_steps=max_steps,
            session_id=session_id,
        )

        extra_system = str(self._config.get("system_prompt_extra", ""))
        ctx: dict[str, Any] = {
            "session_id": session_id,
            "tool_names": self._tool_names(intent),
            "tool_catalog": getattr(
                self._tools, "get_tools_description", lambda: ""
            )(),
            "trace_callback": trace_cb,
            "extra_system": (
                f"{suffix}{extra_system}"
                f"当前识别意图：{intent.intent}，槽位：{intent.slots}"
            ),
        }

        self._tracer.log_event(trace_id, "react.begin", {})
        result = await agent.run(user_input, ctx)
        self._tracer.log_event(
            trace_id,
            "react.end",
            {"success": result.success, "steps": len(result.steps)},
        )
        return result

    async def _run_plan_execute(
        self,
        user_input: str,
        session_id: str,
        intent: IntentContext,
        trace_id: str,
        steps: list[dict[str, Any]],
    ) -> AgentResult:
        llm = _LLMAdapter(self._model_router.get_llm("planner"))

        async def trace_cb(payload: dict[str, Any]) -> None:
            entry = {"ts": time.time(), **payload}
            steps.append(entry)
            self._tracer.log_event(trace_id, "plan_execute", entry)

        planner = PlannerAgent(
            llm=llm,
            tools=self._tools,
            memory=self._memory,
            max_replan_attempts=int(self._config.get("max_replan_attempts", 2)),
        )

        self._tracer.log_event(trace_id, "planner.begin", {})
        result = await planner.run_with_replan(
            user_input,
            session_id,
            tool_names=self._tool_names(intent),
            trace_callback=trace_cb,
        )
        self._tracer.log_event(
            trace_id,
            "planner.end",
            {"success": result.success, "steps": len(result.steps)},
        )
        return result

    async def _run_reflection(
        self,
        user_query: str,
        answer: str,
        trace_id: str,
        steps: list[dict[str, Any]],
    ) -> tuple[ReflectionReport, dict[str, Any]]:
        llm = _LLMAdapter(self._model_router.get_llm("reflection"))
        agent = ReflectionAgent(
            llm=llm,
            min_quality_to_pass=int(self._config.get("reflection_min_quality", 60)),
        )
        trace_summary = str([s.get("phase") or s.get("subtask_id") for s in steps[-20:]])
        self._tracer.log_event(trace_id, "reflection.begin", {})
        report = await agent.reflect(
            user_query,
            answer,
            evidence_snippets=None,
            trace_summary=trace_summary,
        )
        decision = agent.should_retry_or_warn(report)
        self._tracer.log_event(
            trace_id,
            "reflection.end",
            {
                "quality": report.quality_score,
                "hallucination": report.likely_hallucination,
                "suggest_retry": decision.get("suggest_retry", False),
            },
        )
        return report, decision


# ---------------------------------------------------------------------------
# 简易内存型实现，便于本地测试（可选）
# ---------------------------------------------------------------------------
class InMemoryTracer:
    """内存追踪器实现，用于单测或无基础设施环境。"""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def new_trace_id(self) -> str:
        return str(uuid.uuid4())

    def start_span(
        self,
        name: str,
        trace_id: str,
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {"name": name, "trace_id": trace_id, "attributes": attributes or {}}

    def end_span(self, span: Any, error: BaseException | None = None) -> None:
        self.events.append(
            {
                "type": "end_span",
                "span": span,
                "error": str(error) if error else None,
            }
        )

    def log_event(self, trace_id: str, name: str, payload: dict[str, Any]) -> None:
        self.events.append({"trace_id": trace_id, "name": name, "payload": payload})
