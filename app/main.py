"""FastAPI 应用入口：生命周期内初始化异步数据库引擎。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from app.api.routes import analysis, chat, document, health
from app.config import get_settings
from app.infrastructure.database.models import Base
from app.infrastructure.database.session import configure_session, init_engine


async def _ensure_tables(engine) -> None:
    """启动期确保表存在；数据库不可用时降级为告警，不阻断启动。"""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("数据库表检查完成")
    except Exception as exc:  # noqa: BLE001
        logger.warning("建表跳过（数据库不可用）: {}", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("启动 {} ({})", settings.app_name, settings.app_env)
    engine = init_engine(settings.database_url)
    configure_session(engine)
    await _ensure_tables(engine)
    app.state.engine = engine
    yield
    await engine.dispose()
    logger.info("关闭 {}", settings.app_name)


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
    )
    application.include_router(health.router, prefix=settings.api_prefix)
    application.include_router(chat.router, prefix=settings.api_prefix)
    application.include_router(document.router, prefix=settings.api_prefix)
    application.include_router(analysis.router, prefix=settings.api_prefix)
    return application


app = create_app()
