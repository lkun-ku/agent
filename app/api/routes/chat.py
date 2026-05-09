"""对话 API：非流式与流式输出。"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import cast

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from app.config import get_settings
from app.core.intent.recognizer import IntentRecognizer
from app.core.tools.builtin.calculator import CalculatorTool
from app.core.tools.registry import ToolRegistry
from app.infrastructure.llm.model_router import ModelConfig, ModelRouter
from app.infrastructure.trace.tracer import Tracer
from app.models.schemas import ChatRequest, ChatResponse
from app.services.agent_service import (
    AgentService,
    build_knowledge_search_tool,
    build_memory,
)

router = APIRouter(tags=["chat"])

_tracer = Tracer()
_intent = IntentRecognizer()


@lru_cache(maxsize=1)
def get_model_router() -> ModelRouter:
    """进程级单例：保证熔断计数与连接池跨请求复用。"""
    settings = get_settings()
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="未配置 OPENAI_API_KEY，无法调用模型")
    cfg = ModelConfig(
        model_id=settings.openai_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_api_base or None,
        priority=0,
        weight=1.0,
    )
    state_store = None
    try:
        from app.infrastructure.llm.circuit_breaker import RedisStateStore

        state_store = RedisStateStore(settings.redis_url)
    except Exception as exc:  # noqa: BLE001
        logger.warning("熔断共享状态不可用，使用内存状态: {}", exc)
    return ModelRouter([cfg], state_store=state_store)


_agent_service: AgentService | None = None
_agent_lock = asyncio.Lock()
_trace_tasks: set[asyncio.Task[None]] = set()


def _schedule_trace_persist(trace_id: str) -> None:
    """把 trace 落库 / OTLP 导出放到后台，失败不影响响应。"""
    from app.infrastructure.database.session import async_session_factory
    from app.services.trace_service import TraceLogWriter

    record = _tracer.get_trace(trace_id)
    if record is None:
        return
    settings = get_settings()
    if async_session_factory is None and not settings.otlp_endpoint:
        return

    async def _run() -> None:
        if async_session_factory is not None:
            try:
                rows = await TraceLogWriter().persist(record)
                logger.debug("trace {} 落库 {} 行", trace_id, rows)
            except Exception as exc:  # noqa: BLE001
                logger.warning("trace 落库失败: {}", exc)
        if settings.trace_jsonl_path:
            try:
                exported = _tracer.export_jsonl(trace_id, settings.trace_jsonl_path)
                logger.debug("trace {} JSONL 导出 {}", trace_id, exported)
            except Exception as exc:  # noqa: BLE001
                logger.warning("trace JSONL 导出失败: {}", exc)
        if settings.otlp_endpoint:
            try:
                ok = await _tracer.export_otlp(trace_id, settings.otlp_endpoint)
                logger.debug("trace {} OTLP 导出 {}", trace_id, ok)
            except Exception as exc:  # noqa: BLE001
                logger.warning("OTLP 导出失败: {}", exc)

    task = asyncio.create_task(_run())
    _trace_tasks.add(task)
    task.add_done_callback(_trace_tasks.discard)


async def get_agent_service() -> AgentService:
    """装配后的 Agent 服务（进程级单例；记忆不可用时降级）。"""
    global _agent_service
    if _agent_service is not None:
        return _agent_service

    async with _agent_lock:
        if _agent_service is None:
            settings = get_settings()
            registry = ToolRegistry()
            registry.register(CalculatorTool())
            try:
                registry.register(await build_knowledge_search_tool(get_model_router()))
            except Exception as exc:  # noqa: BLE001
                logger.warning("知识库工具初始化失败，跳过: {}", exc)
            memory = None
            try:
                memory = await build_memory(
                    get_model_router(),
                    redis_url=settings.redis_url,
                )
                logger.info("短期/长期记忆已接入")
            except Exception as exc:  # noqa: BLE001
                logger.warning("记忆初始化失败，降级为 NullMemory: {}", exc)

            _agent_service = AgentService(
                model_router=get_model_router(),
                tools=registry,
                tracer=_tracer,
                memory=memory,
                config={"enable_reflection": True, "react_max_steps": 6},
            )
    return _agent_service


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """非流式对话：经意图识别与链路追踪后返回完整回复。"""
    trace_id = str(uuid.uuid4())
    span = _tracer.start_trace(trace_id, "chat")

    try:
        user_text = request.messages[-1].content if request.messages else ""
        intent = await _intent.recognize(user_text)
        clarify = await _intent.clarify(user_text, intent)
        logger.info(
            "意图 intent={} conf={} sub={}",
            intent.intent,
            intent.confidence,
            intent.sub_intent,
        )

        settings = get_settings()
        if settings.agent_enabled:
            agent_resp = await (await get_agent_service()).run(
                user_text,
                session_id=request.conversation_id or "default",
                mode="react",
            )
            if not agent_resp.success or not agent_resp.answer.strip():
                error = agent_resp.error or "Agent 未产生有效回答"
                logger.warning("Agent 调用失败: {}", error)
                _tracer.end_span(span, error=error)
                _schedule_trace_persist(trace_id)
                raise HTTPException(
                    status_code=502,
                    detail=f"Agent 生成失败: {error}",
                )
            _tracer.end_span(
                span,
                result={"mode": agent_resp.mode_used, "success": agent_resp.success},
            )
            _schedule_trace_persist(trace_id)
            return ChatResponse(
                id=str(uuid.uuid4()),
                model=settings.openai_model,
                content=agent_resp.answer,
                trace_id=agent_resp.trace_id or trace_id,
                usage=None,
            )

        router_llm = get_model_router()
        messages = [m.model_dump() for m in request.messages]
        if clarify and intent.confidence < _intent.confidence_threshold:
            messages.append(
                {
                    "role": "system",
                    "content": f"（系统提示：{clarify}）",
                }
            )

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
        _schedule_trace_persist(trace_id)

        return ChatResponse(
            id=str(uuid.uuid4()),
            model=resp.model_id,
            content=resp.content,
            trace_id=trace_id,
            usage=resp.usage,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("chat 失败: {}", exc)
        _tracer.end_span(span, error=str(exc))
        _schedule_trace_persist(trace_id)
        raise HTTPException(status_code=500, detail=f"对话失败: {exc!s}") from exc


@lru_cache(maxsize=1)
def get_openai_client() -> AsyncOpenAI:
    """流式接口复用同一个客户端，连接池不随请求重建。"""
    settings = get_settings()
    return AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_api_base or None,
        timeout=60.0,
        max_retries=2,
    )


async def _stream_generator(
    request: ChatRequest,
    trace_id: str,
) -> AsyncIterator[bytes]:
    """SSE 风格流：每行 data: {json}\\n\\n。"""
    settings = get_settings()
    if not settings.openai_api_key:
        error_payload = json.dumps(
            {"error": "未配置 API Key"}, ensure_ascii=False
        ).encode()
        yield b"data: " + error_payload + b"\n\n"
        return

    client = get_openai_client()
    messages = [
        cast(ChatCompletionMessageParam, cast(object, m.model_dump()))
        for m in request.messages
    ]
    model = request.model or settings.openai_model

    try:
        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                payload = {"content": delta, "trace_id": trace_id}
                yield b"data: " + json.dumps(payload, ensure_ascii=False).encode() + b"\n\n"
        yield b"data: " + json.dumps({"done": True}, ensure_ascii=False).encode() + b"\n\n"
    except Exception as exc:
        logger.exception("chat_stream 失败: {}", exc)
        yield b"data: " + json.dumps({"error": str(exc)}, ensure_ascii=False).encode() + b"\n\n"
    finally:
        _schedule_trace_persist(trace_id)


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """流式输出（Server-Sent Events 兼容格式）。"""
    trace_id = str(uuid.uuid4())
    span = _tracer.start_trace(trace_id, "chat_stream")
    _tracer.end_span(span, result={"mode": "stream"})

    return StreamingResponse(
        _stream_generator(request, trace_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Trace-Id": trace_id,
        },
    )
