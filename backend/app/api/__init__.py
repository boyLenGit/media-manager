"""API 路由聚合,在 main.py 中统一注册。

鉴权策略:
- /api/health, /api/info, /api/auth/* 公开
- 其余接口需要登录(通过 require_user 依赖)
"""
from fastapi import APIRouter, Depends

from app.api import (
    auth,
    authors,
    downloads,
    files,
    health,
    jellyfin,
    library,
    library_tools,
    media_types,
    playback,
    scan,
    search,
    settings as settings_api,
    stats,
    tags,
    thumbnails,
)
from app.core.deps import require_user

api_router = APIRouter(prefix="/api")

# --- 公开 ---
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
# 缩略图也公开访问 (图片资源不需要鉴权,且 URL 用 media_id 不可枚举出敏感信息)
api_router.include_router(thumbnails.router, prefix="/thumbnails", tags=["thumbnails"])

# --- 需要登录 ---
protected = [Depends(require_user)]
api_router.include_router(stats.router, prefix="/stats", tags=["stats"], dependencies=protected)
api_router.include_router(library.router, prefix="/media", tags=["library"], dependencies=protected)
api_router.include_router(library_tools.router, prefix="/library", tags=["library-tools"], dependencies=protected)
# files 路由内部各端点自己决定鉴权方式 (stream 走签名 token,其他走 require_user)
api_router.include_router(files.router, prefix="/files", tags=["files"])
api_router.include_router(scan.router, prefix="/scan", tags=["scan"], dependencies=protected)
api_router.include_router(search.router, prefix="/search", tags=["search"], dependencies=protected)
api_router.include_router(downloads.router, prefix="/downloads", tags=["downloads"], dependencies=protected)
api_router.include_router(playback.router, prefix="/playback", tags=["playback"], dependencies=protected)
api_router.include_router(jellyfin.router, prefix="/jellyfin", tags=["jellyfin"], dependencies=protected)
api_router.include_router(authors.router, prefix="/authors", tags=["authors"], dependencies=protected)
api_router.include_router(media_types.router, prefix="/media-types", tags=["media-types"], dependencies=protected)
api_router.include_router(tags.router, prefix="/tags", tags=["tags"], dependencies=protected)
api_router.include_router(settings_api.router, prefix="/settings", tags=["settings"], dependencies=protected)
