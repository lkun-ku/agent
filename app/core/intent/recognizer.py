"""意图识别：强规则优先 + 语义近邻兜底 + 置信度澄清。"""

from __future__ import annotations

import re
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from app.core.intent.semantic import SemanticIntentClassifier


class IntentResult(BaseModel):
    """意图识别结果。"""

    intent: str = Field(description="主意图标签")
    confidence: float = Field(ge=0.0, le=1.0, description="置信度 0~1")
    slots: dict[str, Any] = Field(default_factory=dict, description="槽位信息")
    sub_intent: str | None = Field(default=None, description="子意图（树形第二层）")
    rationale: str = Field(default="", description="简要理由（可给模型或日志用）")
    source: str = Field(
        default="rule",
        description="识别来源：rule / semantic / fallback",
    )


# 简易树形意图：根 -> 子意图。强特征仍走规则，弱特征才进入语义兜底。
_INTENT_TREE: dict[str, dict[str, list[str]]] = {
    "问答": {
        "政策咨询": ["政策", "规则", "流程", "条件", "怎么退", "如何退", "能不能退", "多久"],
        "知识问答": ["什么", "为什么", "如何", "解释", "含义"],
        "闲聊": ["你好", "谢谢", "再见", "聊天", "随便", "说说"],
    },
    "任务": {
        "搜索": ["搜索", "查一下", "帮我找", "search"],
        "计算": ["计算", "等于", "算", "加", "减"],
        "数据库": ["sql", "查询", "表", "统计"],
    },
    "售后": {
        "退款": ["退款", "退货", "退钱", "售后", "仅退款", "退货退款", "refund"],
    },
    "文档": {
        "上传": ["上传", "上传文档", "pdf", "加入知识库", "导入资料"],
        "总结": ["总结", "摘要", "概括"],
    },
}

_REFUND_RE = re.compile(
    r"(退款|退货|退钱|售后|仅退款|退货退款|refund|退回来|退回去|退掉)",
    re.I,
)
_POLICY_RE = re.compile(r"(政策|规则|流程|条件|多久|怎么退|如何退|能不能退)")
_REFUND_ACTION_RE = re.compile(
    r"(我要|我想|申请|办理|帮我|提交|发起|处理|退掉|退回|refund)",
    re.I,
)
_ORDER_RE = re.compile(
    r"(?:订单号|订单|order[_\s-]?id|order)\s*[:：]?\s*([A-Za-z0-9][A-Za-z0-9_-]{5,})",
    re.I,
)
_REFUND_ID_RE = re.compile(
    r"(?:退款单号|退款单|refund[_\s-]?id)\s*[:：]?\s*([A-Za-z0-9][A-Za-z0-9_-]{5,})",
    re.I,
)


def is_refund_action(query: str) -> bool:
    """判断是否为可执行的退款动作，而不是政策/流程咨询。

    该函数是资金动作的确定性闸门：即使语义分类器认为 intent=售后，
    这里不通过就不会调用退款工具。
    """
    if not _REFUND_RE.search(query):
        return False
    if _POLICY_RE.search(query):
        # “退货流程怎么办理”虽有办理/动作词，但主体仍是政策咨询。
        if not _REFUND_ACTION_RE.search(query):
            return False
        if re.search(r"(流程|步骤|怎么|如何|多久|条件|规则|政策)", query, re.I):
            return False
    # 显式提供退款单号视为继续办理；普通“查询待退款记录”不触发退款工具。
    if _REFUND_ID_RE.search(query):
        return True
    return bool(_REFUND_ACTION_RE.search(query))


class IntentRecognizer:
    """意图识别器：树形规则 + 语义兜底 + 置信度澄清。"""

    def __init__(
        self,
        confidence_threshold: float = 0.55,
        *,
        semantic_enabled: bool | None = None,
        semantic_min_similarity: float | None = None,
    ) -> None:
        enabled, min_similarity = _read_semantic_settings(
            semantic_enabled,
            semantic_min_similarity,
        )
        self._threshold = confidence_threshold
        self._semantic = SemanticIntentClassifier(
            enabled=enabled,
            min_similarity=min_similarity,
        )

    @property
    def confidence_threshold(self) -> float:
        """置信度阈值：低于该值时建议澄清。"""
        return self._threshold

    @property
    def semantic_classifier(self) -> SemanticIntentClassifier:
        """暴露语义分类器，便于测试与影子评估。"""
        return self._semantic

    def _score_branch(self, query: str) -> tuple[str, str | None, float, str]:
        """返回 (根意图, 子意图, 置信度, 理由)。"""
        q = query.strip().lower()
        best_root = "未知"
        best_child: str | None = None
        best_hits = 0

        for root, children in _INTENT_TREE.items():
            for child, kws in children.items():
                hits = sum(1 for kw in kws if kw.lower() in q)
                if hits > best_hits:
                    best_hits = hits
                    best_root = root
                    best_child = child

        if best_hits == 0:
            # 无关键词命中：根据问号弱推断，等待语义分类器兜底。
            conf = 0.35 if "?" in q or "？" in q else 0.25
            return "问答", "知识问答", conf, "规则未命中关键词，弱规则推断"

        conf = min(0.95, 0.45 + 0.12 * best_hits)
        rationale = f"关键词命中 {best_hits} 次，归类为 {best_root}/{best_child}"
        return best_root, best_child, conf, rationale

    async def recognize(
        self, query: str, context: dict[str, Any] | None = None
    ) -> IntentResult:
        """识别用户意图；context 可包含历史轮次等（当前规则引擎未使用）。"""
        _ = context
        text = query.strip()

        # 资金动作永远优先走强规则；语义分类器不直接决定是否调用退款工具。
        if is_refund_action(text):
            intent = "售后"
            sub_intent: str | None = "退款"
            confidence = 0.98
            rationale = "强规则命中可执行退款动作"
            source = "rule"
        else:
            intent, sub_intent, confidence, rationale = self._score_branch(text)
            source = "rule" if confidence >= self._threshold else "fallback"

            # 规则完全未命中时才加载语义模型；避免给每次请求都增加嵌入开销。
            if confidence < self._threshold:
                try:
                    match = await self._semantic.classify(text)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("意图语义兜底失败，继续使用规则结果: {}", exc)
                    match = None
                if match is not None and match.confidence >= self._threshold:
                    intent = match.intent
                    sub_intent = match.sub_intent
                    confidence = match.confidence
                    rationale = match.rationale
                    source = "semantic"

        slots = self._extract_slots(text, intent)
        result = IntentResult(
            intent=intent,
            confidence=confidence,
            slots=slots,
            sub_intent=sub_intent,
            rationale=rationale,
            source=source,
        )
        logger.info(
            "意图识别 query_preview={} -> {} / {} conf={} source={}",
            text[:100],
            result.intent,
            result.sub_intent,
            result.confidence,
            result.source,
        )
        return result

    @staticmethod
    def _extract_slots(query: str, intent: str) -> dict[str, Any]:
        """从 query 中抽取工具调用所需槽位。"""
        slots: dict[str, Any] = {}
        nums = re.findall(r"[-+]?\d*\.\d+|\d+", query)
        if nums:
            slots["numbers"] = nums[:5]
        order = _ORDER_RE.search(query)
        if order:
            slots["order_id"] = order.group(1)
        refund = _REFUND_ID_RE.search(query)
        if refund:
            slots["refund_id"] = refund.group(1)
        if intent == "售后":
            slots["raw_query"] = query
        return slots

    async def clarify(self, query: str, intent_result: IntentResult) -> str:
        """置信度不足时生成澄清提示语。"""
        if intent_result.confidence >= self._threshold:
            return ""

        return (
            "我不太确定您的具体需求。"
            f"您是想了解「{intent_result.intent}」相关"
            f"（当前置信度 {intent_result.confidence:.2f}）吗？"
            "请补充场景、对象或期望的输出格式（例如：只要结论 / 需要步骤）。"
        )


def _read_semantic_settings(
    enabled_override: bool | None,
    similarity_override: float | None,
) -> tuple[bool, float]:
    """读取语义分类配置；测试或异常配置时提供安全默认值。"""
    enabled = True
    min_similarity = 0.65
    try:
        from app.config import get_settings

        settings = get_settings()
        enabled = bool(settings.intent_semantic_enabled)
        min_similarity = float(settings.intent_semantic_min_similarity)
    except Exception:  # noqa: BLE001
        logger.warning("意图语义配置读取失败，使用默认值")

    if enabled_override is not None:
        enabled = enabled_override
    if similarity_override is not None:
        min_similarity = similarity_override
    return enabled, min_similarity
