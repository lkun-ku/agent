"""应用级枚举定义（Agent、检索、消息与任务状态）。"""

from enum import StrEnum


class AgentMode(StrEnum):
    """Agent 推理模式。"""

    REACT = "react"
    PLAN_EXECUTE = "plan_execute"


class RetrievalMode(StrEnum):
    """检索模式：向量 / 关键词 / 混合。"""

    VECTOR = "vector"
    KEYWORD = "keyword"
    HYBRID = "hybrid"


class MessageRole(StrEnum):
    """对话消息角色。"""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class TaskStatus(StrEnum):
    """子任务或异步任务状态。"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
