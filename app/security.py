"""Password hashing, JWT, authentication dependencies (RBAC), and a small in-memory rate limiter."""
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, Request

from .config import settings
from .db import db
from .errors import AppError, forbidden, unauthorized


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=10)).decode()


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except ValueError:
        return False


def sign_token(user_id: int, role: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expires_hours)
    return jwt.encode({"sub": str(user_id), "role": role, "exp": exp}, settings.jwt_secret, algorithm="HS256")


def _load_user(token: str | None) -> dict:
    if not token:
        raise unauthorized()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise unauthorized("Session expired or invalid. Please sign in again.")
    # Loaded fresh from the DB on every request, so removed users lose access immediately.
    row = db.one("SELECT id, email, name, role, author_id FROM users WHERE id = ?", (payload["sub"],))
    if not row:
        raise unauthorized()
    return {"id": row["id"], "email": row["email"], "name": row["name"], "role": row["role"], "authorId": row["author_id"]}


def current_user(request: Request) -> dict:
    header = request.headers.get("authorization", "")
    return _load_user(header[7:] if header.startswith("Bearer ") else None)


def current_user_sse(request: Request) -> dict:
    """EventSource cannot set headers, so the SSE endpoint alone also accepts ?token=."""
    header = request.headers.get("authorization", "")
    token = header[7:] if header.startswith("Bearer ") else request.query_params.get("token")
    return _load_user(token)


def require_admin(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "admin":
        raise forbidden()
    return user


def require_author(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "author":
        raise forbidden()
    return user


class RateLimit:
    """Sliding-window limiter per client IP. Use as a dependency: Depends(RateLimit(10, 60))."""

    def __init__(self, max_calls: int, window_s: int = 60):
        self.max, self.window = max_calls, window_s
        self.hits: dict[str, deque] = defaultdict(deque)

    def __call__(self, request: Request):
        fwd = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        key = fwd or (request.client.host if request.client else "unknown")
        now, q = time.monotonic(), self.hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.max:
            raise AppError(429, "RATE_LIMITED", "Too many requests. Please slow down and try again shortly.")
        q.append(now)
