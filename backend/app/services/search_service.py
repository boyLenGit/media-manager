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
    """走 FTS5 索引搜索,返回匹配的 media_item_id 列表(按相关度排序)。

    覆盖字段:title / original_title(原始文件名) / normalized_title /
    author_name / tag_names / description / filenames / paths。

    与 /api/search/local 用的是同一套查询逻辑 —— 之前资源库列表接口(list_media)
    只用 MediaItem.title 做简单 LIKE 匹配,搜不到"标题被清洗成英文,但原始文件名/
    标签里有中文关键词"这类常见场景;这里统一改用 FTS5,覆盖面更全。
    """
    q = q.strip()
    if not q:
        return []
    safe_q = q.replace('"', '""')
    fts_query = f'"{safe_q}"*'  # 前缀匹配
    sql = text(
        """
        SELECT media_item_id
        FROM media_search_fts
        WHERE media_search_fts MATCH :q
        ORDER BY rank
        LIMIT :limit
        """
    )
    try:
        rows = session.exec(sql.bindparams(q=fts_query, limit=limit)).all()
    except Exception:  # noqa: BLE001
        # FTS5 query 语法错误(比如用户输入了裸露的特殊符号)时不让整个接口 500,
        # 退化为空结果,前端表现为"没搜到"而不是报错。
        logger.warning("FTS5 query failed for q=%r", q, exc_info=True)
        return []
    return [r[0] for r in rows]
