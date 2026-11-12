from __future__ import annotations

"""Authentication, password security, session management, and authorization dependencies."""

import hashlib
import hmac
import logging
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, Header, HTTPException, status

from app.db import get_db

logger = logging.getLogger(__name__)

# Security Constants (OWASP 2023+ PBKDF2-HMAC-SHA256 Standard)
PBKDF2_ALGORITHM = "sha256"
PBKDF2_ITERATIONS = 600_000
PBKDF2_MIN_ITERATIONS = 100_000
PBKDF2_MAX_ITERATIONS = 2_000_000
PBKDF2_SALT_BYTES = 16
LEGACY_SALT = "smartstock_secret_salt_2026"
SESSION_DURATION_DAYS = 7


def _utc_now() -> datetime:
    """Return current UTC datetime as naive UTC for consistent ISO comparisons."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with a unique 16-byte cryptographic salt.

    Returns:
        Formatted string: 'pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>'
    """
    salt = secrets.token_hex(PBKDF2_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(
        PBKDF2_ALGORITHM,
        password.encode(),
        salt.encode(),
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${dk.hex()}"


def verify_password(password: str, stored_hash: str) -> tuple[bool, bool]:
    """Verify a candidate password against stored hash.

    Supports both current PBKDF2 hashes and legacy static-salted SHA-256 hashes.

    Returns:
        tuple[is_valid, needs_rehash]:
            - is_valid: True if password matches.
            - needs_rehash: True if matched via legacy algorithm or sub-optimal iteration count,
              signaling that the database record should be upgraded to PBKDF2 600k.
    """
    if stored_hash.startswith("pbkdf2_sha256$"):
        try:
            parts = stored_hash.split("$")
            if len(parts) != 4:
                return False, False
            _, iters_str, salt, target_hex = parts
            iters = int(iters_str)
            if not (PBKDF2_MIN_ITERATIONS <= iters <= PBKDF2_MAX_ITERATIONS):
                logger.warning("Out-of-bounds PBKDF2 iteration count rejected")
                return False, False
            dk = hashlib.pbkdf2_hmac(
                PBKDF2_ALGORITHM,
                password.encode(),
                salt.encode(),
                iters,
            )
            matched = hmac.compare_digest(dk.hex(), target_hex)
            needs_rehash = matched and (iters < PBKDF2_ITERATIONS)
            return matched, needs_rehash
        except Exception as exc:
            logger.warning("Error verifying PBKDF2 password: %s", exc)
            return False, False

    # Check legacy SHA-256 hash (64 hex characters) for login-time transparent migration
    try:
        legacy_hash = hashlib.sha256(f"{LEGACY_SALT}_{password}".encode()).hexdigest()
        if hmac.compare_digest(legacy_hash, stored_hash):
            return True, True  # Valid match, needs upgrade to PBKDF2
    except Exception as exc:
        logger.warning("Error verifying legacy password: %s", exc)

    return False, False


def create_session(
    user_id: str,
    user_email: str,
    db: sqlite3.Connection,
    duration_days: int = SESSION_DURATION_DAYS,
) -> str:
    """Generate a 256-bit cryptographically secure random session token and persist it."""
    if duration_days < 1:
        raise ValueError("duration_days must be at least 1")

    token = secrets.token_hex(32)
    now = _utc_now()
    expires_at = (now + timedelta(days=duration_days)).isoformat()
    now_iso = now.isoformat()

    cursor = db.cursor()
    cursor.execute(
        """INSERT INTO app_sessions (token, user_id, user_email, created_at, expires_at, revoked)
           VALUES (?, ?, ?, ?, ?, 0)""",
        (token, user_id, user_email.strip().lower(), now_iso, expires_at),
    )
    db.commit()
    return token


def revoke_session(token: str, db: sqlite3.Connection) -> bool:
    """Revoke an active session token."""
    cursor = db.cursor()
    cursor.execute("UPDATE app_sessions SET revoked = 1 WHERE token = ?", (token,))
    db.commit()
    return cursor.rowcount > 0


def get_current_user(
    authorization: str | None = Header(None),
    db: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    """FastAPI Dependency: Authenticate request via Bearer token and return active user profile.

    Enforces strict cryptographic session persistence in app_sessions.
    Raises 401 Unauthorized for missing, invalid, expired, or revoked tokens.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Missing or malformed Bearer authorization token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token cannot be empty.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    cursor = db.cursor()
    cursor.execute(
        """SELECT s.token, s.user_id, s.user_email, s.expires_at, s.revoked,
                  u.id, u.email, u.store_name, u.phone, u.manager
           FROM app_sessions s
           JOIN app_users u ON s.user_id = u.id
           WHERE s.token = ?""",
        (token,),
    )
    row = cursor.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or unrecognized authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    session_data = dict(row)
    if session_data["revoked"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been revoked. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    now_utc = _utc_now()
    try:
        exp_dt = datetime.fromisoformat(session_data["expires_at"].replace("Z", "+00:00")).replace(tzinfo=None)
        is_expired = exp_dt <= now_utc
    except Exception:
        is_expired = session_data["expires_at"] <= now_utc.isoformat()

    if is_expired:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "id": session_data["id"],
        "email": session_data["email"],
        "store_name": session_data["store_name"],
        "phone": session_data["phone"],
        "manager": session_data["manager"],
        "token": token,
    }
