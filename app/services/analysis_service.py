"""经营分析 Agent：组装 schema / SQL / 计算工具与分析提示词。"""

from __future__ import annotations

from typing import Any

from app.core.agent.orchestrator import AgentResponse
from app.core.tools.builtin.calculator import CalculatorTool
from app.core.tools.builtin.database import DatabaseQueryTool
from app.core.tools.builtin.schema import SchemaInspectTool
from app.core.tools.registry import ToolRegistry
from app.services.agent_service import AgentService

ANALYSIS_SYSTEM_PROMPT = """你是企业经营分析 Agent。必须遵守：
1. 写 SQL 前先调用 schema_inspect 查看表结构，不要假设字段；
2. 只允许只读的 SELECT/WITH，禁止任何写操作；
3. 空结果时调整过滤条件或时间范围，最多重试 2 次；
4. 结论必须包含口径、数字、时间范围；多表查询说明 join 键；
5. 工具报错时改写 SQL，不要把错误原文返回给用户；
6. 信息不足时明确说明，禁止编造。
"""


class AnalysisService:
    """分析场景的薄封装：固定工具集与提示词，复用 AgentService。"""

    def __init__(
        self,
        model_router: Any,
        session_factory: Any,
        tracer: Any,
    ) -> None:
        registry = ToolRegistry()
        registry.register(CalculatorTool())
        registry.register(DatabaseQueryTool(session_factory))
        registry.register(SchemaInspectTool(session_factory))
        self._registry = registry
        self._agent = AgentService(
            model_router=model_router,
            tools=registry,
            tracer=tracer,
            memory=None,
            config={
                "enable_reflection": False,
                "react_max_steps": 8,
                "system_prompt_extra": ANALYSIS_SYSTEM_PROMPT,
            },
        )

    @property
    def tool_names(self) -> list[str]:
        return self._registry.list_tool_names()

    async def run(
        self,
        question: str,
        session_id: str = "analysis",
    ) -> AgentResponse:
        return await self._agent.run(question, session_id=session_id)
