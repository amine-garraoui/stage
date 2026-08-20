"""
Security utilities using stdlib PBKDF2 + python-jose (JWT).
No external bcrypt dependency required.

Password hashing: PBKDF2-HMAC-SHA256, 600000 iterations (NIST 2023 recommendation).
Format: pbkdf2$<iterations>$<salt_hex>$<hash_hex>
"""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt

from config.settings import get_settings

_ITERATIONS = 600_000
_HASH_NAME = "sha256"
_SALT_BYTES = 32


def hash_password(plain: str) -> str:
    """Hash plain-text password with PBKDF2-HMAC-SHA256."""
    salt = os.urandom(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(_HASH_NAME, plain.encode("utf-8"), salt, _ITERATIONS)
    return f"pbkdf2${_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(plain: str, hashed: str) -> bool:
    """Verify password against stored PBKDF2 hash. Constant-time comparison."""
    try:
        parts = hashed.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2":
            return False
        _, iterations, salt_hex, stored_hex = parts
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac(_HASH_NAME, plain.encode("utf-8"), salt, int(iterations))
        return secrets.compare_digest(dk.hex(), stored_hex)
    except Exception:
        return False


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def create_access_token(subject: str, role: str, session_token: str,
                        expires_delta: timedelta | None = None) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    payload: dict[str, Any] = {
        "sub": subject, "role": role, "sid": session_token,
        "iat": now, "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any] | None:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None


def is_strong_password(password: str) -> tuple[bool, str]:
    if len(password) < 10:
        return False, "Le mot de passe doit contenir au moins 10 caractères."
    if not any(c.isupper() for c in password):
        return False, "Le mot de passe doit contenir au moins une majuscule."
    if not any(c.islower() for c in password):
        return False, "Le mot de passe doit contenir au moins une minuscule."
    if not any(c.isdigit() for c in password):
        return False, "Le mot de passe doit contenir au moins un chiffre."
    special = set("!@#$%^&*()_+-=[]{}|;':\",./<>?")
    if not any(c in special for c in password):
        return False, "Le mot de passe doit contenir au moins un caractère spécial."
    return True, ""
