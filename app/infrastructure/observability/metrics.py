"""Prometheus 指标：统一命名空间与主链路指标。"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUESTS = Counter(
    "enterprise_agent_http_requests_total",
    "Total HTTP requests by method, route and status.",
    ["method", "route", "status"],
)
HTTP_DURATION = Histogram(
    "enterprise_agent_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ["method", "route"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)
HTTP_ERRORS = Counter(
    "enterprise_agent_http_errors_total",
    "Total unhandled HTTP handler errors by route.",
    ["route"],
)
CHAT_REQUESTS = Counter(
    "enterprise_agent_chat_requests_total",
    "Total chat requests by route and mode.",
    ["route", "mode"],
)
CHAT_DURATION = Histogram(
    "enterprise_agent_chat_request_duration_seconds",
    "Chat request duration in seconds.",
    ["route"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
)
RAG_CACHE_REQUESTS = Counter(
    "enterprise_agent_rag_cache_requests_total",
    "RAG cache lookups by result.",
    ["result"],
)
DEPENDENCY_ERRORS = Counter(
    "enterprise_agent_dependency_errors_total",
    "Dependency errors by component and operation.",
    ["component", "operation"],
)
ACTIVE_TOOL_INVOCATIONS = Gauge(
    "enterprise_agent_tool_invocations_active",
    "Active agent tool invocations.",
)
TOOL_DURATION = Histogram(
    "enterprise_agent_tool_duration_seconds",
    "Agent tool duration in seconds.",
    ["tool"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)

__all__ = [
    "ACTIVE_TOOL_INVOCATIONS",
    "CHAT_DURATION",
    "CHAT_REQUESTS",
    "DEPENDENCY_ERRORS",
    "HTTP_DURATION",
    "HTTP_ERRORS",
    "HTTP_REQUESTS",
    "RAG_CACHE_REQUESTS",
    "TOOL_DURATION",
]
