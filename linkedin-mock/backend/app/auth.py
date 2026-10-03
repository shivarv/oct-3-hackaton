"""Password hashing and cookie-based sessions."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from bson import ObjectId
from fastapi import Cookie, Depends, HTTPException, Response

from .config import settings
from .db import mongo

SESSION_COOKIE = "session"

# scrypt cost. OWASP suggests N=2^17; 2^14 keeps logins fast in a small container (fine for a mock).
_N, _R, _P, _DKLEN = 2**14, 8, 1, 32


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        password.encode(), salt=salt, n=n, r=r, p=p, dklen=_DKLEN, maxmem=128 * n * r * 2
    )


def hash_password_sync(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = _scrypt(password, salt, _N, _R, _P)
    b64 = base64.b64encode
    return f"scrypt${_N}${_R}${_P}${b64(salt).decode()}${b64(digest).decode()}"


def verify_password_sync(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt_b64, digest_b64 = stored.split("$")
        if algo != "scrypt":
            return False
        expected = base64.b64decode(digest_b64)
        actual = _scrypt(password, base64.b64decode(salt_b64), int(n), int(r), int(p))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


# Hashing is CPU-bound (~50 ms), so keep it off the event loop.
async def hash_password(password: str) -> str:
    return await asyncio.to_thread(hash_password_sync, password)


async def verify_password(password: str, stored: str | None) -> bool:
    if stored is None:
        # Unknown user: still do the work so response time doesn't reveal which usernames exist.
        await asyncio.to_thread(verify_password_sync, password, _DUMMY_HASH)
        return False
    return await asyncio.to_thread(verify_password_sync, password, stored)


_DUMMY_HASH = hash_password_sync(secrets.token_urlsafe(16))


def _token_id(token: str) -> str:
    """Sessions are stored by SHA-256 of the token, so a database leak doesn't leak live tokens."""
    return hashlib.sha256(token.encode()).hexdigest()


async def start_session(response: Response, user_id: ObjectId) -> None:
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    expires = now + timedelta(days=settings.session_days)
    await mongo.db.sessions.insert_one(
        {"_id": _token_id(token), "user_id": user_id, "created_at": now, "expires_at": expires}
    )
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_days * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )


async def end_session(response: Response, token: str | None) -> None:
    if token:
        await mongo.db.sessions.delete_one({"_id": _token_id(token)})
    response.delete_cookie(SESSION_COOKIE, path="/")


async def current_user(
    session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> dict[str, Any]:
    """FastAPI dependency: the logged-in user's document, or 401."""
    if not session:
        raise HTTPException(status_code=401, detail="Not logged in")
    record = await mongo.db.sessions.find_one(
        {"_id": _token_id(session), "expires_at": {"$gt": datetime.now(UTC)}}
    )
    user = await mongo.db.users.find_one({"_id": record["user_id"]}) if record else None
    if user is None:
        raise HTTPException(status_code=401, detail="Session expired, please log in again")
    return user


CurrentUser = Annotated[dict[str, Any], Depends(current_user)]
