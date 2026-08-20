"""
Application settings — pure stdlib + pydantic, no external settings library.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


class Settings:
    app_name: str = "RSI Sagemcom KPI Platform"
    app_version: str = "1.0.0"

    # Database
    database_path: Path = Path(_env("DATABASE_PATH", "./data/db/rsi_kpi.db"))

    # Security
    secret_key: str = _env("SECRET_KEY", secrets.token_hex(32))
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = int(_env("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
    session_idle_timeout_minutes: int = int(_env("SESSION_IDLE_TIMEOUT_MINUTES", "60"))
    max_login_attempts: int = int(_env("MAX_LOGIN_ATTEMPTS", "5"))
    lockout_duration_minutes: int = int(_env("LOCKOUT_DURATION_MINUTES", "30"))
    bcrypt_rounds: int = int(_env("BCRYPT_ROUNDS", "12"))

    # Files
    upload_dir: Path = Path(_env("UPLOAD_DIR", "./data/uploads"))
    export_dir: Path = Path(_env("EXPORT_DIR", "./data/exports"))
    max_upload_size_mb: int = int(_env("MAX_UPLOAD_SIZE_MB", "50"))
    allowed_extensions: tuple[str, ...] = (".xlsx", ".xls", ".csv")

    # Logging
    log_level: str = _env("LOG_LEVEL", "INFO")
    log_dir: Path = Path(_env("LOG_DIR", "./logs"))

    # Forecasting
    forecast_horizon_months: int = int(_env("FORECAST_HORIZON_MONTHS", "6"))
    min_history_months: int = int(_env("MIN_HISTORY_MONTHS", "3"))
    confidence_interval: float = float(_env("CONFIDENCE_INTERVAL", "0.95"))

    # Anomaly
    anomaly_zscore_threshold: float = float(_env("ANOMALY_ZSCORE_THRESHOLD", "2.0"))
    anomaly_spike_percent: float = float(_env("ANOMALY_SPIKE_PERCENT", "25.0"))

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    def ensure_directories(self) -> None:
        for d in (self.upload_dir, self.export_dir, self.log_dir, self.database_path.parent):
            d.mkdir(parents=True, exist_ok=True)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        # Load .env manually if present
        env_file = Path(".env")
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())
        _settings = Settings()
        _settings.ensure_directories()
    return _settings
