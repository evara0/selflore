"""User accounts, browser sessions, and server-side authorization."""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal
from uuid import UUID, uuid4

import psycopg
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field


hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
_DUMMY_HASH = hasher.hash("not-a-real-account-password")
_USERNAME = re.compile(r"^[a-z][a-z0-9_-]{2,31}$")
_SESSION_LENGTH = timedelta(hours=24)
_THROTTLE_WINDOW = timedelta(minutes=15)
_THROTTLE_LIMIT = 5
_ADMIN_LOCK = 436177100223002


class Settings:
    def __init__(self) -> None:
        self.database_url = os.environ.get("SELFLORE_DATABASE_URL", "")
        self.environment = os.environ.get("SELFLORE_ENV", "dev")
        if self.environment not in {"dev", "prod"}:
            raise RuntimeError("SELFLORE_ENV 必须是 dev 或 prod")
        default_origins = "http://127.0.0.1:24566,http://127.0.0.1:24567" if self.environment == "dev" else ""
        self.origins = frozenset(
            item.strip().rstrip("/")
            for item in os.environ.get("SELFLORE_ALLOWED_ORIGINS", default_origins).split(",")
            if item.strip()
        )
        self.allow_registration = os.environ.get("SELFLORE_ALLOW_REGISTRATION", "true").lower() == "true"
        self.allow_insecure_http = (
            self.environment == "prod" and os.environ.get("SELFLORE_ALLOW_INSECURE_HTTP", "false").lower() == "true"
        )
        self.throttle_key = os.environ.get("SELFLORE_THROTTLE_KEY", "")
        if self.environment == "prod" and (not self.origins or not self.throttle_key):
            raise RuntimeError("生产环境需要 SELFLORE_ALLOWED_ORIGINS 和 SELFLORE_THROTTLE_KEY")
        if self.environment == "prod":
            required_scheme = "http://" if self.allow_insecure_http else "https://"
            if any(not origin.startswith(required_scheme) for origin in self.origins):
                raise RuntimeError(f"生产环境当前仅允许 {required_scheme[:-3].upper()} Origin")

    @property
    def cookie_name(self) -> str:
        if self.environment == "prod":
            return "selflore_session_http" if self.allow_insecure_http else "__Host-selflore_session"
        return "selflore_session_dev"

    @property
    def secure_cookie(self) -> bool:
        return self.environment == "prod" and not self.allow_insecure_http


def get_settings() -> Settings:
    return Settings()


def get_db(settings: Annotated[Settings, Depends(get_settings)]):
    if not settings.database_url:
        raise HTTPException(503, "数据库未配置")
    with psycopg.connect(settings.database_url) as connection:
        yield connection


def _now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_username(value: str) -> str:
    normalized = value.lower()
    if not _USERNAME.fullmatch(normalized):
        raise HTTPException(422, "用户名须为 3–32 位字母、数字、下划线或连字符，且以字母开头")
    return normalized


def validate_password(value: str) -> None:
    if not 12 <= len(value) <= 128:
        raise HTTPException(422, "密码长度须为 12–128 个字符")


def _verify_password(stored: str, supplied: str) -> bool:
    try:
        return hasher.verify(stored, supplied)
    except (VerifyMismatchError, VerificationError):
        return False


def _public_user(row) -> dict:
    return {"id": str(row[0]), "username": row[1], "role": row[2], "is_active": row[3]}


def _origin(request: Request, settings: Settings) -> None:
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin", "").rstrip("/")
        if origin not in settings.origins:
            raise HTTPException(403, "请求来源不受信任")


def _csrf(request: Request, token: str) -> None:
    supplied = request.headers.get("x-csrf-token", "")
    if not supplied or not hmac.compare_digest(supplied, token):
        raise HTTPException(403, "CSRF 验证失败")


def _bucket(settings: Settings, dimension: str, value: str) -> str:
    key = settings.throttle_key.encode() if settings.throttle_key else b"selflore-local-development-only"
    return hmac.new(key, f"{dimension}:{value}".encode(), hashlib.sha256).hexdigest()


def _locked_buckets(db: psycopg.Connection, keys: list[str], now: datetime) -> bool:
    with db.cursor() as cursor:
        for key in sorted(keys):
            cursor.execute(
                "INSERT INTO app.auth_login_throttle (bucket_key) VALUES (%s) ON CONFLICT DO NOTHING",
                (key,),
            )
        cursor.execute(
            "SELECT bucket_key, blocked_until FROM app.auth_login_throttle WHERE bucket_key = ANY(%s) ORDER BY bucket_key FOR UPDATE",
            (keys,),
        )
        return any(until is not None and until > now for _, until in cursor.fetchall())


def _record_attempt(db: psycopg.Connection, keys: list[str], now: datetime) -> None:
    with db.cursor() as cursor:
        for key in keys:
            cursor.execute(
                "SELECT failed_count, window_started_at FROM app.auth_login_throttle WHERE bucket_key = %s",
                (key,),
            )
            count, started = cursor.fetchone()
            if now - started >= _THROTTLE_WINDOW:
                count, started = 0, now
            count += 1
            cursor.execute(
                """UPDATE app.auth_login_throttle
                   SET failed_count = %s, window_started_at = %s,
                       blocked_until = %s, updated_at = %s
                   WHERE bucket_key = %s""",
                (count, started, now + _THROTTLE_WINDOW if count >= _THROTTLE_LIMIT else None, now, key),
            )


def _create_user(db: psycopg.Connection, username: str, password: str) -> dict:
    normalized = normalize_username(username)
    validate_password(password)
    user_id = uuid4()
    try:
        with db.cursor() as cursor:
            cursor.execute(
                """INSERT INTO app.users (id, username, password_hash, role)
                   VALUES (%s, %s, %s, 'member') RETURNING id, username, role, is_active""",
                (user_id, normalized, hasher.hash(password)),
            )
            row = cursor.fetchone()
            cursor.execute("SELECT to_regclass('app.user_profiles')")
            if cursor.fetchone()[0] is not None:
                cursor.execute("INSERT INTO app.user_profiles(user_id, display_name) VALUES (%s, %s)", (user_id, normalized))
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, "用户名已被使用") from None
    return _public_user(row)


def _session(db: psycopg.Connection, raw_token: str):
    token_hash = hashlib.sha256(raw_token.encode()).digest()
    with db.cursor() as cursor:
        cursor.execute(
            """SELECT u.id, u.username, u.role, u.is_active, s.csrf_token, s.id
               FROM app.auth_sessions s JOIN app.users u ON u.id = s.user_id
               WHERE s.token_hash = %s AND s.revoked_at IS NULL AND s.expires_at > now()
                 AND u.is_active = true""",
            (token_hash,),
        )
        return cursor.fetchone()


def current_user(
    request: Request,
    db: Annotated[psycopg.Connection, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    token = request.cookies.get(settings.cookie_name)
    row = _session(db, token) if token else None
    if row is None:
        raise HTTPException(401, "请先登录")
    return row


def admin_user(user: Annotated[tuple, Depends(current_user)]):
    if user[2] != "admin":
        raise HTTPException(403, "需要管理员权限")
    return user


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(max_length=32)
    password: str = Field(max_length=128)


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str
    new_password: str = Field(max_length=128)


class UserPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["member", "admin"] | None = None
    is_active: bool | None = None


router = APIRouter(prefix="/api", tags=["accounts"])


@router.get("/auth/config")
def auth_config(settings: Annotated[Settings, Depends(get_settings)]):
    return {"registration_enabled": settings.allow_registration}


@router.post("/auth/register", status_code=201)
def register(
    body: Credentials,
    request: Request,
    db: Annotated[psycopg.Connection, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    _origin(request, settings)
    if not settings.allow_registration:
        raise HTTPException(403, "公开注册已关闭")
    now = _now()
    key = _bucket(settings, "register-ip", request.client.host if request.client else "unknown")
    if _locked_buckets(db, [key], now):
        raise HTTPException(429, "请求过于频繁")
    _record_attempt(db, [key], now)
    db.commit()
    return _create_user(db, body.username, body.password)


@router.post("/auth/login")
def login(
    body: Credentials,
    request: Request,
    response: Response,
    db: Annotated[psycopg.Connection, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    _origin(request, settings)
    username = body.username.lower()
    now = _now()
    keys = [
        _bucket(settings, "login-ip", request.client.host if request.client else "unknown"),
        _bucket(settings, "login-user", username),
    ]
    if _locked_buckets(db, keys, now):
        raise HTTPException(429, "请求过于频繁")
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT id, username, role, is_active, password_hash FROM app.users WHERE username = %s",
            (username,),
        )
        row = cursor.fetchone()
    valid = _verify_password(row[4] if row else _DUMMY_HASH, body.password)
    if not row or not row[3] or not valid:
        _record_attempt(db, keys, now)
        db.commit()
        raise HTTPException(401, "用户名或密码错误")
    raw_token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    with db.cursor() as cursor:
        cursor.execute(
            """INSERT INTO app.auth_sessions (id, user_id, token_hash, csrf_token, expires_at)
               VALUES (%s, %s, %s, %s, %s)""",
            (uuid4(), row[0], hashlib.sha256(raw_token.encode()).digest(), csrf_token, now + _SESSION_LENGTH),
        )
        cursor.execute("DELETE FROM app.auth_login_throttle WHERE bucket_key = %s", (keys[1],))
    response.set_cookie(
        settings.cookie_name, raw_token, max_age=int(_SESSION_LENGTH.total_seconds()),
        secure=settings.secure_cookie, httponly=True, samesite="lax", path="/",
    )
    return _public_user(row)


@router.get("/auth/me")
def me(user: Annotated[tuple, Depends(current_user)]):
    return {**_public_user(user), "csrf_token": user[4]}


@router.post("/auth/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    user: Annotated[tuple, Depends(current_user)],
    db: Annotated[psycopg.Connection, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    _origin(request, settings)
    _csrf(request, user[4])
    with db.cursor() as cursor:
        cursor.execute("UPDATE app.auth_sessions SET revoked_at = now() WHERE id = %s", (user[5],))
    response.delete_cookie(settings.cookie_name, path="/", secure=settings.secure_cookie, httponly=True, samesite="lax")


@router.post("/auth/change-password", status_code=204)
def change_password(
    body: PasswordChange,
    request: Request,
    response: Response,
    user: Annotated[tuple, Depends(current_user)],
    db: Annotated[psycopg.Connection, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    _origin(request, settings)
    _csrf(request, user[4])
    validate_password(body.new_password)
    with db.cursor() as cursor:
        cursor.execute("SELECT password_hash FROM app.users WHERE id = %s FOR UPDATE", (user[0],))
        if not _verify_password(cursor.fetchone()[0], body.current_password):
            raise HTTPException(400, "当前密码错误")
        cursor.execute("UPDATE app.users SET password_hash = %s, updated_at = now() WHERE id = %s", (hasher.hash(body.new_password), user[0]))
        cursor.execute("UPDATE app.auth_sessions SET revoked_at = now() WHERE user_id = %s AND revoked_at IS NULL", (user[0],))
    response.delete_cookie(settings.cookie_name, path="/", secure=settings.secure_cookie, httponly=True, samesite="lax")


@router.get("/admin/users")
def list_users(
    admin: Annotated[tuple, Depends(admin_user)],
    db: Annotated[psycopg.Connection, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    with db.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM app.users")
        total = cursor.fetchone()[0]
        cursor.execute(
            "SELECT id, username, role, is_active FROM app.users ORDER BY created_at, id LIMIT %s OFFSET %s",
            (limit, offset),
        )
        items = [_public_user(row) for row in cursor.fetchall()]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("/admin/users", status_code=201)
def admin_create_user(
    body: Credentials,
    request: Request,
    admin: Annotated[tuple, Depends(admin_user)],
    db: Annotated[psycopg.Connection, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    _origin(request, settings)
    _csrf(request, admin[4])
    created = _create_user(db, body.username, body.password)
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO app.account_audit (id, actor_user_id, target_user_id, action, role_after, is_active_after) VALUES (%s, %s, %s, 'created', 'member', true)",
            (uuid4(), admin[0], UUID(created["id"])),
        )
    return created


@router.patch("/admin/users/{user_id}")
def patch_user(
    user_id: UUID,
    body: UserPatch,
    request: Request,
    admin: Annotated[tuple, Depends(admin_user)],
    db: Annotated[psycopg.Connection, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    _origin(request, settings)
    _csrf(request, admin[4])
    if not body.model_fields_set or any(getattr(body, field) is None for field in body.model_fields_set):
        raise HTTPException(422, "请提供角色或可用状态")
    with db.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", (_ADMIN_LOCK,))
        cursor.execute("SELECT id, username, role, is_active FROM app.users WHERE id = %s FOR UPDATE", (user_id,))
        old = cursor.fetchone()
        if old is None:
            raise HTTPException(404, "账号不存在")
        new_role = body.role if body.role is not None else old[2]
        new_active = body.is_active if body.is_active is not None else old[3]
        if old[2] == "admin" and old[3] and (new_role != "admin" or not new_active):
            cursor.execute("SELECT count(*) FROM app.users WHERE role = 'admin' AND is_active = true")
            if cursor.fetchone()[0] <= 1:
                raise HTTPException(409, "至少需要保留一位可用管理员")
        if (new_role, new_active) != (old[2], old[3]):
            cursor.execute(
                "UPDATE app.users SET role = %s, is_active = %s, updated_at = now() WHERE id = %s",
                (new_role, new_active, user_id),
            )
            cursor.execute("UPDATE app.auth_sessions SET revoked_at = now() WHERE user_id = %s AND revoked_at IS NULL", (user_id,))
            if new_role != old[2]:
                cursor.execute(
                    """INSERT INTO app.account_audit
                       (id, actor_user_id, target_user_id, action, role_before, role_after)
                       VALUES (%s, %s, %s, 'role_changed', %s, %s)""",
                    (uuid4(), admin[0], user_id, old[2], new_role),
                )
            if new_active != old[3]:
                cursor.execute(
                    """INSERT INTO app.account_audit
                       (id, actor_user_id, target_user_id, action, is_active_before, is_active_after)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (uuid4(), admin[0], user_id, "activated" if new_active else "deactivated", old[3], new_active),
                )
        return {"id": str(old[0]), "username": old[1], "role": new_role, "is_active": new_active}
