"""混合意图识别测试：强规则优先 + 语义兜底 + 资金动作闸门。"""

from __future__ import annotations

import pytest

from app.core.intent.recognizer import IntentRecognizer, is_refund_action
from app.core.intent.semantic import (
    _SEMANTIC_EXAMPLES,
    SemanticIntentClassifier,
    SemanticMatch,
    _similarity_to_confidence,
)


class _FakeSemantic:
    def __init__(
        self,
        match: SemanticMatch | None = None,
        error: Exception | None = None,
    ) -> None:
        self.match = match
        self.error = error
        self.calls: list[str] = []

    async def classify(self, query: str) -> SemanticMatch | None:
        self.calls.append(query)
        if self.error is not None:
            raise self.error
        return self.match


@pytest.mark.asyncio
async def test_strong_refund_rule_wins_over_semantic() -> None:
    recognizer = IntentRecognizer()
    recognizer._semantic = _FakeSemantic(
        SemanticMatch(
            intent="问答",
            sub_intent="知识问答",
            confidence=0.95,
            similarity=0.90,
            rationale="fake",
        )
    )

    result = await recognizer.recognize(
        "我要退款，退款单号 RF202611100001"
    )
    assert result.intent == "售后"
    assert result.sub_intent == "退款"
    assert result.source == "rule"
    assert result.slots["refund_id"] == "RF202611100001"
    assert recognizer._semantic.calls == []  # 强规则命中，不调用语义模型


@pytest.mark.asyncio
async def test_semantic_fallback_only_when_rule_confidence_is_low() -> None:
    recognizer = IntentRecognizer()
    recognizer._semantic = _FakeSemantic(
        SemanticMatch(
            intent="售后",
            sub_intent="退款",
            confidence=0.82,
            similarity=0.79,
            rationale="semantic",
        )
    )

    # 不包含退款/退货等强关键词，规则引擎只能给出低置信度。
    query = "上一笔交易的支付有点问题，需要原路处理"
    result = await recognizer.recognize(query)
    assert result.intent == "售后"
    assert result.sub_intent == "退款"
    assert result.source == "semantic"
    assert recognizer._semantic.calls == [query]


@pytest.mark.asyncio
async def test_semantic_failure_falls_back_to_rule() -> None:
    recognizer = IntentRecognizer()
    recognizer._semantic = _FakeSemantic(error=RuntimeError("embedding down"))

    result = await recognizer.recognize("帮我看下这个报告要怎么处理")
    assert result.intent == "问答"
    assert result.source == "fallback"
    assert result.confidence < recognizer.confidence_threshold


@pytest.mark.asyncio
async def test_policy_question_is_not_refund_action() -> None:
    recognizer = IntentRecognizer()
    result = await recognizer.recognize("退货政策是什么")
    assert result.intent == "问答"
    assert result.sub_intent == "政策咨询"
    assert is_refund_action("退货政策是什么") is False


@pytest.mark.asyncio
async def test_database_query_with_refund_word_is_not_action() -> None:
    recognizer = IntentRecognizer()
    result = await recognizer.recognize("查询订单表里的待退款记录")
    assert result.intent == "任务"
    assert result.sub_intent == "数据库"
    assert is_refund_action("查询订单表里的待退款记录") is False


@pytest.mark.asyncio
async def test_refund_process_question_is_not_action() -> None:
    assert is_refund_action("退货流程怎么办理") is False
    recognizer = IntentRecognizer()
    result = await recognizer.recognize("退货流程怎么办理")
    assert result.intent == "问答"


@pytest.mark.asyncio
async def test_low_confidence_generates_clarification() -> None:
    recognizer = IntentRecognizer(semantic_enabled=False)
    result = await recognizer.recognize("我想处理一下")
    message = await recognizer.clarify("我想处理一下", result)
    assert result.confidence < recognizer.confidence_threshold
    assert "不太确定" in message


def test_similarity_confidence_mapping() -> None:
    assert _similarity_to_confidence(0.45) == 0.0
    assert _similarity_to_confidence(0.65) == pytest.approx(0.5714)
    assert _similarity_to_confidence(0.80) == pytest.approx(0.95)
    assert _similarity_to_confidence(0.99) == 0.95


class _FakeEmbedder:
    """按固定向量表模拟本地嵌入模型。"""

    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self.vectors = vectors

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.vectors[text] for text in texts]

    async def aembed_query(self, text: str) -> list[float]:
        return self.vectors.get(text, [0.0, 0.0])


@pytest.mark.asyncio
async def test_semantic_classifier_selects_nearest_label() -> None:
    vectors: dict[str, list[float]] = {}
    refunds = _SEMANTIC_EXAMPLES[("售后", "退款")]
    policies = _SEMANTIC_EXAMPLES[("问答", "政策咨询")]
    refund_vector = [1.0, 0.0]
    policy_vector = [0.0, 1.0]

    for text in refunds:
        vectors[text] = refund_vector
    for text in policies:
        vectors[text] = policy_vector
    # 补齐其他示例，避免批量编码时缺向量。
    for label, examples in _SEMANTIC_EXAMPLES.items():
        for text in examples:
            vectors.setdefault(text, [0.5, 0.5])

    classifier = SemanticIntentClassifier(
        enabled=True,
        min_similarity=0.65,
        embedder=_FakeEmbedder(vectors),
    )
    match = await classifier.classify(refunds[0])
    assert match is not None
    assert (match.intent, match.sub_intent) == ("售后", "退款")

    policy_match = await classifier.classify(policies[0])
    assert policy_match is not None
    assert (policy_match.intent, policy_match.sub_intent) == ("问答", "政策咨询")


@pytest.mark.asyncio
async def test_semantic_classifier_rejects_low_similarity() -> None:
    classifier = SemanticIntentClassifier(
        enabled=True,
        min_similarity=0.65,
        embedder=_FakeEmbedder({}),
    )
    classifier._labels = [("问答", "知识问答")]
    classifier._vectors = [[1.0, 0.0]]
    classifier._ready = True

    match = await classifier.classify("完全无关的输入")
    assert match is None


def test_intent_tree_covers_policy_branch() -> None:
    recognizer = IntentRecognizer()
    # 这个断言确保“政策咨询”在同级同命中数时优先于“知识问答”。
    root, child, confidence, _ = recognizer._score_branch("退款政策是什么")
    assert root == "问答"
    assert child == "政策咨询"
    assert confidence > 0
