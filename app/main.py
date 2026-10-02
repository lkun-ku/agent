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

from fastapi import FastAPI
from loguru import logger

from app.api.routes import chat, document, health, web
from app.cli import main
from app.config import get_settings
from app.core.tools import get_tool_registry
from app.core.tools.factory import reset_tool_registry
from app.infrastructure.cache.factory import close_redis_cache
from app.infrastructure.database.session import configure_session, init_engine


def _configure_logging(level: str) -> None:
    """按 LOG_LEVEL 初始化 loguru，未配置时默认 INFO。"""
    logger.remove()
    _ = logger.add(sys.stderr, level=(level or "INFO").upper())


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    _configure_logging(settings.log_level)
    logger.info("启动 {} ({})", settings.app_name, settings.app_env)
    engine = init_engine(settings.database_url)
    app.state.session_factory = configure_session(engine)
    app.state.engine = engine

    sync_task = None
    if settings.knowledge_autoscan and settings.rag_enabled:
        sync_task = asyncio.create_task(_sync_knowledge_on_startup())
        app.state.knowledge_sync_task = sync_task

    tool_registry = get_tool_registry()
    app.state.tool_registry = tool_registry
    logger.info("Agent 工具: {}", tool_registry.list_tool_names())

    yield
    if sync_task is not None:
        sync_task.cancel()
    reset_tool_registry()
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
    return application


app = create_app()

__all__ = ["app", "create_app", "lifespan", "main"]


if __name__ == "__main__":
    raise SystemExit(main() or 0)
