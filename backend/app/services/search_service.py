"""FTS5 索引同步。

策略:
- media_item / media_tag / media_file 变化时,删除旧 FTS 行 + 插入新 FTS 行
- 提供 sync_one(media_id) 和 rebuild_all() 两个 API
- 在 library / scan_service / batch 操作处主动调用
"""
import logging

from sqlalchemy import text
from sqlmodel import Session, select

from app.models import (
    Author,
    FileAsset,
    MediaFile,
    MediaItem,
    MediaTag,
    Tag,
)

logger = logging.getLogger(__name__)


def _build_row(session: Session, media_id: int) -> dict | None:
    media = session.get(MediaItem, media_id)
    if not media:
        return None

    author_name = ""
    if media.author_id:
        a = session.get(Author, media.author_id)
        if a:
            author_name = f"{a.name} {a.alias or ''}".strip()

    # 标签
    tag_rows = session.exec(
        select(Tag.name).join(MediaTag, MediaTag.tag_id == Tag.id).where(  # type: ignore[arg-type]
            MediaTag.media_item_id == media_id
        )
    ).all()
    tag_names = " ".join(r if isinstance(r, str) else r[0] for r in tag_rows)

    # 文件名 + 路径
    file_rows = session.exec(
        select(FileAsset.filename, FileAsset.path)  # type: ignore[arg-type]
        .join(MediaFile, MediaFile.file_asset_id == FileAsset.id)  # type: ignore[arg-type]
        .where(MediaFile.media_item_id == media_id)
    ).all()
    filenames = " ".join(r[0] for r in file_rows)
    paths = " ".join(r[1] for r in file_rows)

    return {
        "media_item_id": media_id,
        "title": media.title or "",
        "original_title": media.original_title or "",
        "normalized_title": media.normalized_title or "",
        "author_name": author_name,
        "tag_names": tag_names,
        "description": media.description or "",
        "filenames": filenames,
        "paths": paths,
    }


def sync_one(session: Session, media_id: int) -> None:
    """同步单个 media 的 FTS 行。"""
    row = _build_row(session, media_id)
    # 先删
    session.exec(
        text("DELETE FROM media_search_fts WHERE media_item_id = :id").bindparams(id=media_id)
    )
    if row:
        session.exec(
            text(
                """
                INSERT INTO media_search_fts (
                    media_item_id, title, original_title, normalized_title,
                    author_name, tag_names, description, filenames, paths
                ) VALUES (
                    :media_item_id, :title, :original_title, :normalized_title,
                    :author_name, :tag_names, :description, :filenames, :paths
                )
                """
            ).bindparams(**row)
        )
    # 注意:调用方负责 commit


def remove_one(session: Session, media_id: int) -> None:
    session.exec(
        text("DELETE FROM media_search_fts WHERE media_item_id = :id").bindparams(id=media_id)
    )


def rebuild_all(session: Session) -> int:
    """全量重建。"""
    session.exec(text("DELETE FROM media_search_fts"))
    media_ids = [m.id for m in session.exec(select(MediaItem)).all() if m.id]
    for mid in media_ids:
        sync_one(session, mid)
    return len(media_ids)


def search_media_ids(session: Session, q: str, limit: int = 500) -> list[int]:
    """搜索,返回匹配的 media_item_id 列表。

    覆盖字段:title / original_title(原始文件名) / normalized_title /
    author_name / tag_names / description / filenames / paths。

    两段式查询,兼顾"按词匹配"和"任意子串匹配":
    1. FTS5 MATCH 前缀匹配(按相关度排序,分词效果好,适合搜整个词/标题片段)
    2. 命中不足时,补一次 LIKE '%q%' 子串匹配(FTS5 虚拟表本身支持裸列 LIKE 查询,
       不需要额外 JOIN 回 MediaItem/FileAsset)。

    为什么需要第 2 步:FTS5 分词后是按"整词"索引的,前缀匹配只能匹配"以 q 开头的词",
    搜不到"词中间/结尾的子串"——比如文件名 `NameSearch-3180681_副本.mp4` 会被分词出
    `3180681` 这个词,搜索开头子串 `318` 能匹配到,但搜索中间/结尾子串 `0681` 匹配不到
    (这是很常见的场景:用户经常只记得文件名编号的后半段)。而原来的 MediaItem.title
    LIKE 查询虽然能做子串匹配,但只搜标题一个字段,覆盖面又太窄。两段结合取长补短。
    """
    q = q.strip()
    if not q:
        return []

    ordered_ids: list[int] = []
    seen: set[int] = set()

    # 第 1 步:FTS5 前缀匹配(按相关度排序,更精确的结果排在前面)
    safe_q = q.replace('"', '""')
    fts_query = f'"{safe_q}"*'
    try:
        rows = session.exec(
            text(
                """
                SELECT media_item_id
                FROM media_search_fts
                WHERE media_search_fts MATCH :q
                ORDER BY rank
                LIMIT :limit
                """
            ).bindparams(q=fts_query, limit=limit)
        ).all()
        for r in rows:
            if r[0] not in seen:
                seen.add(r[0])
                ordered_ids.append(r[0])
    except Exception:  # noqa: BLE001
        # FTS5 query 语法错误(比如用户输入了裸露的特殊符号)时不让整个接口 500,
        # 跳过这一步,继续走下面的 LIKE 兜底。
        logger.warning("FTS5 MATCH query failed for q=%r", q, exc_info=True)

    # 第 2 步:LIKE 子串兜底(结果数不足 limit 时才查,避免大库场景下总是白跑一次全表扫描)
    if len(ordered_ids) < limit:
        like_q = f"%{q}%"
        like_rows = session.exec(
            text(
                """
                SELECT media_item_id FROM media_search_fts
                WHERE title LIKE :q OR original_title LIKE :q OR normalized_title LIKE :q
                   OR author_name LIKE :q OR tag_names LIKE :q OR description LIKE :q
                   OR filenames LIKE :q OR paths LIKE :q
                LIMIT :limit
                """
            ).bindparams(q=like_q, limit=limit)
        ).all()
        for r in like_rows:
            if r[0] not in seen:
                seen.add(r[0])
                ordered_ids.append(r[0])

    return ordered_ids[:limit]
