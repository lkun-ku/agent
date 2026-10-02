"""工具组装：Agent 核心只依赖这里拿到默认工具集。"""

from __future__ import annotations

from app.config import get_settings
from app.core.tools.registry import ToolRegistry

_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """懒加载默认工具；退款工具通过统一配置开关注册。"""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
        if get_settings().refund_enabled:
            from app.core.tools.refund import RefundTool

            _registry.register(RefundTool())
    return _registry


def reset_tool_registry() -> None:
    """应用关闭/测试隔离时释放工具与连接池。"""
    global _registry
    if _registry is not None:
        _registry.close()
        _registry = None
