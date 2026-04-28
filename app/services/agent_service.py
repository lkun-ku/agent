"""装配层：把 core 层协议接到基础设施实现，并提供开关式 Agent 服务。"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from loguru import logger

from app.core.agent.orchestrator import AgentOrchestrator, AgentResponse
from app.core.tools.base import BaseTool
from app.core.tools.registry import ToolRegistry
from app.infrastructure.llm.model_router import ModelRouter
from app.infrastructure.trace.tracer import Tracer
from app.models.enums import MessageRole
from app.models.schemas import Message


class _RouterLLM:
    """把 ModelRouter.chat 适配成 orchestrator 期望的 acomplete。"""

    def __init__(self, router: ModelRouter, purpose: str) -> None:
        self._router = router
        self._purpose = purpose

    async def acomplete(self, messages, **kwargs: Any) -> str:
        response = await self._router.chat(messages, **kwargs)
        return str(getattr(response, "content", "") or "")

    async def ainvoke(self, input: Any, **kwargs: Any) -> str:
        """兼容 ShortTermMemory 的摘要接口。"""
        messages = [{"role": "user", "content": input}] if isinstance(input, str) else input
        return await self.acomplete(messages, **kwargs)


class ModelRouterAdapter:
    """core 期望 get_llm(purpose)，infra 提供 chat(messages)。"""

    def __init__(self, router: ModelRouter) -> None:
        self._router = router

    def get_llm(self, purpose: str) -> _RouterLLM:
        return _RouterLLM(self._router, purpose)


class ToolRegistryAdapter:
    """core 期望 list_tool_names / invoke。"""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def list_tool_names(self) -> list[str]:
        return self._registry.list_tool_names()

    def get_tools_description(self) -> str:
        return self._registry.get_tools_description()

    async def invoke(self, name: str, arguments: dict[str, Any]) -> str:
        return await self._registry.invoke(name, arguments)


class TracerAdapter:
    """core 期望 new_trace_id / start_span / end_span / log_event。"""

    def __init__(self, tracer: Tracer) -> None:
        self._tracer = tracer

    def new_trace_id(self) -> str:
        return str(uuid.uuid4())

    def start_span(
        self,
        name: str,
        trace_id: str,
        attributes: dict[str, Any] | None = None,
    ) -> Any:
        return self._tracer.start_child_span(trace_id, name)

    def end_span(self, span: Any, error: BaseException | None = None) -> None:
        self._tracer.end_span(span, error=str(error) if error else None)

    def log_event(self, trace_id: str, name: str, payload: dict[str, Any]) -> None:
        logger.debug("trace={} event={} payload={}", trace_id, name, payload)


class NullMemory:
    """无 Redis/Milvus 时的空记忆，保证装配可运行。"""

    async def get_relevant(self, session_id: str, query: str, limit: int = 8) -> list[str]:
        return []

    async def append_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        return None


class MemoryWritePolicy:
    """规则式长期记忆写入：仅当用户明确表达“要记住”时触发。"""

    TRIGGERS = ("记住", "别忘", "偏好", "我叫", "我的", "以后", "下次")
    QUESTION_MARKERS = ("什么", "吗", "怎么", "如何", "哪", "?", "？")

    def should_store(self, role: str, content: str) -> bool:
        if role != "user":
            return False
        text = content.strip()
        if len(text) < 4:
            return False
        if any(marker in text for marker in self.QUESTION_MARKERS):
            return False
        return any(trigger in text for trigger in self.TRIGGERS)


class MemoryManagerAdapter:
    """把 MemoryManager.get_context/save 适配成 orchestrator 期望的 get_relevant/append_turn。"""

    def __init__(self, manager: Any, policy: MemoryWritePolicy | None = None) -> None:
        self._manager = manager
        self._policy = policy or MemoryWritePolicy()

    async def get_relevant(
        self,
        session_id: str,
        query: str,
        limit: int = 8,
    ) -> list[str]:
        ctx = await self._manager.get_context(session_id, query)
        recent = [m.content for m in ctx.short_term_messages[-limit:]]
        long_term = [item.content for item in ctx.long_term_items[:limit]]
        return recent + long_term

    async def append_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        try:
            role_enum = MessageRole(role)
        except ValueError:
            role_enum = MessageRole.USER
        await self._manager.save(
            session_id,
            Message(role=role_enum, content=content, metadata=metadata or {}),
        )
        if self._policy.should_store(role, content):
            await self._manager.save_long_term(
                session_id,
                content,
                {"source": "auto", "role": role},
            )


async def build_memory(
    model_router: Any,
    *,
    redis_url: str,
    collection_name: str = "agent_memory",
    dim: int = 512,
) -> MemoryManagerAdapter:
    """构建真实短期（Redis）+ 长期（Milvus）记忆；失败由调用方降级。"""
    import redis.asyncio as aioredis
    from pymilvus import Collection

    from app.core.memory.long_term import LongTermMemory
    from app.core.memory.manager import MemoryManager
    from app.core.memory.short_term import ShortTermMemory
    from app.infrastructure.vectordb.milvus_client import MilvusManager
    from app.services.indexing_service import get_embedder

    milvus = MilvusManager()
    await milvus.create_collection(collection_name, dim)
    collection = await asyncio.to_thread(Collection, collection_name)
    await asyncio.to_thread(collection.load)

    embedder = get_embedder()
    embedder.assert_dim(dim)

    redis_client = aioredis.from_url(redis_url, decode_responses=True)
    short_term = ShortTermMemory(redis_client, _RouterLLM(model_router, "memory"))
    long_term = LongTermMemory(collection, embedder)
    # 与 MilvusManager 创建的主键/文本字段对齐
    long_term.pk_field = "id"
    long_term.content_field = "text"
    return MemoryManagerAdapter(MemoryManager(short_term, long_term))


async def build_knowledge_search_tool(model_router: Any) -> BaseTool:
    """构建知识检索工具（内部完成 ModelRouter -> ainvoke 适配）。"""
    from app.services.indexing_service import build_knowledge_tool

    return await build_knowledge_tool(_RouterLLM(model_router, "rag"))


class AgentService:
    """装配后的 Agent 服务：对外只需 run(user_input, session_id)。"""

    def __init__(
        self,
        model_router: Any,
        tools: ToolRegistry,
        tracer: Tracer,
        memory: Any | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        cfg = dict(config or {})
        cfg.setdefault("enable_reflection", True)
        self._orchestrator = AgentOrchestrator(
            config=cfg,
            model_router=ModelRouterAdapter(model_router),
            memory_manager=memory or NullMemory(),
            tool_registry=ToolRegistryAdapter(tools),
            tracer=TracerAdapter(tracer),
        )

    async def run(
        self,
        user_input: str,
        session_id: str = "default",
        mode: str = "react",
    ) -> AgentResponse:
        return await self._orchestrator.run(
            user_input,
            session_id=session_id,
            mode=mode,
        )
