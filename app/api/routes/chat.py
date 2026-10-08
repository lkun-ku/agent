"""对话 API：非流式与流式输出；业务编排在应用服务层。"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any, cast

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from openai import AsyncOpenAI

from app.config import get_settings
from app.core.chat.service import ChatApplicationService
from app.core.intent.recognizer import IntentRecognizer
from app.infrastructure.llm.model_router import build_thinking_extra
from app.infrastructure.trace.tracer import Tracer
from app.models.schemas import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])

_chat_service = ChatApplicationService(Tracer(), IntentRecognizer())


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """非流式对话：HTTP 层只负责协议与错误转换。"""
    trace_id = str(uuid.uuid4())
    span = _chat_service.tracer.start_trace(trace_id, "chat")
    try:
        return await _chat_service.run_chat(request, trace_id=trace_id, span=span)
    except RuntimeError as exc:
        logger.warning("chat 上游不可用: {}", exc)
        raise HTTPException(
            status_code=503,
            detail="模型服务暂时不可用，请稍后重试",
        ) from exc
    except Exception as exc:
        logger.exception("chat 失败: {}", exc)
        raise HTTPException(status_code=500, detail=f"对话失败: {exc!s}") from exc


async def _stream_generator(
    request: ChatRequest,
    trace_id: str,
    conversation_id: str,
) -> AsyncIterator[bytes]:
    """SSE 风格流：每行 ``data: {json}\\n\\n``。"""
    settings = get_settings()
    await _chat_service.persist_trace(trace_id)
    messages: list[dict[str, str]] = [
        m.model_dump(mode="json") for m in request.messages
    ]
    model = request.model or settings.openai_model
    query = request.messages[-1].content if request.messages else ""

    async def persist(content: str, mode: str) -> None:
        await _chat_service.persist_chat(
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

    intent = await _chat_service.intent_recognizer.recognize(query)
    refund_result = await _chat_service.try_refund(query, intent)
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
        yield b"data: " + json.dumps(refund_payload, ensure_ascii=False).encode() + b"\n\n"
        yield b"data: " + json.dumps({"done": True}, ensure_ascii=False).encode() + b"\n\n"
        return

    if not settings.openai_api_key:
        err = json.dumps({"error": "未配置 API Key"}, ensure_ascii=False).encode()
        yield b"data: " + err + b"\n\n"
        return

    rag_response = await _chat_service.try_rag(query, messages)
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

    thinking_params = {
        "extra_body": build_thinking_extra(settings.openai_thinking),
    }
    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_api_base or None,
    )
    try:
        create = cast("Any", client.chat.completions.create)
        stream = await create(
            model=model,
            messages=messages,
            stream=True,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            **thinking_params,
        )
    except Exception as exc:
        error_payload = {"error": f"模型调用失败: {exc!s}", "trace_id": trace_id}
        yield b"data: " + json.dumps(error_payload, ensure_ascii=False).encode() + b"\n\n"
        yield b"data: " + json.dumps({"done": True}, ensure_ascii=False).encode() + b"\n\n"
        return

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


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """流式输出（Server-Sent Events 兼容格式）。"""
    trace_id = str(uuid.uuid4())
    conversation_id = _chat_service.canonical_conversation_id(
        request.conversation_id or trace_id
    )
    span = _chat_service.tracer.start_trace(trace_id, "chat_stream")
    _chat_service.tracer.end_span(span, result={"mode": "stream"})

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
