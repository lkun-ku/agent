"""FastAPI 应用入口：生命周期内初始化异步数据库引擎。

命令行入口统一在 :mod:`app.cli`（``python main.py --help`` 查看全部子命令）。
"""

import asyncio
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

# 支持 `python app/main.py` 直接运行：把项目根目录加入 sys.path，
# 使 `app.*` 绝对导入可用（`python -m app.main` 时无需此步）。
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request, Response
from loguru import logger

from app.api.routes import chat, document, health, web
from app.cli import main
from app.config import get_settings
from app.core.tools import get_tool_registry
from app.core.tools.factory import reset_tool_registry
from app.infrastructure.cache.factory import close_redis_cache
from app.infrastructure.database.repositories import (
    ObservabilityRetentionService,
)
from app.infrastructure.database.session import configure_session, init_engine
from app.infrastructure.llm.factory import reset_model_router
from app.infrastructure.observability.context import (
    reset_trace_context,
    set_trace_context,
)
from app.infrastructure.observability.metrics import (
    HTTP_DURATION,
    HTTP_ERRORS,
    HTTP_REQUESTS,
)


def _configure_logging(level: str, *, json_logs: bool = False) -> None:
    """按 LOG_LEVEL 初始化 loguru；结构化模式供采集器使用。"""
    logger.remove()

    def _patch(record: Any) -> None:
        from app.infrastructure.observability.context import (
            current_conversation_id,
            current_trace_id,
        )

        record["extra"]["trace_id"] = current_trace_id()
        record["extra"]["conversation_id"] = current_conversation_id()

    logger.configure(patcher=_patch)
    _ = logger.add(
        sys.stderr,
        level=(level or "INFO").upper(),
        serialize=json_logs,
        backtrace=False,
        diagnose=False,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    _configure_logging(settings.log_level, json_logs=settings.log_json)
    logger.info("启动 {} ({})", settings.app_name, settings.app_env)
    engine = init_engine(
        settings.database_url,
        connect_timeout=settings.database_connect_timeout,
        command_timeout=settings.database_command_timeout,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
    )
    app.state.session_factory = configure_session(engine)
    app.state.engine = engine

    sync_task = None
    if settings.knowledge_autoscan and settings.rag_enabled:
        sync_task = asyncio.create_task(_sync_knowledge_on_startup())
        app.state.knowledge_sync_task = sync_task

    tool_registry = get_tool_registry()
    app.state.tool_registry = tool_registry
    logger.info("Agent 工具: {}", tool_registry.list_tool_names())

    retention_service = ObservabilityRetentionService(app.state.session_factory)
    try:
        retention = await retention_service.cleanup(
            trace_retention_days=settings.trace_log_retention_days,
            conversation_retention_days=settings.conversation_log_retention_days,
        )
        if retention["trace_logs"] or retention["messages"]:
            logger.info("可观测性数据清理完成: {}", retention)
    except Exception as exc:
        logger.warning("可观测性数据清理失败（不影响启动）: {}", exc)

    yield
    if sync_task is not None:
        sync_task.cancel()
    reset_tool_registry()
    reset_model_router()
    await close_redis_cache()
    await engine.dispose()
    logger.info("关闭 {}", settings.app_name)


async def _sync_knowledge_on_startup() -> None:
    """后台增量同步知识库目录（无变化时只做哈希比对，秒级完成）。"""
    from app.core.rag.ingest import sync_knowledge_dir

    try:
        report = await sync_knowledge_dir()
        if report.errors:
            logger.warning(
                "知识库目录同步有错误：{}（新增 {} 更新 {} 删除 {}）",
                report.summary(),
                len(report.added),
                len(report.updated),
                len(report.deleted),
            )
        else:
            logger.info(
                "知识库目录同步完成：{}（新增 {} 更新 {} 删除 {}）",
                report.summary(),
                len(report.added),
                len(report.updated),
                len(report.deleted),
            )
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("知识库目录同步失败（不影响服务启动）: {}", exc)


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
        # 默认的 Swagger UI / ReDoc 依赖外网 CDN，离线环境会白屏；
        # 改由 app/api/routes/web.py 提供自包含的 /docs 与 /redoc
        docs_url=None,
        redoc_url=None,
    )
    application.include_router(health.router, prefix=settings.api_prefix)
    application.include_router(chat.router, prefix=settings.api_prefix)
    application.include_router(document.router, prefix=settings.api_prefix)
    # 根路径页面（首页 / 聊天演示）不挂 API 前缀
    application.include_router(web.router)

    @application.middleware("http")
    async def observe_http(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        path = request.url.path
        if path == f"{settings.api_prefix}/metrics":
            return await call_next(request)

        trace_id = request.headers.get("x-trace-id") or str(uuid.uuid4())
        conversation_id = request.headers.get("x-conversation-id")
        tokens = set_trace_context(trace_id, conversation_id)
        started_at = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
        except Exception:
            HTTP_ERRORS.labels(route=path).inc()
            raise
        finally:
            HTTP_DURATION.labels(method=request.method, route=path).observe(
                time.perf_counter() - started_at
            )
            reset_trace_context(tokens)

        HTTP_REQUESTS.labels(
            method=request.method,
            route=path,
            status=str(response.status_code),
        ).inc()
        if "x-trace-id" not in response.headers:
            response.headers["x-trace-id"] = trace_id
        if conversation_id and "x-conversation-id" not in response.headers:
            response.headers["x-conversation-id"] = conversation_id
        return response

    return application


app = create_app()

__all__ = ["app", "create_app", "lifespan", "main"]


if __name__ == "__main__":
    raise SystemExit(main() or 0)
