"""FastAPI 入口。

启动顺序:
1. 加载配置
2. 配置日志
3. 跑数据库迁移
4. 注册路由 / 中间件 / 静态文件
5. 启动调度器(后续)
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import api_router
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.migrate import run_migrations
from app.services import ffprobe_service
from app.tasks import download_sync, scan_worker

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    settings = get_settings()
    setup_logging(settings.app_debug)
    logger.info("Starting %s (debug=%s)", settings.app_name, settings.app_debug)
    run_migrations()
    ffprobe_service.check_ffprobe()  # 不阻塞启动,只打日志
    scan_worker.start_worker()
    download_sync.start_worker()
    yield
    await scan_worker.stop_worker()
    await download_sync.stop_worker()
    logger.info("Shutting down")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API
    app.include_router(api_router)

    # 前端静态资源(生产模式)
    static_dir = Path(settings.static_dir).resolve()
    if static_dir.exists():
        # 静态资源 (assets/) 走 StaticFiles
        assets_dir = static_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str):  # noqa: ARG001
            """Vue Router history 模式回退到 index.html。"""
            index_file = static_dir / "index.html"
            if index_file.exists():
                return FileResponse(index_file)
            return {"detail": "frontend not built"}
    else:
        logger.warning(
            "Static dir not found: %s (run `npm run build` in frontend/)",
            static_dir,
        )

    return app


app = create_app()
