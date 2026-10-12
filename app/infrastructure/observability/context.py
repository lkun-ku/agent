"""可观测性上下文：请求级 trace / conversation 绑定。"""

from __future__ import annotations

from contextvars import ContextVar, Token

trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)
conversation_id_var: ContextVar[str | None] = ContextVar(
    "conversation_id", default=None
)


def set_trace_context(
    trace_id: str | None,
    conversation_id: str | None = None,
) -> tuple[Token[str | None], Token[str | None]]:
    """绑定当前请求上下文；返回 token 供 finally 重置。"""
    return (
        trace_id_var.set(trace_id),
        conversation_id_var.set(conversation_id),
    )


def reset_trace_context(
    tokens: tuple[Token[str | None], Token[str | None]],
) -> None:
    """重置上下文，避免后台任务继承上一个请求。"""
    trace_id_var.reset(tokens[0])
    conversation_id_var.reset(tokens[1])


def current_trace_id() -> str | None:
    return trace_id_var.get()


def current_conversation_id() -> str | None:
    return conversation_id_var.get()


__all__ = [
    "conversation_id_var",
    "current_conversation_id",
    "current_trace_id",
    "reset_trace_context",
    "set_trace_context",
    "trace_id_var",
]
