"""对话应用服务：统一意图路由、缓存、持久化与编排。"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, cast

from loguru import logger

from app.config import get_settings
from app.core.agent import AgentOrchestrator, IntentContext
from app.core.agent.adapters import (
    RegistryToolInvoker,
    RouterLLMProvider,
    TraceAdapter,
)
from app.core.intent.recognizer import IntentRecognizer, IntentResult, is_refund_action
from app.core.rag.pipeline import get_pipeline
from app.core.tools import get_tool_registry
from app.core.tools.schemas import RefundToolResult
from app.infrastructure.cache.factory import get_redis_cache
from app.infrastructure.database import session as database_session
from app.infrastructure.database.repositories import (
    ConversationMemory,
    ConversationRepository,
    TraceRepository,
)
from app.infrastructure.llm.factory import get_model_router
from app.infrastructure.llm.model_router import ModelRouter
from app.infrastructure.observability.context import set_trace_context
from app.infrastructure.observability.metrics import (
    CHAT_DURATION,
    CHAT_REQUESTS,
    RAG_CACHE_REQUESTS,
)
from app.infrastructure.trace.tracer import Tracer, TraceSpan
from app.models.schemas import ChatRequest, ChatResponse, Citation, RAGResponse
from app.shared.hashing import sha256_text, uuid4_str
from app.shared.jsonx import dumps_json, loads_json

if TYPE_CHECKING:
    from app.core.tools.refund import RefundTool


class ChatApplicationService:
    """单轮对话的应用层门面。"""

    def __init__(
        self,
        tracer: Tracer,
        intent_recognizer: IntentRecognizer,
    ) -> None:
        self._tracer = tracer
        self._intent = intent_recognizer

    @property
    def tracer(self) -> Tracer:
        return self._tracer

    @property
    def intent_recognizer(self) -> IntentRecognizer:
        return self._intent

    async def run_chat(
        self,
        request: ChatRequest,
        *,
        trace_id: str,
        span: Any,
    ) -> ChatResponse:
        conversation_id = self.canonical_conversation_id(
            request.conversation_id or trace_id
        )
        started_at = time.perf_counter()
        context_tokens = set_trace_context(trace_id, conversation_id)

        async def finish(response: ChatResponse, mode: str) -> ChatResponse:
            await self.persist_chat(
                conversation_id,
                user_text,
                response,
                mode=mode,
            )
            await self.persist_trace(trace_id)
            CHAT_REQUESTS.labels(route="chat", mode=mode).inc()
            CHAT_DURATION.labels(route="chat").observe(
                time.perf_counter() - started_at
            )
            return response

        user_text = request.messages[-1].content if request.messages else ""
        try:
            intent = await self._intent.recognize(user_text)
            clarify = await self._intent.clarify(user_text, intent)
            logger.info(
                "意图 intent={} conf={} sub={}",
                intent.intent,
                intent.confidence,
                intent.sub_intent,
            )

            messages = [m.model_dump() for m in request.messages]
            if clarify and intent.confidence < self._intent.confidence_threshold:
                messages.append({"role": "system", "content": f"（系统提示：{clarify}）"})

            refund_result = await self._tracked_call(
                trace_id,
                "refund_route",
                lambda: self.try_refund(user_text, intent),
            )
            if refund_result is not None:
                self._tracer.end_span(
                    span,
                    result={"mode": "refund_tool", "action": refund_result.action},
                )
                return await finish(
                    self._refund_response(trace_id, conversation_id, refund_result),
                    "refund_tool",
                )

            agent_response = await self._tracked_call(
                trace_id,
                "agent_orchestrator",
                lambda: self.try_orchestrator(
                    user_text,
                    intent,
                    trace_id,
                    conversation_id,
                ),
            )
            if agent_response is not None:
                self._tracer.end_span(span, result={"mode": "agent_orchestrator"})
                return await finish(agent_response, "agent_orchestrator")

            cache_key = self.rag_cache_key(request)
            cached = await self._tracked_call(
                trace_id,
                "rag_cache_get",
                lambda: self.get_cached_rag(cache_key),
            )
            if cached is not None:
                RAG_CACHE_REQUESTS.labels(result="hit").inc()
                self._tracer.end_span(span, result={"mode": "rag_cache"})
                return await finish(
                    self._cached_response(cached, trace_id, conversation_id),
                    "rag_cache",
                )
            RAG_CACHE_REQUESTS.labels(result="miss").inc()

            rag_response = await self._tracked_call(
                trace_id,
                "rag_pipeline",
                lambda: self.try_rag(user_text, messages),
            )
            if rag_response is not None:
                await self.store_cached_rag(cache_key, rag_response)
                self._tracer.end_span(
                    span,
                    result={
                        "model": rag_response.model,
                        "mode": "rag",
                        "citations": len(rag_response.citations),
                    },
                )
                return await finish(
                    self._rag_response(trace_id, conversation_id, rag_response),
                    "rag",
                )

            response = await self._tracked_call(
                trace_id,
                "plain_llm",
                lambda: self._plain_llm_response(
                    request,
                    messages,
                    trace_id,
                    conversation_id,
                ),
            )
            self._tracer.end_span(
                span,
                result={"model": response.model, "usage": response.usage},
            )
            return await finish(response, "llm")
        finally:
            from app.infrastructure.observability.context import reset_trace_context

            reset_trace_context(context_tokens)
            trace_record = self._tracer.get_trace(trace_id)
            if trace_record is not None:
                root_span = trace_record.spans[0]
                if root_span.end_time is None:
                    self._tracer.end_span(
                        root_span,
                        result={"status": "completed"},
                    )

    async def _tracked_call(
        self,
        trace_id: str,
        operation: str,
        func: Callable[[], Awaitable[Any]],
    ) -> Any:
        """在子 Span 中执行一次异步调用，记录耗时与错误。"""
        span: TraceSpan = self._tracer.start_child_span(trace_id, operation)
        try:
            result = await func()
        except Exception as exc:
            self._tracer.end_span(span, error=str(exc))
            raise
        self._tracer.end_span(span, result={"status": "ok"})
        return result

    def _response(
        self,
        *,
        model: str,
        content: str,
        trace_id: str,
        conversation_id: str,
        usage: dict[str, Any] | None = None,
        citations: list[Citation] | None = None,
        tool: str | None = None,
        tool_result: RefundToolResult | None = None,
        cache_hit: bool = False,
    ) -> ChatResponse:
        return ChatResponse(
            id=uuid4_str(),
            model=model,
            content=content,
            trace_id=trace_id,
            conversation_id=conversation_id,
            usage=usage,
            citations=citations,
            tool=tool,
            tool_result=tool_result,
            cache_hit=cache_hit,
        )

    @staticmethod
    def canonical_conversation_id(value: str) -> str:
        from app.infrastructure.database.repositories import (
            canonical_conversation_id,
        )

        return canonical_conversation_id(value)

    async def try_refund(
        self,
        user_text: str,
        intent: IntentResult,
    ) -> RefundToolResult | None:
        """退款意图直接走 Agent 工具；政策咨询仍走 RAG。"""
        settings = get_settings()
        if (
            not settings.refund_enabled
            or intent.intent != "售后"
            or not is_refund_action(user_text)
        ):
            return None
        try:
            tool = get_tool_registry().get_tool("refund")
        except KeyError:
            logger.warning("退款意图已识别，但工具未注册")
            return None
        return await cast("RefundTool", tool).execute(
            order_id=str(intent.slots.get("order_id", "")),
            refund_id=str(intent.slots.get("refund_id", "")),
            reason=user_text,
        )

    def _refund_response(
        self,
        trace_id: str,
        conversation_id: str,
        result: RefundToolResult,
    ) -> ChatResponse:
        return self._response(
            model="tool:refund",
            content=result.reply,
            trace_id=trace_id,
            conversation_id=conversation_id,
            tool="refund",
            tool_result=result,
        )

    def _session_factory(self) -> Any:
        return database_session.async_session_factory

    async def persist_chat(
        self,
        conversation_id: str,
        user_text: str,
        response: ChatResponse,
        *,
        mode: str,
    ) -> None:
        """持久化一轮问答；失败只记录日志，不影响对话可用性。"""
        settings = get_settings()
        factory = self._session_factory()
        if not settings.conversation_persistence_enabled or factory is None:
            return
        metadata: dict[str, Any] = {
            "trace_id": response.trace_id,
            "mode": mode,
            "model": response.model,
        }
        if response.tool:
            metadata["tool"] = response.tool
        if response.tool_result:
            metadata["tool_action"] = response.tool_result.action
        try:
            await ConversationRepository(factory).append_turn(
                conversation_id,
                user_text,
                response.content,
                assistant_metadata=metadata,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("会话持久化失败 conversation={}: {}", conversation_id, exc)

    async def persist_trace(self, trace_id: str) -> None:
        """把内存 Span 同步到 TraceLog；失败不影响响应。"""
        settings = get_settings()
        factory = self._session_factory()
        if not settings.trace_persistence_enabled or factory is None:
            return
        try:
            record = self._tracer.get_trace(trace_id)
            if record is not None:
                await TraceRepository(factory).save_record(record)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Trace 持久化失败 trace={}: {}", trace_id, exc)

    def rag_cache_key(self, request: ChatRequest) -> str:
        settings = get_settings()
        model = request.model or settings.openai_model
        payload = {
            "messages": [m.model_dump(mode="json") for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "model": model,
            "collection": settings.rag_collection_name,
            "retrieval_mode": settings.rag_retrieval_mode,
        }
        raw = dumps_json(payload, sort_keys=True)
        digest = sha256_text(raw)
        return f"rag:v1:{settings.rag_collection_name}:{digest}"

    async def get_cached_rag(self, key: str) -> dict[str, Any] | None:
        settings = get_settings()
        if not settings.rag_cache_enabled:
            return None
        try:
            raw = await get_redis_cache().get(key)
            return loads_json(raw) if raw else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("读取 RAG 缓存失败: {}", exc)
            return None

    async def store_cached_rag(self, key: str, response: RAGResponse) -> None:
        settings = get_settings()
        if not settings.rag_cache_enabled:
            return
        try:
            payload = {
                "content": response.answer,
                "model": response.model,
                "citations": [c.model_dump(mode="json") for c in response.citations],
            }
            await get_redis_cache().set(
                key,
                dumps_json(payload),
                ttl=settings.rag_cache_ttl_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("写入 RAG 缓存失败: {}", exc)

    async def try_orchestrator(
        self,
        user_text: str,
        intent: IntentResult,
        trace_id: str,
        conversation_id: str,
    ) -> ChatResponse | None:
        """任务类意图走通用 ReAct；退款仍保持确定性短路。"""
        settings = get_settings()
        if (
            not settings.agent_orchestrator_enabled
            or intent.intent != "任务"
            or not settings.openai_api_key
        ):
            return None

        registry = get_tool_registry()
        allowed_tools = [name for name in registry.list_tool_names() if name != "refund"]
        config = {"react_max_steps": settings.agent_max_steps}
        memory = None
        factory = self._session_factory()
        if settings.conversation_persistence_enabled and factory is not None:
            memory = ConversationMemory(ConversationRepository(factory))

        orchestrator = AgentOrchestrator(
            config,
            RouterLLMProvider(self.build_router()),
            memory,
            RegistryToolInvoker(registry),
            TraceAdapter(self._tracer, trace_id),
        )
        agent_result = await orchestrator.run(
            user_text,
            conversation_id,
            intent=IntentContext(
                intent=intent.intent,
                confidence=intent.confidence,
                slots=intent.slots,
                allowed_tools=allowed_tools,
            ),
        )
        if not agent_result.success or not agent_result.answer:
            logger.warning("通用 Agent 执行失败，回退常规链路: {}", agent_result.error)
            return None
        return self._response(
            model=f"agent:{agent_result.mode_used}",
            content=agent_result.answer,
            trace_id=trace_id,
            conversation_id=conversation_id,
        )

    def build_router(self) -> ModelRouter:
        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError("未配置 OPENAI_API_KEY，无法调用模型")
        return get_model_router()

    async def try_rag(
        self,
        query: str,
        messages: list[dict[str, Any]],
    ) -> RAGResponse | None:
        """检索命中时走 RAG；任何环节失败都降级为普通对话。"""
        settings = get_settings()
        if not settings.rag_enabled or not query.strip():
            return None
        try:
            pipeline = await get_pipeline()
            if pipeline is None:
                return None
            contexts = await pipeline.retrieve(query, top_k=settings.rag_top_k)
            if not contexts:
                logger.info("知识库未命中，使用普通对话")
                return None
            logger.info("知识库命中 {} 条上下文", len(contexts))
            return await pipeline.answer(query, messages[:-1], contexts)
        except Exception as exc:  # noqa: BLE001
            logger.warning("RAG 链路失败，降级为普通对话: {}", exc)
            return None

    def _cached_response(
        self,
        cached: dict[str, Any],
        trace_id: str,
        conversation_id: str,
    ) -> ChatResponse:
        citations = [
            Citation.model_validate(item)
            for item in (cached.get("citations") or [])
        ]
        return self._response(
            model=str(cached.get("model") or get_settings().openai_model),
            content=str(cached.get("content") or ""),
            trace_id=trace_id,
            conversation_id=conversation_id,
            citations=citations or None,
            cache_hit=True,
        )

    def _rag_response(
        self,
        trace_id: str,
        conversation_id: str,
        response: RAGResponse,
    ) -> ChatResponse:
        return self._response(
            model=response.model or get_settings().openai_model,
            content=response.answer,
            trace_id=trace_id,
            conversation_id=conversation_id,
            citations=response.citations or None,
        )

    async def _plain_llm_response(
        self,
        request: ChatRequest,
        messages: list[dict[str, Any]],
        trace_id: str,
        conversation_id: str,
    ) -> ChatResponse:
        router_llm = self.build_router()
        response = await router_llm.chat(
            messages,
            model_preference=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        return self._response(
            model=response.model_id,
            content=response.content,
            trace_id=trace_id,
            conversation_id=conversation_id,
            usage=response.usage,
        )


__all__ = ["ChatApplicationService"]
