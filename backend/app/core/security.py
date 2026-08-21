"""认证安全工具:argon2 密码哈希 + JWT 令牌。"""
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import get_settings

_ph = PasswordHasher()
_settings = get_settings()


# ---- 密码 ----
def hash_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, plain)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


# ---- JWT ----
def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(user_id: int, role: str) -> tuple[str, datetime]:
    expires = _now_utc() + timedelta(minutes=_settings.jwt_access_ttl_minutes)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": _now_utc(),
        "exp": expires,
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(payload, _settings.jwt_secret, algorithm=_settings.jwt_algorithm)
    return token, expires


def create_refresh_token(user_id: int) -> tuple[str, str, datetime]:
    """返回 (token, jti, expires)。jti 用于撤销。"""
    jti = uuid.uuid4().hex
    expires = _now_utc() + timedelta(days=_settings.jwt_refresh_ttl_days)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": _now_utc(),
        "exp": expires,
        "jti": jti,
    }
    token = jwt.encode(payload, _settings.jwt_secret, algorithm=_settings.jwt_algorithm)
    return token, jti, expires


def decode_token(token: str) -> dict:
    """解码 JWT,异常自然抛出 (jwt.PyJWTError)。"""
    return jwt.decode(token, _settings.jwt_secret, algorithms=[_settings.jwt_algorithm])


# ---- 文件流签名 token ----
# 用于 <video src> 这种无法发送 Authorization header 的场景
# 短期(默认 1 小时),只能访问指定 file_asset_id
def create_stream_token(user_id: int, file_asset_id: int, ttl_minutes: int = 60) -> str:
    expires = _now_utc() + timedelta(minutes=ttl_minutes)
    payload = {
        "sub": str(user_id),
        "type": "stream",
        "fid": file_asset_id,
        "iat": _now_utc(),
        "exp": expires,
    }
    return jwt.encode(payload, _settings.jwt_secret, algorithm=_settings.jwt_algorithm)


def verify_stream_token(token: str, expected_file_id: int) -> int:
    """验证流 token,返回 user_id。失败抛 jwt.PyJWTError。"""
    payload = decode_token(token)
    if payload.get("type") != "stream":
        raise jwt.InvalidTokenError("wrong_token_type")
    if int(payload.get("fid", 0)) != expected_file_id:
        raise jwt.InvalidTokenError("file_id_mismatch")
    return int(payload["sub"])


# ---- 自定义字幕流签名 token ----
# 与视频 stream token 分开,payload 用不同的 type + csid 字段,
# 避免自定义字幕表和 file_asset 表各自独立的 id 空间被 verify 逻辑混淆
# (比如 custom_subtitle.id=5 与 file_asset.id=5 不应被当成同一个资源)
def create_custom_subtitle_token(
    user_id: int, custom_subtitle_id: int, ttl_minutes: int = 60
) -> str:
    expires = _now_utc() + timedelta(minutes=ttl_minutes)
    payload = {
        "sub": str(user_id),
        "type": "custom_subtitle_stream",
        "csid": custom_subtitle_id,
        "iat": _now_utc(),
        "exp": expires,
    }
    return jwt.encode(payload, _settings.jwt_secret, algorithm=_settings.jwt_algorithm)


def verify_custom_subtitle_token(token: str, expected_id: int) -> int:
    """验证自定义字幕流 token,返回 user_id。失败抛 jwt.PyJWTError。"""
    payload = decode_token(token)
    if payload.get("type") != "custom_subtitle_stream":
        raise jwt.InvalidTokenError("wrong_token_type")
    if int(payload.get("csid", 0)) != expected_id:
        raise jwt.InvalidTokenError("subtitle_id_mismatch")
    return int(payload["sub"])
