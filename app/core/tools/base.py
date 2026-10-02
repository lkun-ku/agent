"""工具基类：统一 name、description、parameters、execute 与生命周期接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel

from app.core.tools.schemas import ToolResult


class ToolParameter(BaseModel):
    """JSON Schema 风格的单个参数描述。"""

    name: str
    type: Literal["string", "number", "integer", "boolean", "object", "array"] = "string"
    description: str = ""
    required: bool = True


class BaseTool(ABC):
    """所有 Agent 工具的抽象基类。"""

    name: str = "base_tool"
    description: str = "基础工具"

    def __init__(self) -> None:
        self.parameters: list[ToolParameter] = []

    def schema_parameters(self) -> dict[str, Any]:
        """导出为 OpenAI tools 风格的 parameters 结构。"""
        properties: dict[str, Any] = {}
        required: list[str] = []
        for p in self.parameters:
            properties[p.name] = {"type": p.type, "description": p.description}
            if p.required:
                required.append(p.name)
        return {"type": "object", "properties": properties, "required": required}

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """执行工具逻辑；子类必须返回类型化结果。"""

    def close(self) -> None:
        """释放工具持有的资源；默认无资源。"""
        return None
