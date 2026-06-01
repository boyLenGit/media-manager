"""资源库重复检测接口 + 解析器配置接口。"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.deps import require_admin
from app.db.session import get_session
from app.models import MediaFile, MediaItem, User
from app.providers.parser.pipeline import ParserPipeline, list_available
from app.services import audit_service
from app.services.duplicate_service import find_duplicate_groups
from app.services.filename_parser import reset_pipeline_cache
from app.services.parser_config import (
    get_active_parser_names,
    set_active_parser_names,
)

router = APIRouter()


# ============================================================
# 重复检测
# ============================================================
@router.get("/duplicates")
def list_duplicates(
    similarity: float = Query(default=0.9, ge=0.5, le=1.0),
    session: Session = Depends(get_session),
) -> dict:
    """返回所有疑似重复组。"""
    groups = find_duplicate_groups(session, similarity_threshold=similarity)
    return {
        "total_groups": len(groups),
        "total_media": sum(len(g.members) for g in groups),
        "groups": [
            {
                "group_key": g.group_key,
                "match_level": g.match_level,
                "match_reason": g.match_reason,
                "members": [m.__dict__ for m in g.members],
            }
            for g in groups
        ],
    }


class MergeIn(BaseModel):
    """把多个 media 合并到一个"主 media",其他的删除(media_item 删,但 file_asset 保留)。

    被合并掉的 media 上的 media_file 关联会改成主 media。
    被合并的 media tag 关联会合并到主 media。
    """

    keep_media_id: int
    merge_media_ids: list[int]


@router.post("/duplicates/merge")
def merge_media(
    payload: MergeIn,
    request: Request = None,  # type: ignore[assignment]
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
) -> dict:
    """合并重复资源。"""
    keep = session.get(MediaItem, payload.keep_media_id)
    if not keep:
        raise HTTPException(status_code=404, detail="keep_media_not_found")

    affected_files = 0
    for mid in payload.merge_media_ids:
        if mid == payload.keep_media_id:
            continue
        # 把 media_file 转移到 keep
        files = session.exec(
            select(MediaFile).where(MediaFile.media_item_id == mid)
        ).all()
        for f in files:
            # 检查 keep 下没已有同 file_asset
            existing = session.exec(
                select(MediaFile).where(
                    MediaFile.media_item_id == payload.keep_media_id,
                    MediaFile.file_asset_id == f.file_asset_id,
                )
            ).first()
            if existing:
                # 已有,则删被合并的 media_file
                session.delete(f)
            else:
                f.media_item_id = payload.keep_media_id
                session.add(f)
                affected_files += 1

        # 删被合并的 media (media_tag 会因为 ON DELETE CASCADE 一起删)
        merged = session.get(MediaItem, mid)
        if merged:
            session.delete(merged)

    session.commit()
    # 审计
    audit_service.record(
        session,
        actor=admin,
        action="duplicates_merge",
        target_type="media",
        target_id=payload.keep_media_id,
        metadata={
            "merged_ids": [m for m in payload.merge_media_ids if m != payload.keep_media_id],
            "affected_files": affected_files,
            "keep_title": keep.title,
        },
        request=request,
    )
    return {"keep_media_id": payload.keep_media_id, "affected_files": affected_files}


class DeleteMediaIn(BaseModel):
    media_ids: list[int]
    delete_disk_files: bool = False  # MVP 不真删磁盘文件,仅从 DB 删


@router.post("/duplicates/delete")
def delete_duplicate_media(
    payload: DeleteMediaIn,
    request: Request = None,  # type: ignore[assignment]
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
) -> dict:
    """从重复组里删除某些资源(只删 DB 记录,不删磁盘)。"""
    deleted = 0
    deleted_titles: list[str] = []
    for mid in payload.media_ids:
        m = session.get(MediaItem, mid)
        if m:
            deleted_titles.append(m.title)
            session.delete(m)
            deleted += 1
    session.commit()
    # 审计
    audit_service.record(
        session,
        actor=admin,
        action="duplicates_delete",
        target_type="media",
        metadata={
            "media_ids": payload.media_ids,
            "deleted": deleted,
            "titles": deleted_titles,
        },
        request=request,
    )
    return {"deleted": deleted}


# ============================================================
# 解析器配置 + 重新解析
# ============================================================
@router.get("/parsers")
def get_parsers() -> dict:
    return {
        "available": list_available(),
        "active": get_active_parser_names(),
    }


class UpdateParsersIn(BaseModel):
    active: list[str]


@router.put("/parsers")
def update_parsers(payload: UpdateParsersIn) -> dict:
    set_active_parser_names(payload.active)
    return {"active": payload.active}


class ParseTestIn(BaseModel):
    filename: str
    parsers: list[str] | None = None  # 不传则用当前激活的


class ParseTestOut(BaseModel):
    title: str
    normalized_title: str
    year: int | None = None
    season: int | None = None
    episode: int | None = None
    quality: str | None = None
    release_group: str | None = None
    language_tags: list[str] = []
    pipeline: list[str] = []


@router.post("/parsers/test", response_model=ParseTestOut)
def test_parser(payload: ParseTestIn) -> ParseTestOut:
    """测试解析效果(不写库,前端"试一下"按钮用)。"""
    pipeline = ParserPipeline.from_config(payload.parsers)
    r = pipeline.parse(payload.filename)
    return ParseTestOut(
        title=r.title,
        normalized_title=r.normalized_title,
        year=r.year,
        season=r.season,
        episode=r.episode,
        quality=r.quality,
        release_group=r.release_group,
        language_tags=r.language_tags,
        pipeline=r.applied,
    )


@router.post("/parsers/reparse-all", status_code=202)
def reparse_all_media(session: Session = Depends(get_session)) -> dict:
    """用当前激活的 pipeline 重新解析所有 media_item 的标题。

    用 original_title 作为输入(它是原始文件名 stem,扫描时存的),
    如果没有则用 title。
    """
    reset_pipeline_cache()
    from app.providers.parser.pipeline import ParserPipeline

    pipeline = ParserPipeline.from_config(get_active_parser_names())

    items = session.exec(select(MediaItem)).all()
    updated = 0
    for it in items:
        source = it.original_title or it.title
        if not source:
            continue
        r = pipeline.parse(source)
        new_title = r.title.strip()
        new_norm = r.normalized_title
        if not new_title:
            continue
        if new_title != it.title or new_norm != it.normalized_title:
            it.title = new_title
            it.normalized_title = new_norm
            if r.year and not it.release_date:
                it.release_date = str(r.year)
            it.updated_at = datetime.utcnow()
            session.add(it)
            updated += 1
    session.commit()
    return {"total": len(items), "updated": updated}
