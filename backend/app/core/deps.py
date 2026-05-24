"""FastAPI 依赖:从 Authorization header 解析当前用户。

用法:
    @router.get("/protected")
    def view(user: User = Depends(require_user)): ...

    @router.post("/admin-only")
    def admin_view(user: User = Depends(require_admin)): ...
"""
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlmodel import Session, select

from app.core.security import decode_token
from app.db.session import get_session
from app.models import RevokedToken, User


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing_token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return authorization[7:].strip()


def require_user(
    authorization: Annotated[str | None, Header()] = None,
    session: Session = Depends(get_session),
) -> User:
    token = _bearer(authorization)
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="token_expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="invalid_token")

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="wrong_token_type")

    user_id = int(payload["sub"])
    user = session.get(User, user_id)
    if not user or not user.enabled:
        raise HTTPException(status_code=401, detail="user_disabled")

    # access token 的 jti 也可能被撤销(管理员强制下线)
    jti = payload.get("jti")
    if jti:
        revoked = session.exec(select(RevokedToken).where(RevokedToken.jti == jti)).first()
        if revoked:
            raise HTTPException(status_code=401, detail="token_revoked")

    return user


def require_admin(user: User = Depends(require_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="admin_required")
    return user
