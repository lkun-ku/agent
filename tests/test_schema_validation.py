"""API/领域输入模型的边界与类型约束。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.schemas import (
    ChatMessage,
    ChatRequest,
    Citation,
    RetrievalResult,
)


def test_chat_rejects_empty_and_blank_content() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(messages=[{"role": "user", "content": ""}])
    with pytest.raises(ValidationError):
        ChatRequest(messages=[{"role": "user", "content": "   "}])


def test_chat_rejects_unknown_or_tool_role() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(messages=[{"role": "admin", "content": "hi"}])
    with pytest.raises(ValidationError):
        ChatRequest(messages=[{"role": "tool", "content": "{}"}])


def test_chat_rejects_invalid_numeric_bounds() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(
            messages=[{"role": "user", "content": "hi"}],
            temperature=2.1,
        )
    with pytest.raises(ValidationError):
        ChatRequest(
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=0,
        )


def test_chat_rejects_too_many_messages() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(
            messages=[
                {"role": "user", "content": f"message-{i}"}
                for i in range(101)
            ]
        )


def test_chat_accepts_enum_role() -> None:
    message = ChatMessage(role="user", content="hello")
    assert message.role.value == "user"


def test_citation_and_retrieval_constraints() -> None:
    with pytest.raises(ValidationError):
        Citation(index=0, result_id="r1", snippet="x")
    with pytest.raises(ValidationError):
        Citation(index=1, result_id="", snippet="x")
    with pytest.raises(ValidationError):
        RetrievalResult(id="r1", content="", score=0.1)
    with pytest.raises(ValidationError):
        RetrievalResult(id="r1", content="x", score=-0.1)
