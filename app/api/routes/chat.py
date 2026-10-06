"""对话 API：非流式与流式输出。"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, cast

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from openai import AsyncOpenAI

from app.config import get_settings
from app.core.agent import AgentOrchestrator, IntentContext
from app.core.agent.adapters import (
    RegistryToolInvoker,
    RouterLLMProvider,
    TraceAdapter,
)
from app.core.intent.recognizer import (
    IntentRecognizer,
    IntentResult,
    is_refund_action,
)
from app.core.rag.pipeline import get_pipeline
from app.core.tools import get_tool_registry
from app.core.tools.schemas import RefundToolResult
from app.infrastructure.cache.factory import get_redis_cache
from app.infrastructure.database import session as database_session
from app.infrastructure.database.repositories import (
    ConversationMemory,
    ConversationRepository,
    TraceRepository,
    canonical_conversation_id,
)
from app.infrastructure.llm.factory import get_model_router
from app.infrastructure.llm.model_router import ModelRouter, build_thinking_extra
from app.infrastructure.trace.tracer import Tracer
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    Citation,
    RAGResponse,
)

if TYPE_CHECKING:
    from app.core.tools.refund import RefundTool

router = APIRouter(tags=["chat"])

_tracer = Tracer()
_intent = IntentRecognizer()


async def _try_refund(user_text: str, intent: IntentResult) -> RefundToolResult | None:
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


def _tool_response(
    trace_id: str,
    conversation_id: str,
    result: RefundToolResult,
) -> ChatResponse:
    return ChatResponse(
        id=str(uuid.uuid4()),
        model="tool:refund",
        content=result.reply,
        trace_id=trace_id,
        conversation_id=conversation_id,
        tool="refund",
        tool_result=result,
    )


def _session_factory() -> Any:
    return database_session.async_session_factory


async def _persist_chat(
    conversation_id: str,
    user_text: str,
    response: ChatResponse,
    *,
    mode: str,
) -> None:
    """持久化一轮问答；失败只记录日志，不影响对话可用性。"""
    settings = get_settings()
    factory = _session_factory()
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


async def _persist_trace(trace_id: str) -> None:
    """把内存 Span 同步到 TraceLog；失败不影响响应。"""
    settings = get_settings()
    factory = _session_factory()
    if not settings.trace_persistence_enabled or factory is None:
        return
    try:
        record = _tracer.get_trace(trace_id)
        if record is not None:
            await TraceRepository(factory).save_record(record)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Trace 持久化失败 trace={}: {}", trace_id, exc)


def _rag_cache_key(request: ChatRequest) -> str:
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
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"rag:v1:{settings.rag_collection_name}:{digest}"


async def _get_cached_rag(key: str) -> dict[str, Any] | None:
    settings = get_settings()
    if not settings.rag_cache_enabled:
        return None
    try:
        raw = await get_redis_cache().get(key)
        return json.loads(raw) if raw else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("读取 RAG 缓存失败: {}", exc)
        return None


async def _store_cached_rag(key: str, response: RAGResponse) -> None:
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
            json.dumps(payload, ensure_ascii=False),
            ttl=settings.rag_cache_ttl_seconds,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("写入 RAG 缓存失败: {}", exc)


async def _try_orchestrator(
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
    config = {
        "react_max_steps": settings.agent_max_steps,
        "enable_reflection": False,
        "fallback_react_on_plan_failure": True,
    }
    memory = None
    factory = _session_factory()
    if settings.conversation_persistence_enabled and factory is not None:
        memory = ConversationMemory(
            ConversationRepository(factory),
            write_turns=False,
        )

    orchestrator = AgentOrchestrator(
        config,
        RouterLLMProvider(_build_router()),
        memory,
        RegistryToolInvoker(registry),
        TraceAdapter(_tracer, trace_id),
    )
    agent_result = await orchestrator.run(
        user_text,
        conversation_id,
        mode="react",
        intent=IntentContext(
            intent=intent.intent,
            confidence=intent.confidence,
            slots=intent.slots,
            allowed_tools=allowed_tools,
        ),
    )
    if not agent_result.success or not agent_result.answer:
        logger.warning(
            "通用 Agent 执行失败，回退常规链路: {}",
            agent_result.error,
        )
        return None
    return ChatResponse(
        id=str(uuid.uuid4()),
        model=f"agent:{agent_result.mode_used}",
        content=agent_result.answer,
        trace_id=trace_id,
        conversation_id=conversation_id,
    )


def _thinking_params() -> dict[str, Any]:
    """思考模式开关（流式路径直接调用 SDK，需自行透传）。"""
    return {"extra_body": build_thinking_extra(get_settings().openai_thinking)}


def _build_router() -> ModelRouter:
    """获取进程级模型路由器，保持连接池与熔断器状态。"""
    settings = get_settings()
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="未配置 OPENAI_API_KEY，无法调用模型")
    return get_model_router()


async def _try_rag(
    query: str,
    messages: list[dict[str, Any]],
) -> RAGResponse | None:
    """检索命中时走 RAG；任何环节失败都降级为普通对话，不影响可用性。"""
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


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """非流式对话：意图路由、缓存、持久化与链路追踪。"""
    trace_id = str(uuid.uuid4())
    conversation_id = canonical_conversation_id(request.conversation_id or trace_id)
    span = _tracer.start_trace(trace_id, "chat")

    async def finish(response: ChatResponse, mode: str) -> ChatResponse:
        await _persist_chat(conversation_id, _last_user_text, response, mode=mode)
        await _persist_trace(trace_id)
        return response

    try:
        _last_user_text = request.messages[-1].content if request.messages else ""
        intent = await _intent.recognize(_last_user_text)
        clarify = await _intent.clarify(_last_user_text, intent)
        logger.info(
            "意图 intent={} conf={} sub={}",
            intent.intent,
            intent.confidence,
            intent.sub_intent,
        )

        messages = [m.model_dump() for m in request.messages]
        if clarify and intent.confidence < _intent.confidence_threshold:
            messages.append(
                {
                    "role": "system",
                    "content": f"（系统提示：{clarify}）",
                }
            )

        refund_result = await _try_refund(_last_user_text, intent)
        if refund_result is not None:
            _tracer.end_span(
                span,
                result={
                    "mode": "refund_tool",
                    "action": refund_result.action,
                },
            )
            response = _tool_response(trace_id, conversation_id, refund_result)
            return await finish(response, "refund_tool")

        agent_response = await _try_orchestrator(
            _last_user_text,
            intent,
            trace_id,
            conversation_id,
        )
        if agent_response is not None:
            _tracer.end_span(
                span,
                result={"mode": "agent_orchestrator"},
            )
            return await finish(agent_response, "agent_orchestrator")

        cache_key = _rag_cache_key(request)
        cached = await _get_cached_rag(cache_key)
        if cached is not None:
            _tracer.end_span(
                span,
                result={"mode": "rag_cache"},
            )
            response = ChatResponse(
                id=str(uuid.uuid4()),
                model=str(cached.get("model") or get_settings().openai_model),
                content=str(cached.get("content") or ""),
                trace_id=trace_id,
                conversation_id=conversation_id,
                citations=[
                    Citation.model_validate(item)
                    for item in (cached.get("citations") or [])
                ]
                or None,
                cache_hit=True,
            )
            return await finish(response, "rag_cache")

        router_llm = _build_router()
        rag_response = await _try_rag(_last_user_text, messages)
        if rag_response is not None:
            await _store_cached_rag(cache_key, rag_response)
            _tracer.end_span(
                span,
                result={
                    "model": rag_response.model,
                    "mode": "rag",
                    "citations": len(rag_response.citations),
                },
            )
            response = ChatResponse(
                id=str(uuid.uuid4()),
                model=rag_response.model or get_settings().openai_model,
                content=rag_response.answer,
                trace_id=trace_id,
                conversation_id=conversation_id,
                citations=rag_response.citations or None,
            )
            return await finish(response, "rag")

        resp = await router_llm.chat(
            messages,
            model_preference=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        _tracer.end_span(
            span,
            result={"model": resp.model_id, "usage": resp.usage},
        )

        response = ChatResponse(
            id=str(uuid.uuid4()),
            model=resp.model_id,
            content=resp.content,
            trace_id=trace_id,
            conversation_id=conversation_id,
            usage=resp.usage,
        )
        return await finish(response, "llm")
    except HTTPException:
        await _persist_trace(trace_id)
        raise
    except RuntimeError as exc:
        # 模型/外部依赖不可用属于可恢复的上游故障，返回 503 而不是 500。
        logger.warning("chat 上游不可用: {}", exc)
        _tracer.end_span(span, error=str(exc))
        await _persist_trace(trace_id)
        raise HTTPException(
            status_code=503,
            detail="模型服务暂时不可用，请稍后重试",
        ) from exc
    except Exception as exc:
        logger.exception("chat 失败: {}", exc)
        _tracer.end_span(span, error=str(exc))
        await _persist_trace(trace_id)
        raise HTTPException(status_code=500, detail=f"对话失败: {exc!s}") from exc


async def _stream_generator(
    request: ChatRequest,
    trace_id: str,
    conversation_id: str,
) -> AsyncIterator[bytes]:
    """SSE 风格流：每行 data: {json}\\n\\n。"""
    settings = get_settings()
    await _persist_trace(trace_id)
    messages: Any = [m.model_dump() for m in request.messages]
    model = request.model or settings.openai_model
    query = request.messages[-1].content if request.messages else ""

    async def persist(content: str, mode: str) -> None:
        await _persist_chat(
            conversation_id,
            query,
            ChatResponse(
                id=str(uuid.uuid4()),
                model=mode,
                content=content,
                trace_id=trace_id,
                conversation_id=conversation_id,
            ),
            mode=mode,
        )

    intent = await _intent.recognize(query)
    refund_result = await _try_refund(query, intent)
    if refund_result is not None:
        refund_payload: dict[str, Any] = {
            "content": refund_result.reply,
            "trace_id": trace_id,
            "conversation_id": conversation_id,
            "model": "tool:refund",
            "tool": "refund",
            "tool_result": refund_result.model_dump(mode="json"),
        }
        await persist(refund_result.reply, "refund_tool")
        yield b"data: " + json.dumps(
            refund_payload, ensure_ascii=False
        ).encode() + b"\n\n"
        yield b"data: " + json.dumps({"done": True}, ensure_ascii=False).encode() + b"\n\n"
        return

    if not settings.openai_api_key:
        err = json.dumps({"error": "未配置 API Key"}, ensure_ascii=False).encode()
        yield b"data: " + err + b"\n\n"
        return

    # 命中知识库时整段返回（保留 citations），否则回落到原生流式
    rag_response = await _try_rag(query, messages)
    if rag_response is not None:
        rag_payload: dict[str, Any] = {
            "content": rag_response.answer,
            "trace_id": trace_id,
            "conversation_id": conversation_id,
            "model": rag_response.model,
            "citations": [c.model_dump(mode="json") for c in rag_response.citations],
        }
        await persist(rag_response.answer, "rag")
        yield b"data: " + json.dumps(rag_payload, ensure_ascii=False).encode() + b"\n\n"
        yield b"data: " + json.dumps({"done": True}, ensure_ascii=False).encode() + b"\n\n"
        return

    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_api_base or None,
    )

    try:
        stream: Any = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=True,
            **_thinking_params(),
        )
        full_content_parts: list[str] = []
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                full_content_parts.append(delta)
                payload = {"content": delta, "trace_id": trace_id}
                yield b"data: " + json.dumps(payload, ensure_ascii=False).encode() + b"\n\n"
        full_content = "".join(full_content_parts)
        if full_content:
            await persist(full_content, "llm_stream")
        yield b"data: " + json.dumps({"done": True}, ensure_ascii=False).encode() + b"\n\n"
    except Exception as exc:
        logger.exception("chat_stream 失败: {}", exc)
        yield b"data: " + json.dumps({"error": str(exc)}, ensure_ascii=False).encode() + b"\n\n"


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """流式输出（Server-Sent Events 兼容格式）。"""
    trace_id = str(uuid.uuid4())
    conversation_id = canonical_conversation_id(request.conversation_id or trace_id)
    span = _tracer.start_trace(trace_id, "chat_stream")
    _tracer.end_span(span, result={"mode": "stream"})

    return StreamingResponse(
        _stream_generator(request, trace_id, conversation_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Trace-Id": trace_id,
            "X-Conversation-Id": conversation_id,
        },
    )
