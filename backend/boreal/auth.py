"""Opaque server sessions, Argon2id, throttling and role/CSRF checks."""

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import HTTPException, Request

from .common import audit
from .db import connect

PASSWORD_HASHER = PasswordHasher()
COOKIE = "boreal_session"
ORIGIN = os.environ.get("BOREAL_ORIGIN", "http://127.0.0.1:8000")
SECURE = os.environ.get("BOREAL_COOKIE_SECURE", "0") == "1"
SESSION_SECONDS = 3600


def fail(code, message, status=400):
    raise HTTPException(status_code=status, detail={"code": code, "message": message})


def validate_configuration():
    parsed = urlparse(ORIGIN)
    if os.environ.get("BOREAL_DEMO") == "1" and parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise RuntimeError("Demonstration failure controls are restricted to a loopback origin")
    if parsed.hostname not in ("127.0.0.1", "localhost", "::1") and (parsed.scheme != "https" or not SECURE):
        raise RuntimeError("Non-local operation requires HTTPS origin and BOREAL_COOKIE_SECURE=1")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise RuntimeError("BOREAL_ORIGIN must be an origin, without path/query/fragment")


def check_origin(request):
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != ORIGIN.rstrip("/"):
        fail("ORIGIN_REJECTED", "Request origin is not permitted.", 403)
    if request.headers.get("sec-fetch-site") == "cross-site":
        fail("ORIGIN_REJECTED", "Cross-site requests are not permitted.", 403)


def token_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def current_user(request: Request):
    token = request.cookies.get(COOKIE, "")
    if not token:
        fail("AUTH_REQUIRED", "Sign in to continue.", 401)
    with connect() as conn:
        row = conn.execute(
            """SELECT u.id,u.username,u.role,s.csrf FROM sessions s JOIN users u ON u.id=s.user_id
                            WHERE token_hash=%s AND expires_at>now()""",
            (token_hash(token),),
        ).fetchone()
    if not row:
        fail("SESSION_EXPIRED", "Your session has expired. Sign in again.", 401)
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        check_origin(request)
        if not secrets.compare_digest(request.headers.get("x-csrf-token", ""), row["csrf"]):
            fail("CSRF_REJECTED", "The session verification token is missing or invalid.", 403)
    return row


def require(user, *roles):
    if user["role"] not in roles:
        fail("ROLE_FORBIDDEN", "Your role is not authorized for this action.", 403)


def login(request, response, username, password):
    check_origin(request)
    if len(username) > 100 or len(password) > 1024:
        fail("INVALID_CREDENTIALS", "Invalid username or password.", 401)
    identity = token_hash(f"{request.client.host if request.client else 'local'}:{username}")
    with connect() as conn:
        # Serialize per identity so parallel login attempts cannot evade throttling.
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (identity,))
        count = conn.execute(
            "SELECT count(*) AS n FROM login_attempts WHERE identity=%s AND created_at>now()-interval '5 minutes'",
            (identity,),
        ).fetchone()["n"]
        if count >= 5:
            fail("LOGIN_THROTTLED", "Too many attempts. Try again in five minutes.", 429)
        conn.execute("INSERT INTO login_attempts(identity) VALUES (%s)", (identity,))
        user = conn.execute("SELECT * FROM users WHERE username=%s", (username,)).fetchone()
        valid = False
        if user:
            try:
                valid = PASSWORD_HASHER.verify(user["password_hash"], password)
            except (VerificationError, InvalidHashError):
                valid = False
        else:
            # Keep the expensive password-hashing path for unknown accounts as well.
            PASSWORD_HASHER.hash(password)
        if not valid:
            audit(conn, "anonymous", "login.failed", username)
        else:
            token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
            conn.execute(
                "INSERT INTO sessions(token_hash,user_id,csrf,expires_at) VALUES (%s,%s,%s,%s)",
                (token_hash(token), user["id"], csrf, datetime.now(timezone.utc) + timedelta(seconds=SESSION_SECONDS)),
            )
            conn.execute("DELETE FROM login_attempts WHERE identity=%s", (identity,))
            audit(conn, user["id"], "session.created", user["id"])
    # Raise after the transaction commits the unsuccessful attempt.
    if not valid:
        fail("INVALID_CREDENTIALS", "Invalid username or password.", 401)
    response.set_cookie(
        COOKIE, token, max_age=SESSION_SECONDS, httponly=True, secure=SECURE, samesite="strict", path="/"
    )
    return {"user": {k: user[k] for k in ("id", "username", "role")}, "csrf": csrf}
