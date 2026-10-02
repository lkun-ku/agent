"""记忆相关回归测试：Milvus 表达式转义与会话隔离。"""

from __future__ import annotations

from typing import Any

from app.core.memory.long_term import LongTermMemory
from app.models.schemas import Message, MessageRole


class _FakeEmbed:
    def embed_query(self, text: str) -> list[float]:
        return [0.1, 0.2]


class _CapturingCollection:
    """记录 search/delete 时传入的表达式，模拟按会话过滤。"""

    def __init__(self, by_session: dict[str, list[dict[str, Any]]]) -> None:
        self.by_session = by_session
        self.last_expr: str | None = None

    def insert(self, data: Any, **kwargs: Any) -> None:  # pragma: no cover - 未使用
        return None

    def flush(self, **kwargs: Any) -> None:  # pragma: no cover - 未使用
        return None

    def delete(self, expr: str, **kwargs: Any) -> None:
        self.last_expr = expr

    def search(self, data, anns_field, param, limit, expr=None, output_fields=None, **kwargs):
        self.last_expr = expr
        session = (expr or "").split('"')[1] if expr and '"' in expr else ""
        rows = self.by_session.get(session, [])
        hits = []
        for row in rows[:limit]:
            hit = type("Hit", (), {})()
            hit.entity = row
            hit.distance = 0.1
            hit.id = row["pk"]
            hits.append(hit)
        return [hits]


def test_escape_literal_escapes_double_quote_and_backslash() -> None:
    assert LongTermMemory._escape_literal('a"b') == 'a\\"b'
    assert LongTermMemory._escape_literal("a\\b") == "a\\\\b"


async def test_recall_expression_is_escaped() -> None:
    coll = _CapturingCollection({"sess-A": [{"pk": "m1", "content": "记忆A", "meta": "{}"}]})
    ltm = LongTermMemory(coll, _FakeEmbed())
    evil_session = 'sess-A" or pk like "%'
    items = await ltm.recall("query", evil_session, top_k=5)
    # 表达式中的引号必须被转义，不能闭合成跨会话条件
    assert coll.last_expr is not None
    assert 'sess-A\\" or pk like \\"%' in coll.last_expr
    assert items == []


async def test_recall_returns_only_target_session() -> None:
    coll = _CapturingCollection(
        {
            "sess-A": [{"pk": "m1", "content": "A 的记忆", "meta": "{}"}],
            "sess-B": [{"pk": "m2", "content": "B 的记忆", "meta": "{}"}],
        }
    )
    ltm = LongTermMemory(coll, _FakeEmbed())
    items = await ltm.recall("query", "sess-A", top_k=5)
    assert [i.content for i in items] == ["A 的记忆"]


def test_message_role_is_str_enum() -> None:
    """StrEnum 改造后，序列化仍应得到纯字符串值。"""
    msg = Message(role=MessageRole.USER, content="hi")
    assert msg.role == "user"
    assert msg.role.value == "user"
