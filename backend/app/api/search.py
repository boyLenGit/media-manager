"""搜索接口。

外部搜索:并发查询所有启用的 resource_source,聚合结果 + 去重提示。
本地搜索:基于 FTS5 查 media_search_fts。
"""
import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session, select

from app.db.session import get_session
from app.models import ResourceSource
from app.providers.search.base import SearchHit
from app.providers.search.factory import create_provider, parse_source_config
from app.services.duplicate_service import detect_search_result_duplicate

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# 资源源 CRUD
# ============================================================
class ResourceSourceIn(BaseModel):
    name: str
    source_type: str = "torznab"
    base_url: str | None = None
    enabled: bool = True
    auth_config: str | None = None
    rate_limit_config: str | None = None
    remark: str | None = None


@router.get("/sources")
def list_sources(session: Session = Depends(get_session)) -> list[ResourceSource]:
    return session.exec(select(ResourceSource).order_by(ResourceSource.id)).all()  # type: ignore[union-attr]


@router.post("/sources", status_code=201)
def create_source(
    payload: ResourceSourceIn, session: Session = Depends(get_session)
) -> ResourceSource:
    obj = ResourceSource(**payload.model_dump())
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


@router.patch("/sources/{source_id}")
def update_source(
    source_id: int, payload: ResourceSourceIn, session: Session = Depends(get_session)
) -> ResourceSource:
    obj = session.get(ResourceSource, source_id)
    if not obj:
        raise HTTPException(status_code=404)
    for k, v in payload.model_dump().items():
        setattr(obj, k, v)
    obj.updated_at = datetime.utcnow()
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(source_id: int, session: Session = Depends(get_session)) -> None:
    obj = session.get(ResourceSource, source_id)
    if not obj:
        raise HTTPException(status_code=404)
    session.delete(obj)
    session.commit()


@router.post("/sources/{source_id}/test")
async def test_source(
    source_id: int, session: Session = Depends(get_session)
) -> dict:
    src = session.get(ResourceSource, source_id)
    if not src:
        raise HTTPException(status_code=404)
    cfg = parse_source_config(src)
    provider = create_provider(src.source_type, cfg)
    if not provider:
        return {"ok": False, "error": "unknown_provider_type"}
    try:
        ok = await provider.health_check()
        return {"ok": ok}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


# ============================================================
# 聚合搜索
# ============================================================
class SearchHitOut(BaseModel):
    title: str
    source_id: int
    source_name: str
    magnet_uri: str | None = None
    info_hash: str | None = None
    size_bytes: int | None = None
    publish_time: datetime | None = None
    source_url: str | None = None
    seeders: int | None = None
    leechers: int | None = None
    duplicate: dict | None = None  # 由后端计算


@router.get("")
async def search(
    q: str = Query(..., min_length=1),
    limit_per_source: int = 50,
    session: Session = Depends(get_session),
) -> dict:
    sources = session.exec(
        select(ResourceSource).where(ResourceSource.enabled == True)  # noqa: E712
    ).all()

    if not sources:
        return {"q": q, "hits": [], "errors": [{"detail": "no_enabled_source"}]}

    async def _query_one(src: ResourceSource) -> tuple[ResourceSource, list[SearchHit] | Exception]:
        cfg = parse_source_config(src)
        provider = create_provider(src.source_type, cfg)
        if not provider:
            return src, []
        try:
            return src, await provider.search(q, limit=limit_per_source)
        except Exception as e:  # noqa: BLE001
            return src, e

    results = await asyncio.gather(*(_query_one(s) for s in sources))

    hits_out: list[SearchHitOut] = []
    errors: list[dict] = []

    for src, ret in results:
        if isinstance(ret, Exception):
            errors.append({"source": src.name, "error": str(ret)})
            continue
        for h in ret:
            dup = detect_search_result_duplicate(
                session,
                title=h.title,
                info_hash=h.info_hash,
                magnet_uri=h.magnet_uri,
                size_bytes=h.size_bytes,
            )
            hits_out.append(
                SearchHitOut(
                    title=h.title,
                    source_id=src.id,  # type: ignore[arg-type]
                    source_name=src.name,
                    magnet_uri=h.magnet_uri,
                    info_hash=h.info_hash,
                    size_bytes=h.size_bytes,
                    publish_time=h.publish_time,
                    source_url=h.source_url,
                    seeders=h.seeders,
                    leechers=h.leechers,
                    duplicate=(
                        {
                            "level": dup.level,
                            "reason": dup.reason,
                            "matched_media_id": dup.matched_media_id,
                            "score": dup.score,
                        }
                        if dup.level != "none"
                        else None
                    ),
                )
            )

    # 排序:种子数降序 → 发布时间降序
    hits_out.sort(
        key=lambda h: (
            -(h.seeders or 0),
            -(h.publish_time.timestamp() if h.publish_time else 0),
        )
    )

    return {"q": q, "hits": hits_out, "errors": errors}


# ============================================================
# 本地资源全文搜索 (FTS5)
# ============================================================
@router.get("/local")
def search_local(
    q: str = Query(..., min_length=1),
    limit: int = 50,
    session: Session = Depends(get_session),
) -> dict:
    """走 FTS5 索引搜索本地资源库。

    支持 title / author / tag / filename / path 全字段搜索。
    """
    # FTS5 query 需要转义双引号
    safe_q = q.replace('"', '""')
    fts_query = f'"{safe_q}"*'  # 前缀匹配
    sql = text(
        """
        SELECT media_item_id, title, author_name, tag_names
        FROM media_search_fts
        WHERE media_search_fts MATCH :q
        LIMIT :limit
        """
    )
    rows = session.exec(sql.bindparams(q=fts_query, limit=limit)).all()
    return {
        "q": q,
        "hits": [
            {
                "media_item_id": r[0],
                "title": r[1],
                "author_name": r[2],
                "tag_names": r[3],
            }
            for r in rows
        ],
    }
