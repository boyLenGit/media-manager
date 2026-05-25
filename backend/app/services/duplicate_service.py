"""资源去重服务。

两个用途:
1. 下载前检查:detect_search_result_duplicate
2. 资源库内部扫描:find_duplicate_groups,找出已入库的疑似重复组

去重维度(按精确度递减):
1. info_hash 完全匹配 → exact
2. partial_hash 完全匹配 → exact
3. magnet_uri 完全匹配 → exact
4. normalized_title + size_bytes 接近(±10MB) → high
5. normalized_title 完全匹配 → high
6. 标题模糊匹配 (Levenshtein < 0.2) → medium
7. 都不匹配 → none
"""
from collections import defaultdict
from dataclasses import dataclass, field
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


# ============================================================
# 资源库内部重复组扫描
# ============================================================
@dataclass
class DuplicateMember:
    """一个疑似重复组里的成员。"""

    media_id: int
    title: str
    cover_path: Optional[str] = None
    file_count: int = 0
    total_size_bytes: int = 0
    primary_filename: Optional[str] = None
    primary_path: Optional[str] = None
    primary_codec: Optional[str] = None
    primary_container: Optional[str] = None
    primary_quality: Optional[str] = None
    primary_width: Optional[int] = None
    primary_height: Optional[int] = None
    primary_duration_seconds: Optional[float] = None
    primary_partial_hash: Optional[str] = None
    created_at: Optional[str] = None
    watch_status: str = "unwatched"
    favorite: bool = False


@dataclass
class DuplicateGroup:
    """一组疑似重复的资源(2 个或更多)。"""

    group_key: str  # 用于前端 react key,例如 'norm:inception' 或 'phash:abc123'
    match_level: str  # exact / high / medium
    match_reason: str
    members: list[DuplicateMember] = field(default_factory=list)


def find_duplicate_groups(session: Session, similarity_threshold: float = 0.9) -> list[DuplicateGroup]:
    """全库扫描,找出所有疑似重复组。

    扫描策略(按精度从高到低,每个 media 只能落入一个组,避免重复):
    1. partial_hash 完全相同 → exact (同一文件,基本是同一资源)
    2. normalized_title 完全相同 → high
    3. normalized_title 模糊匹配 (Levenshtein > similarity_threshold) → medium

    返回的组:每组至少 2 个成员,member 顺序按 media_id 升序。
    """
    # 拉所有 media + 主文件 + file_asset
    rows = session.exec(
        select(MediaItem, MediaFile, FileAsset)
        .join(MediaFile, MediaFile.media_item_id == MediaItem.id, isouter=True)  # type: ignore[arg-type]
        .join(FileAsset, FileAsset.id == MediaFile.file_asset_id, isouter=True)  # type: ignore[arg-type]
    ).all()

    # 按 media_id 收集每个 media 的所有 file
    media_data: dict[int, dict] = {}
    for mi, mf, fa in rows:
        if mi.id is None:
            continue
        if mi.id not in media_data:
            media_data[mi.id] = {
                "item": mi,
                "files": [],  # list of (mf, fa)
            }
        if mf is not None and fa is not None:
            media_data[mi.id]["files"].append((mf, fa))

    if not media_data:
        return []

    # 用集合记录已经被分组的 media_id,避免重复
    grouped_ids: set[int] = set()
    groups: list[DuplicateGroup] = []

    # ---- 第 1 轮:partial_hash 相同 (exact) ----
    hash_to_mids: dict[str, list[int]] = defaultdict(list)
    for mid, d in media_data.items():
        for _mf, fa in d["files"]:
            if fa.partial_hash and fa.size_bytes:
                key = f"{fa.partial_hash}:{fa.size_bytes}"
                hash_to_mids[key].append(mid)
    for hkey, mids in hash_to_mids.items():
        unique = sorted(set(mids))
        if len(unique) >= 2:
            groups.append(
                DuplicateGroup(
                    group_key=f"phash:{hkey}",
                    match_level="exact",
                    match_reason="文件 partial_hash + 大小完全相同(基本可确认是同一资源)",
                    members=[_make_member(media_data[m]) for m in unique],
                )
            )
            grouped_ids.update(unique)

    # ---- 第 2 轮:normalized_title 完全相同 (high) ----
    norm_to_mids: dict[str, list[int]] = defaultdict(list)
    for mid, d in media_data.items():
        if mid in grouped_ids:
            continue
        nt = d["item"].normalized_title
        if nt and len(nt) >= 2:
            norm_to_mids[nt].append(mid)
    for nt, mids in norm_to_mids.items():
        unique = sorted(set(mids))
        if len(unique) >= 2:
            groups.append(
                DuplicateGroup(
                    group_key=f"norm:{nt}",
                    match_level="high",
                    match_reason="标题完全相同",
                    members=[_make_member(media_data[m]) for m in unique],
                )
            )
            grouped_ids.update(unique)

    # ---- 第 3 轮:标题模糊匹配 (medium) ----
    # O(n²) 但 n 一般不大;若超过 1000 可优化
    remaining = [
        (mid, d["item"].normalized_title)
        for mid, d in media_data.items()
        if mid not in grouped_ids and d["item"].normalized_title
    ]
    used: set[int] = set()
    for i, (mid_i, nt_i) in enumerate(remaining):
        if mid_i in used or len(nt_i) < 3:
            continue
        cluster = [mid_i]
        for j in range(i + 1, len(remaining)):
            mid_j, nt_j = remaining[j]
            if mid_j in used:
                continue
            sim = _levenshtein_ratio(nt_i, nt_j)
            if sim >= similarity_threshold:
                cluster.append(mid_j)
        if len(cluster) >= 2:
            for c in cluster:
                used.add(c)
            cluster_sorted = sorted(cluster)
            groups.append(
                DuplicateGroup(
                    group_key=f"fuzzy:{nt_i}",
                    match_level="medium",
                    match_reason=f"标题相似度 ≥ {int(similarity_threshold * 100)}%",
                    members=[_make_member(media_data[m]) for m in cluster_sorted],
                )
            )

    # 按"严重程度"排序:exact > high > medium,组内成员多的在前
    level_order = {"exact": 0, "high": 1, "medium": 2}
    groups.sort(key=lambda g: (level_order.get(g.match_level, 9), -len(g.members)))
    return groups


def _make_member(d: dict) -> DuplicateMember:
    item: MediaItem = d["item"]
    files = d["files"]

    # 主文件(优先 is_primary,否则第一个)
    primary_pair = None
    if files:
        primary_pair = next((p for p in files if p[0].is_primary), files[0])

    total_size = sum((fa.size_bytes or 0) for _mf, fa in files)

    m = DuplicateMember(
        media_id=item.id,  # type: ignore[arg-type]
        title=item.title,
        cover_path=item.cover_path,
        file_count=len(files),
        total_size_bytes=total_size,
        watch_status=item.watch_status,
        favorite=item.favorite,
        created_at=item.created_at.isoformat() + "Z" if item.created_at else None,
    )
    if primary_pair:
        mf, fa = primary_pair
        m.primary_filename = fa.filename
        m.primary_path = fa.path
        m.primary_codec = mf.video_codec
        m.primary_container = mf.container
        m.primary_quality = mf.quality
        m.primary_width = mf.width
        m.primary_height = mf.height
        m.primary_duration_seconds = mf.duration_seconds
        m.primary_partial_hash = fa.partial_hash
    return m
