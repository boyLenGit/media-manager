"""系统设置 API。

设计:key-value 风格,前端拿到后渲染为分类设置页。
"""
import logging
from datetime import datetime
from pathlib import Path

import jwt
from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session, select

from app.core.deps import require_admin
from app.core.security import decode_token, verify_password
from app.db.session import get_session
from app.models import AppSetting, RevokedToken, User
from app.services import audit_service, thumbnail_service

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
    # 当前管理员的登录密码 — 服务端 bcrypt 验证
    password: str
    # 是否同时把缩略图磁盘文件清掉
    purge_thumbnails: bool = True


class ResetAllResult(BaseModel):
    cleared_tables: list[str]
    thumbnails_purged: bool
    note: str
    # 提示前端立即清 token 跳登录
    force_logout: bool = True


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
    request: Request = None,  # type: ignore[assignment]
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
) -> ResetAllResult:
    """**危险操作**: 清空除当前管理员之外的所有数据。

    安全:
    - 必须是当前 admin
    - 必须用 admin 自己的登录密码二次确认(服务端 bcrypt 校验)
    - 操作完成后强制让当前 admin 重新登录:
        * access token jti 加入 revoked_token 黑名单
        * 前端收到 force_logout=true 后清 localStorage 跳登录
    - 写一条 audit_log

    会清空:
    - 所有视频/资源 (media_item, file_asset, media_file, media_tag, ...)
    - 所有扫描任务和历史 (scan_job, scan_log, scan_path)
    - 所有标签/作者/类型/资源源
    - 所有下载任务、播放历史、播放目标
    - 所有 app_setting 条目
    - 除当前管理员外的所有用户和 revoked_token (审计日志会保留)
    - 缩略图文件(可选)

    不会动:
    - 当前管理员账号本身
    - 审计日志(audit_log)
    - SQLite 文件结构(只 DELETE FROM,不 DROP)
    - 你磁盘上的真实视频文件
    """
    # 1. 二次密码验证
    if not verify_password(payload.password, admin.password_hash):
        # 失败也写一条审计
        audit_service.record(
            session,
            actor=admin,
            action="reset_all.failed",
            target_type="system",
            metadata={"reason": "password_incorrect"},
            request=request,
        )
        raise HTTPException(status_code=403, detail="password_incorrect")

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

    # 5. 强制 admin 重新登录
    #    把当前 access token 的 jti 加入 revoked_token,
    #    require_user 下次校验时就会拒。前端配合 force_logout=true 立刻清 localStorage。
    try:
        if authorization and authorization.lower().startswith("bearer "):
            tok = authorization[7:].strip()
            try:
                data = decode_token(tok)
                jti = data.get("jti")
                exp_ts = data.get("exp")
                if jti and exp_ts:
                    session.add(
                        RevokedToken(
                            jti=jti,
                            user_id=admin.id,  # type: ignore[arg-type]
                            expires_at=datetime.utcfromtimestamp(exp_ts),
                        )
                    )
                    session.commit()
            except jwt.PyJWTError:
                pass  # token 解析失败就算了
    except Exception as e:  # noqa: BLE001
        logger.warning("revoke admin token failed: %s", e)

    # 6. 写审计 (audit_log 在 _TABLES_TO_RESET 之外,不会被自己清掉)
    audit_service.record(
        session,
        actor=admin,
        action="reset_all",
        target_type="system",
        metadata={
            "cleared_tables": cleared,
            "thumbnails_purged": thumbnails_purged,
            "purge_thumbnails_param": payload.purge_thumbnails,
        },
        request=request,
    )

    return ResetAllResult(
        cleared_tables=cleared,
        thumbnails_purged=thumbnails_purged,
        note=(
            "数据已全部清空。当前管理员账号保留;"
            "你磁盘上的真实视频文件未被删除;请重新进入「设置 → 扫描路径」开始新一轮扫描。"
            "为安全考虑,你的当前会话已被作废,请重新登录。"
        ),
        force_logout=True,
    )


# ============================================================
# 审计日志查询
# ============================================================
class AuditLogOut(BaseModel):
    id: int
    actor_user_id: int | None = None
    actor_username: str | None = None
    action: str
    target_type: str | None = None
    target_id: str | None = None
    metadata_json: str | None = None
    ip: str | None = None
    user_agent: str | None = None
    created_at: datetime


@router.get("/audit-log", response_model=list[AuditLogOut])
def list_audit_logs(
    limit: int = 100,
    action: str | None = None,
    session: Session = Depends(get_session),
    _admin: User = Depends(require_admin),
) -> list[AuditLogOut]:
    """查询审计日志(admin only,按时间倒序)。"""
    from app.models import AuditLog

    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())  # type: ignore[union-attr]
    if action:
        stmt = stmt.where(AuditLog.action == action)
    rows = session.exec(stmt.limit(min(limit, 500))).all()
    return [
        AuditLogOut(
            id=r.id,  # type: ignore[arg-type]
            actor_user_id=r.actor_user_id,
            actor_username=r.actor_username,
            action=r.action,
            target_type=r.target_type,
            target_id=r.target_id,
            metadata_json=r.metadata_json,
            ip=r.ip,
            user_agent=r.user_agent,
            created_at=r.created_at,
        )
        for r in rows
    ]
