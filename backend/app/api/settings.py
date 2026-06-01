"""系统设置 API。

设计:key-value 风格,前端拿到后渲染为分类设置页。
"""
import logging
from pathlib import Path

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session, select

from app.core.deps import require_admin
from app.db.session import get_session
from app.models import AppSetting, User
from app.services import thumbnail_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("")
def list_settings(session: Session = Depends(get_session)) -> list[AppSetting]:
    return session.exec(select(AppSetting)).all()


@router.put("/{key}")
def upsert_setting(key: str, payload: dict, session: Session = Depends(get_session)) -> AppSetting:
    value = payload.get("value")
    value_type = payload.get("value_type", "string")
    obj = session.exec(select(AppSetting).where(AppSetting.key == key)).first()
    if obj:
        obj.value = value
        obj.value_type = value_type
    else:
        obj = AppSetting(key=key, value=value, value_type=value_type)
        session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


@router.delete("/{key}", status_code=204)
def delete_setting(key: str, session: Session = Depends(get_session)) -> None:
    obj = session.exec(select(AppSetting).where(AppSetting.key == key)).first()
    if not obj:
        raise HTTPException(status_code=404)
    session.delete(obj)
    session.commit()


# ============================================================
# 危险操作: 一键清空所有数据
# ============================================================
class ResetAllIn(BaseModel):
    # 必须传入 confirm=ERASE_ALL,否则拒绝执行(防误操作)
    confirm: str
    # 是否同时把缩略图磁盘文件清掉
    purge_thumbnails: bool = True


class ResetAllResult(BaseModel):
    cleared_tables: list[str]
    thumbnails_purged: bool
    note: str


# 清空顺序很重要 — 先清有外键引用的子表,再清父表
# 注:不会清空当前管理员账号(留一个 admin 让用户能重新登录)
_TABLES_TO_RESET = [
    # 资源相关
    "media_tag",
    "media_search_fts",
    "media_file",
    "duplicate_match",
    "media_item",
    "file_asset",
    "scan_log",
    "scan_job",
    "scan_path",
    # 派生数据
    "search_result",
    "download_task",
    "playback_history",
    "playback_target",
    # 字典
    "tag",
    "author",
    "media_type",
    "resource_source",
    # 应用配置
    "app_setting",
    # 注:user / revoked_token 单独处理(保留当前管理员)
]


@router.post("/reset-all", response_model=ResetAllResult)
def reset_all(
    payload: ResetAllIn = Body(...),
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
) -> ResetAllResult:
    """**危险操作**: 清空除当前管理员之外的所有数据。

    - 必须传 `confirm: "ERASE_ALL"`
    - 仅当前用户为 admin 才允许
    - 当前管理员的账号会被保留(否则之后无法登录)
    - 缩略图文件可选清理(默认清)

    会清空:
    - 所有视频/资源 (media_item, file_asset, media_file, media_tag, ...)
    - 所有扫描任务和历史 (scan_job, scan_log, scan_path)
    - 所有标签/作者/类型/资源源
    - 所有下载任务、播放历史、播放目标
    - 所有 app_setting 条目
    - 除当前管理员外的所有用户和 revoked_token
    - 缩略图文件(可选)

    不会动:
    - 当前管理员账号本身
    - SQLite 文件结构(只 DELETE FROM,不 DROP)
    - 你磁盘上的真实视频文件
    """
    if payload.confirm != "ERASE_ALL":
        raise HTTPException(status_code=400, detail="confirmation_text_required: ERASE_ALL")

    cleared: list[str] = []

    # 1. 按依赖顺序清表
    for tname in _TABLES_TO_RESET:
        try:
            session.execute(text(f"DELETE FROM {tname}"))
            cleared.append(tname)
        except Exception as e:  # noqa: BLE001
            # 表不存在 / 是虚拟表等情况 → 跳过但记录日志
            logger.warning("reset: skip %s (%s)", tname, e)

    # 2. 用户表:保留当前管理员,删其它所有人 + 撤销 token
    try:
        session.execute(
            text("DELETE FROM revoked_token")
        )  # 全清,反正其他用户都没了
        cleared.append("revoked_token")
        session.execute(
            text("DELETE FROM user WHERE id != :keep_id"), {"keep_id": admin.id}
        )
        cleared.append("user(except current admin)")
    except Exception as e:  # noqa: BLE001
        logger.warning("reset users failed: %s", e)

    # 3. AUTOINCREMENT 序列复位(让重新扫描的 id 从 1 开始,看着干净)
    try:
        session.execute(
            text("DELETE FROM sqlite_sequence WHERE name NOT IN ('user', 'revoked_token')")
        )
    except Exception:  # noqa: BLE001
        pass

    session.commit()

    # 4. 缩略图文件
    thumbnails_purged = False
    if payload.purge_thumbnails:
        try:
            tdir: Path = thumbnail_service.get_thumbnail_dir()
            if tdir.exists():
                for f in tdir.iterdir():
                    if f.is_file():
                        try:
                            f.unlink()
                        except Exception:  # noqa: BLE001
                            pass
                thumbnails_purged = True
        except Exception as e:  # noqa: BLE001
            logger.warning("purge thumbnails failed: %s", e)

    return ResetAllResult(
        cleared_tables=cleared,
        thumbnails_purged=thumbnails_purged,
        note=(
            "数据已全部清空。当前管理员账号保留;"
            "你磁盘上的真实视频文件未被删除;请重新进入「设置 → 扫描路径」开始新一轮扫描。"
        ),
    )
