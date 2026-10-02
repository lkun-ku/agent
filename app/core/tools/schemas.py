"""Agent 工具层统一结果契约。

工具不允许直接返回任意 dict；HTTP、AgentOrchestrator、测试和前端都依赖稳定字段。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolHandoff(BaseModel):
    """工具请求人工/外部系统转交的稳定结构。"""

    to_human: bool = False
    queue: str = ""
    queue_label: str = ""


class ToolResult(BaseModel):
    """所有 Agent 工具的统一出参。"""

    status: str = Field(description="工具业务状态，例如 ok / need_info / error")
    action: str = Field(description="工具动作或错误码")
    reply: str = Field(description="面向用户的回复")
    handoff: ToolHandoff = Field(default_factory=ToolHandoff)
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="工具附加结构化数据；具体 schema 由子类型定义",
    )


class RefundToolResult(ToolResult):
    """退款工具稳定出参；字段与 RefundService 的 CaseView 对齐。"""

    request_id: str = ""
    case_id: str = ""
    refund_id: str = ""
    order_id: str = ""
    action_label: str = ""
    amount: float = Field(default=0.0, ge=0)
    reason: str = ""
    reason_label: str = ""
    queue: str = ""
    queue_label: str = ""
    pending: dict[str, Any] | None = None


__all__ = ["RefundToolResult", "ToolHandoff", "ToolResult"]
