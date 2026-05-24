"""认证接口:setup / login / refresh / logout / me / users 管理。"""
from datetime import datetime

import jwt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.core.deps import require_admin, require_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import get_session
from app.models import RevokedToken, User

router = APIRouter()


# ============================================================
# Schemas
# ============================================================
class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    expires_at: datetime
    user: dict


class RefreshIn(BaseModel):
    refresh_token: str


class SetupIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1)
    display_name: str | None = None


class CreateUserIn(SetupIn):
    role: str = Field(default="viewer", pattern="^(admin|viewer)$")


class UpdateUserIn(BaseModel):
    display_name: str | None = None
    role: str | None = Field(default=None, pattern="^(admin|viewer)$")
    enabled: bool | None = None
    password: str | None = Field(default=None, min_length=1)


# ============================================================
# Helpers
# ============================================================
def _user_dict(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "display_name": u.display_name,
        "role": u.role,
        "enabled": u.enabled,
    }


def _has_any_user(session: Session) -> bool:
    return session.exec(select(User).limit(1)).first() is not None


# ============================================================
# Setup (首次启动引导)
# ============================================================
@router.get("/setup-required")
def setup_required(session: Session = Depends(get_session)) -> dict:
    """前端登录页先调用,判断是否需要走引导流程。"""
    return {"setup_required": not _has_any_user(session)}


@router.post("/setup", response_model=TokenOut)
def setup(payload: SetupIn, session: Session = Depends(get_session)) -> TokenOut:
    if _has_any_user(session):
        raise HTTPException(status_code=409, detail="setup_already_completed")

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name or payload.username,
        role="admin",
        enabled=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return _issue_tokens(user, session)


# ============================================================
# Login / Refresh / Logout
# ============================================================
def _issue_tokens(user: User, session: Session) -> TokenOut:
    access, exp = create_access_token(user.id, user.role)  # type: ignore[arg-type]
    refresh, _jti, _r_exp = create_refresh_token(user.id)  # type: ignore[arg-type]
    user.last_login_at = datetime.utcnow()
    session.add(user)
    session.commit()
    return TokenOut(
        access_token=access,
        refresh_token=refresh,
        expires_at=exp,
        user=_user_dict(user),
    )


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, session: Session = Depends(get_session)) -> TokenOut:
    user = session.exec(select(User).where(User.username == payload.username)).first()
    if not user or not user.enabled:
        raise HTTPException(status_code=401, detail="invalid_credentials")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid_credentials")
    return _issue_tokens(user, session)


@router.post("/refresh", response_model=TokenOut)
def refresh(payload: RefreshIn, session: Session = Depends(get_session)) -> TokenOut:
    try:
        data = decode_token(payload.refresh_token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="token_expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="invalid_token")

    if data.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="wrong_token_type")

    jti = data.get("jti")
    if jti and session.get(RevokedToken, jti):
        raise HTTPException(status_code=401, detail="token_revoked")

    user = session.get(User, int(data["sub"]))
    if not user or not user.enabled:
        raise HTTPException(status_code=401, detail="user_disabled")

    # 旋转 refresh token
    if jti:
        session.add(
            RevokedToken(
                jti=jti,
                user_id=user.id,  # type: ignore[arg-type]
                expires_at=datetime.utcfromtimestamp(data["exp"]),
            )
        )
        session.commit()
    return _issue_tokens(user, session)


@router.post("/logout", status_code=204)
def logout(payload: RefreshIn, session: Session = Depends(get_session)) -> None:
    """登出:撤销 refresh token,access token 因短过期自然失效。"""
    try:
        data = decode_token(payload.refresh_token)
    except jwt.PyJWTError:
        return  # 无效 token 也视为登出成功
    jti = data.get("jti")
    if jti and not session.get(RevokedToken, jti):
        session.add(
            RevokedToken(
                jti=jti,
                user_id=int(data["sub"]),
                expires_at=datetime.utcfromtimestamp(data["exp"]),
            )
        )
        session.commit()


# ============================================================
# 当前用户
# ============================================================
@router.get("/me")
def me(user: User = Depends(require_user)) -> dict:
    return _user_dict(user)


# ============================================================
# 用户管理 (admin only)
# ============================================================
@router.get("/users")
def list_users(
    _admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> list[dict]:
    users = session.exec(select(User).order_by(User.id)).all()  # type: ignore[union-attr]
    return [_user_dict(u) for u in users]


@router.post("/users", status_code=201)
def create_user(
    payload: CreateUserIn,
    _admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    if session.exec(select(User).where(User.username == payload.username)).first():
        raise HTTPException(status_code=409, detail="username_taken")
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name or payload.username,
        role=payload.role,
        enabled=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return _user_dict(user)


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    payload: UpdateUserIn,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")

    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.role is not None:
        # 不允许把自己降级
        if user.id == admin.id and payload.role != "admin":
            raise HTTPException(status_code=400, detail="cannot_demote_self")
        user.role = payload.role
    if payload.enabled is not None:
        if user.id == admin.id and not payload.enabled:
            raise HTTPException(status_code=400, detail="cannot_disable_self")
        user.enabled = payload.enabled
    if payload.password is not None:
        user.password_hash = hash_password(payload.password)

    user.updated_at = datetime.utcnow()
    session.add(user)
    session.commit()
    session.refresh(user)
    return _user_dict(user)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> None:
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="cannot_delete_self")
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user_not_found")
    session.delete(user)
    session.commit()
