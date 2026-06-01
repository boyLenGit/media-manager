"""审计日志写入辅助。

约定:任何敏感操作都通过 record(...) 写一条 audit_log。
不要在调用处直接 INSERT,避免字段漏填。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from fastapi import Request
from sqlmodel import Session

from app.models import AuditLog, User

logger = logging.getLogger(__name__)


def record(
    session: Session,
    *,
    actor: Optional[User],
    action: str,
    target_type: Optional[str] = None,
    target_id: Optional[str | int] = None,
    metadata: Optional[dict[str, Any]] = None,
    request: Optional[Request] = None,
) -> AuditLog:
    """写一条审计日志。

    actor 可为 None(系统操作)。失败不抛,记 logger 后吞掉(审计不该影响主流程)。
    """
    try:
        ip = None
        ua = None
        if request is not None:
            ip = (request.client.host if request.client else None) or request.headers.get(
                "x-forwarded-for", ""
            ).split(",")[0].strip() or None
            ua = request.headers.get("user-agent")

        log = AuditLog(
            actor_user_id=actor.id if actor else None,
            actor_username=actor.username if actor else None,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            metadata_json=json.dumps(metadata, ensure_ascii=False) if metadata else None,
            ip=ip,
            user_agent=ua,
        )
        session.add(log)
        session.commit()
        session.refresh(log)
        return log
    except Exception as e:  # noqa: BLE001
        logger.exception("audit record failed: action=%s err=%s", action, e)
        # 不抛
        try:
            session.rollback()
        except Exception:  # noqa: BLE001
            pass
        # 返回一个未持久化的占位,调用方一般不关心返回值
        return AuditLog(action=action)
