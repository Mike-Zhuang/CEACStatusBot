import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, Request, Response, status

from .config import getSettings
from .database import getConnection, utcNowIso


SESSION_COOKIE_NAME = "ceac_session"


def hashPassword(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 210_000)
    return f"pbkdf2_sha256${salt}${base64.b64encode(digest).decode()}"


def verifyPassword(password: str, storedHash: str) -> bool:
    try:
        algorithm, salt, digest = storedHash.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    candidate = hashPassword(password, salt).split("$", 2)[2]
    return hmac.compare_digest(candidate, digest)


def hashCode(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def createSessionToken(userId: int, role: str) -> str:
    payload = {
        "userId": userId,
        "role": role,
        "expiresAt": (datetime.now(UTC) + timedelta(days=14)).timestamp(),
    }
    payloadBytes = json.dumps(payload, separators=(",", ":")).encode()
    payloadEncoded = base64.urlsafe_b64encode(payloadBytes).decode().rstrip("=")
    signature = hmac.new(getSettings().secretKey.encode(), payloadEncoded.encode(), hashlib.sha256).hexdigest()
    return f"{payloadEncoded}.{signature}"


def parseSessionToken(token: str) -> dict[str, Any] | None:
    try:
        payloadEncoded, signature = token.split(".", 1)
        expected = hmac.new(getSettings().secretKey.encode(), payloadEncoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        padded = payloadEncoded + "=" * (-len(payloadEncoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
    except Exception:
        return None
    if float(payload.get("expiresAt", 0)) < datetime.now(UTC).timestamp():
        return None
    return payload


def setSessionCookie(response: Response, user: dict[str, Any]) -> None:
    token = createSessionToken(int(user["id"]), str(user["role"]))
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        max_age=14 * 24 * 60 * 60,
    )


def clearSessionCookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME)


def getCurrentUser(request: Request) -> dict[str, Any]:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    payload = parseSessionToken(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效")
    with getConnection() as connection:
        user = connection.execute(
            "SELECT id, email, role, is_email_verified, created_at FROM users WHERE id = ?",
            (payload["userId"],),
        ).fetchone()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return user


def requireAdmin(request: Request) -> dict[str, Any]:
    user = getCurrentUser(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user


def seedDefaultUsers() -> None:
    now = utcNowIso()
    settings = getSettings()
    defaults = []
    if settings.defaultAdminEmail and settings.defaultAdminPassword:
        defaults.append((settings.defaultAdminEmail, settings.defaultAdminPassword, "admin"))
    if settings.defaultUserEmail and settings.defaultUserPassword:
        defaults.append((settings.defaultUserEmail, settings.defaultUserPassword, "user"))
    with getConnection() as connection:
        for email, password, role in defaults:
            exists = connection.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if exists:
                continue
            connection.execute(
                """
                INSERT INTO users (email, password_hash, role, is_email_verified, created_at, updated_at)
                VALUES (?, ?, ?, 1, ?, ?)
                """,
                (email, hashPassword(password), role, now, now),
            )
