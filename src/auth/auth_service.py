"""
Authentication service using raw sqlite3.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Optional

from config.settings import get_settings
from src.auth.security import (
    create_access_token, generate_session_token,
    hash_password, verify_password,
)
from src.database.connection import get_db

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    pass


class AccountLockedError(AuthenticationError):
    pass


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except ValueError:
        return None


class AuthService:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._settings = get_settings()

    def login(self, username: str, password: str,
              ip_address: Optional[str] = None) -> tuple[dict, str]:
        dummy = "$2b$12$dummyhashfortimingneutrality000000000000000000000000000"
        row = self._conn.execute(
            "SELECT * FROM users WHERE username=?", (username,)
        ).fetchone()

        candidate_hash = dict(row)["password_hash"] if row else dummy
        password_ok = verify_password(password, candidate_hash)

        if row is None or not row["is_active"]:
            self._audit(None, username, "LOGIN_FAILED", success=0,
                        error="Unknown or inactive user", ip=ip_address)
            raise AuthenticationError("Identifiants incorrects.")

        user = dict(row)
        self._check_lockout(user, ip_address)

        if not password_ok:
            self._record_failed(user, ip_address)
            raise AuthenticationError("Identifiants incorrects.")

        # Reset failures
        self._conn.execute(
            "UPDATE users SET failed_login_attempts=0, locked_until=NULL, last_login=? WHERE id=?",
            (_now_iso(), user["id"])
        )
        token = generate_session_token()
        jwt_token = create_access_token(user["username"], user["role"], token)
        now = datetime.now(UTC)
        expire = (now + timedelta(minutes=self._settings.access_token_expire_minutes)).isoformat()
        self._conn.execute(
            """INSERT INTO user_sessions (user_id, token, ip_address, expires_at, last_activity, is_active)
               VALUES (?,?,?,?,?,1)""",
            (user["id"], token, ip_address, expire, _now_iso())
        )
        self._audit(user["id"], username, "LOGIN", ip=ip_address,
                    details=f"Login from {ip_address}")
        logger.info(f"User '{username}' logged in.")
        return user, jwt_token

    def logout(self, session_token: str) -> None:
        row = self._conn.execute(
            "SELECT user_id FROM user_sessions WHERE token=? AND is_active=1",
            (session_token,)
        ).fetchone()
        if row:
            self._conn.execute(
                "UPDATE user_sessions SET is_active=0 WHERE token=?", (session_token,)
            )
            self._audit(row["user_id"], None, "LOGOUT", details="Session revoked")

    def validate_session(self, session_token: str) -> Optional[dict]:
        now = datetime.now(UTC)
        row = self._conn.execute(
            """SELECT s.*, u.username, u.role, u.full_name, u.is_active, u.must_change_password,
                      u.id as user_id
               FROM user_sessions s JOIN users u ON s.user_id=u.id
               WHERE s.token=? AND s.is_active=1""",
            (session_token,)
        ).fetchone()
        if row is None:
            return None
        row = dict(row)

        expires = _parse_dt(row.get("expires_at"))
        if expires and expires < now:
            self._conn.execute("UPDATE user_sessions SET is_active=0 WHERE token=?", (session_token,))
            return None

        last_activity = _parse_dt(row.get("last_activity"))
        idle_limit = timedelta(minutes=self._settings.session_idle_timeout_minutes)
        if last_activity and (now - last_activity) > idle_limit:
            self._conn.execute("UPDATE user_sessions SET is_active=0 WHERE token=?", (session_token,))
            return None

        self._conn.execute(
            "UPDATE user_sessions SET last_activity=? WHERE token=?", (_now_iso(), session_token)
        )
        return row

    def _check_lockout(self, user: dict, ip: Optional[str]) -> None:
        locked = _parse_dt(user.get("locked_until"))
        if locked and locked > datetime.now(UTC):
            remaining = int((locked - datetime.now(UTC)).total_seconds() // 60)
            self._audit(user["id"], user["username"], "ACCOUNT_LOCKED",
                        success=0, ip=ip, error=f"Locked {remaining}min")
            raise AccountLockedError(
                f"Compte verrouillé. Réessayez dans {remaining} minute(s)."
            )

    def _record_failed(self, user: dict, ip: Optional[str]) -> None:
        attempts = user["failed_login_attempts"] + 1
        locked_until = None
        if attempts >= self._settings.max_login_attempts:
            locked_until = (
                datetime.now(UTC) +
                timedelta(minutes=self._settings.lockout_duration_minutes)
            ).isoformat()
        self._conn.execute(
            "UPDATE users SET failed_login_attempts=?, locked_until=? WHERE id=?",
            (attempts, locked_until, user["id"])
        )
        self._audit(user["id"], user["username"], "LOGIN_FAILED", success=0, ip=ip,
                    error=f"Attempt {attempts}")

    def _audit(self, user_id, username, action, resource=None,
               details=None, ip=None, success=1, error=None) -> None:
        self._conn.execute(
            """INSERT INTO audit_logs (user_id, username, action, resource, details,
               ip_address, success, error_message) VALUES (?,?,?,?,?,?,?,?)""",
            (user_id, username, action, resource, details, ip, success, error)
        )
