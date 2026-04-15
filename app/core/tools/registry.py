"""工具注册中心：集中管理可用工具并生成 Prompt 描述。"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from app.core.tools.base import BaseTool


class ToolRegistry:
    """工具注册中心：管理所有可用工具。"""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """注册工具；同名覆盖并记录日志。"""
        if tool.name in self._tools:
            logger.warning("工具 [{}] 已存在，将被覆盖", tool.name)
        self._tools[tool.name] = tool
        logger.info("已注册工具: {}", tool.name)

    def get_tool(self, name: str) -> BaseTool:
        """按名称获取工具。"""
        if name not in self._tools:
            raise KeyError(f"未注册的工具: {name}")
        return self._tools[name]

    def get_all_tools(self) -> list[BaseTool]:
        """返回全部工具列表。"""
        return list(self._tools.values())

    def get_tools_description(self) -> str:
        """生成所有工具的自然语言描述（用于 System Prompt）。"""
        lines: list[str] = []
        for t in self._tools.values():
            params = ", ".join(f"{p.name}: {p.type}" for p in t.parameters) or "无"
            lines.append(f"- {t.name}: {t.description}（参数: {params}）")
        return "\n".join(lines) if lines else "（当前无可用工具）"

    def list_tool_names(self) -> list[str]:
        """返回全部工具名（供 Agent 层白名单与目录使用）。"""
        return list(self._tools.keys())

    async def invoke(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        """执行工具，永不抛异常：所有失败都转成字符串 Observation。"""
        tool = self._tools.get(name)
        if tool is None:
            return f"错误：未注册的工具 [{name}]。可用：{self.list_tool_names()}"

        args = arguments or {}
        missing = [p.name for p in tool.parameters if p.required and p.name not in args]
        if missing:
            return (
                f"错误：缺少必填参数 {missing}。"
                f"该工具的参数：{json.dumps(tool.schema_parameters(), ensure_ascii=False)}"
            )

        try:
            result = await tool.execute(**args)
        except (TypeError, ValueError) as exc:
            return (
                f"错误：参数或取值不合法（{exc}）。"
                f"正确参数：{json.dumps(tool.schema_parameters(), ensure_ascii=False)}"
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("工具执行失败: {}", name)
            return f"工具执行异常: {type(exc).__name__}: {exc}"

        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False, default=str)
