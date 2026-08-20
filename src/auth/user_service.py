"""User management service using sqlite3."""

from __future__ import annotations

import logging
import sqlite3
from typing import Optional

from src.auth.security import hash_password, is_strong_password, verify_password

logger = logging.getLogger(__name__)


class PermissionError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


class DuplicateUsernameError(Exception):
    pass


class UserService:
    def __init__(self, conn: sqlite3.Connection, acting_user_id: int, acting_role: str) -> None:
        self._conn = conn
        self._actor_id = acting_user_id
        self._actor_role = acting_role

    def create_user(self, username: str, full_name: str, password: str,
                    role: str = "USER", email: Optional[str] = None) -> dict:
        self._require_admin()
        if self._conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
            raise DuplicateUsernameError(f"Le nom d'utilisateur '{username}' est déjà pris.")
        valid, msg = is_strong_password(password)
        if not valid:
            raise ValueError(msg)
        self._conn.execute(
            """INSERT INTO users (username, full_name, email, password_hash, role,
               is_active, must_change_password) VALUES (?,?,?,?,?,1,1)""",
            (username, full_name, email, hash_password(password), role)
        )
        self._audit("USER_CREATED", f"user:{username}", f"Created {username} role={role}")
        row = self._conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        return dict(row)

    def update_user(self, user_id: int, full_name: Optional[str] = None,
                    email: Optional[str] = None, role: Optional[str] = None,
                    is_active: Optional[bool] = None) -> dict:
        self._require_admin()
        user = self._get_or_raise(user_id)
        updates = []
        params = []
        if full_name is not None:
            updates.append("full_name=?"); params.append(full_name)
        if email is not None:
            updates.append("email=?"); params.append(email)
        if role is not None:
            updates.append("role=?"); params.append(role)
        if is_active is not None:
            updates.append("is_active=?"); params.append(int(is_active))
        if updates:
            params.append(user_id)
            self._conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id=?", params)
            self._audit("USER_UPDATED", f"user:{user['username']}", f"Fields: {updates}")
        return dict(self._get_or_raise(user_id))

    def deactivate_user(self, user_id: int) -> None:
        self._require_admin()
        if user_id == self._actor_id:
            raise PermissionError("Vous ne pouvez pas désactiver votre propre compte.")
        user = self._get_or_raise(user_id)
        self._conn.execute("UPDATE users SET is_active=0 WHERE id=?", (user_id,))
        self._audit("USER_DELETED", f"user:{user['username']}", "Deactivated")

    def change_password(self, user_id: int, new_password: str,
                        current_password: Optional[str] = None) -> None:
        user = self._get_or_raise(user_id)
        is_self = user_id == self._actor_id
        is_admin = self._actor_role == "ADMIN"
        if is_self and not is_admin:
            if current_password is None:
                raise ValueError("Le mot de passe actuel est requis.")
            if not verify_password(current_password, user["password_hash"]):
                raise ValueError("Mot de passe actuel incorrect.")
        valid, msg = is_strong_password(new_password)
        if not valid:
            raise ValueError(msg)
        from datetime import UTC, datetime
        self._conn.execute(
            "UPDATE users SET password_hash=?, must_change_password=0, password_changed_at=? WHERE id=?",
            (hash_password(new_password), datetime.now(UTC).isoformat(), user_id)
        )
        self._audit("PASSWORD_CHANGED", f"user:{user['username']}", "Password changed")

    def list_users(self) -> list[dict]:
        self._require_admin()
        rows = self._conn.execute("SELECT * FROM users ORDER BY username").fetchall()
        return [dict(r) for r in rows]

    def _require_admin(self) -> None:
        if self._actor_role != "ADMIN":
            raise PermissionError("Opération réservée aux administrateurs.")

    def _get_or_raise(self, user_id: int) -> sqlite3.Row:
        row = self._conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if row is None:
            raise UserNotFoundError(f"Utilisateur id={user_id} introuvable.")
        return row

    def _audit(self, action: str, resource: str, details: str) -> None:
        self._conn.execute(
            "INSERT INTO audit_logs (user_id, action, resource, details, success) VALUES (?,?,?,?,1)",
            (self._actor_id, action, resource, details)
        )
