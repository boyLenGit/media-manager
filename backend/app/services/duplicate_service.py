"""资源去重服务。

去重维度(按精确度递减):
1. info_hash 完全匹配 → exact
2. partial_hash 完全匹配 → exact
3. magnet_uri 完全匹配 → exact
4. normalized_title + size_bytes 接近(±10MB) → high
5. normalized_title 完全匹配 → high
6. 标题模糊匹配 (Levenshtein < 0.2) → medium
7. 都不匹配 → none
"""
from dataclasses import dataclass
from typing import Optional

from sqlmodel import Session, select

from app.models import (
    DownloadTask,
    FileAsset,
    MediaFile,
    MediaItem,
    SearchResult,
)
from app.services.filename_parser import parse_filename


@dataclass
class DuplicateMatch:
    level: str  # exact / high / medium / none
    reason: str
    matched_media_id: int | None = None
    matched_file_id: int | None = None
    score: float = 0.0


def _normalize(s: str) -> str:
    # 先剥扩展名 (如果搜索结果标题里包含 .mkv 这种)
    import re

    cleaned = re.sub(r"\.(mkv|mp4|webm|avi|mov|m4v|ts|m2ts|flv|wmv|srt|ass|vtt)$", "", s, flags=re.IGNORECASE)
    return parse_filename(cleaned).normalized_title


def _levenshtein_ratio(a: str, b: str) -> float:
    """简单 Levenshtein,返回 0-1 相似度。短串性能没问题。"""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    m, n = len(a), len(b)
    if abs(m - n) / max(m, n) > 0.5:
        return 0.0  # 长度差太多,直接判否
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1]) + 1
    dist = dp[m][n]
    return 1 - dist / max(m, n)


# ============================================================
# 检测搜索结果是否重复(下载前调用)
# ============================================================
def detect_search_result_duplicate(
    session: Session,
    title: str,
    info_hash: Optional[str] = None,
    magnet_uri: Optional[str] = None,
    size_bytes: Optional[int] = None,
) -> DuplicateMatch:
    """检查给定的搜索结果是否在系统中已有对应资源。"""
    # 1. info_hash 命中下载任务
    if info_hash:
        task = session.exec(
            select(DownloadTask).where(DownloadTask.info_hash == info_hash.lower())
        ).first()
        if task:
            return DuplicateMatch(
                level="exact",
                reason=f"info_hash 与下载任务 #{task.id} 完全相同",
                score=1.0,
            )
        # 2. info_hash 命中已扫描的 search_result
        sr = session.exec(
            select(SearchResult).where(SearchResult.info_hash == info_hash.lower())
        ).first()
        if sr and sr.matched_media_id:
            return DuplicateMatch(
                level="exact",
                reason=f"该 info_hash 已被搜索过并关联到资源 #{sr.matched_media_id}",
                matched_media_id=sr.matched_media_id,
                score=1.0,
            )

    # 3. magnet_uri 完全匹配
    if magnet_uri:
        task = session.exec(
            select(DownloadTask).where(DownloadTask.magnet_uri == magnet_uri)
        ).first()
        if task:
            return DuplicateMatch(
                level="exact",
                reason=f"该磁力链接已存在下载任务 #{task.id}",
                score=1.0,
            )

    # 4. 按 normalized_title 找资源
    norm = _normalize(title)
    if not norm:
        return DuplicateMatch(level="none", reason="标题为空")

    candidates = session.exec(
        select(MediaItem).where(MediaItem.normalized_title == norm)
    ).all()

    for media in candidates:
        # 看这个 media 关联的文件,大小是否接近
        if size_bytes:
            file_rows = session.exec(
                select(FileAsset)
                .join(MediaFile, MediaFile.file_asset_id == FileAsset.id)  # type: ignore[arg-type]
                .where(MediaFile.media_item_id == media.id)
            ).all()
            for fa in file_rows:
                if fa.size_bytes and abs(fa.size_bytes - size_bytes) <= 10 * 1024 * 1024:
                    return DuplicateMatch(
                        level="high",
                        reason=f"标题相同且大小接近的资源 #{media.id} (文件 {fa.filename})",
                        matched_media_id=media.id,
                        matched_file_id=fa.id,
                        score=0.9,
                    )

        return DuplicateMatch(
            level="high",
            reason=f"标题完全相同的资源 #{media.id}",
            matched_media_id=media.id,
            score=0.85,
        )

    # 5. 模糊标题(扫一遍最近 200 个媒体作为候选,避免全表扫)
    recent = session.exec(
        select(MediaItem).order_by(MediaItem.id.desc()).limit(200)  # type: ignore[union-attr]
    ).all()
    best_score = 0.0
    best_media = None
    for media in recent:
        if not media.normalized_title:
            continue
        sim = _levenshtein_ratio(norm, media.normalized_title)
        if sim > best_score:
            best_score = sim
            best_media = media

    if best_score >= 0.85 and best_media:
        return DuplicateMatch(
            level="medium",
            reason=f"标题相似度 {best_score:.0%} 的资源 #{best_media.id} ({best_media.title})",
            matched_media_id=best_media.id,
            score=best_score,
        )

    return DuplicateMatch(level="none", reason="无重复")


# ============================================================
# 检测扫描到的文件是否与已存在文件重复 (扫描时使用)
# ============================================================
def detect_file_duplicate(
    session: Session,
    partial_hash: str,
    size_bytes: int,
    exclude_id: int | None = None,
) -> Optional[FileAsset]:
    """根据 partial_hash 找出可能的同源文件。"""
    if not partial_hash:
        return None
    stmt = select(FileAsset).where(
        FileAsset.partial_hash == partial_hash,
        FileAsset.size_bytes == size_bytes,
    )
    if exclude_id is not None:
        stmt = stmt.where(FileAsset.id != exclude_id)
    return session.exec(stmt).first()
