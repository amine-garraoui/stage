"""
Database layer — pure sqlite3, no ORM dependency.
Schema creation, connection management, and first-run bootstrap.
"""

from __future__ import annotations

import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Generator
import logging

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from config.settings import get_settings

logger = logging.getLogger(__name__)

DDL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS users (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    username            TEXT    NOT NULL UNIQUE,
    email               TEXT    UNIQUE,
    full_name           TEXT    NOT NULL,
    password_hash       TEXT    NOT NULL,
    role                TEXT    NOT NULL DEFAULT 'USER',
    is_active           INTEGER NOT NULL DEFAULT 1,
    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until        TEXT,
    last_login          TEXT,
    must_change_password INTEGER NOT NULL DEFAULT 0,
    password_changed_at TEXT,
    created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_sessions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token         TEXT    NOT NULL UNIQUE,
    ip_address    TEXT,
    user_agent    TEXT,
    expires_at    TEXT    NOT NULL,
    last_activity TEXT    NOT NULL,
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_user_sessions_token ON user_sessions(token);

CREATE TABLE IF NOT EXISTS audit_logs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER REFERENCES users(id) ON DELETE SET NULL,
    username      TEXT,
    action        TEXT    NOT NULL,
    resource      TEXT,
    details       TEXT,
    ip_address    TEXT,
    success       INTEGER NOT NULL DEFAULT 1,
    error_message TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_audit_logs_action     ON audit_logs(action);
CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id    ON audit_logs(user_id);

CREATE TABLE IF NOT EXISTS data_imports (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    imported_by       INTEGER REFERENCES users(id) ON DELETE SET NULL,
    original_filename TEXT    NOT NULL,
    stored_filename   TEXT    NOT NULL,
    file_hash         TEXT    NOT NULL,
    file_size_bytes   INTEGER NOT NULL,
    status            TEXT    NOT NULL DEFAULT 'PENDING',
    rows_processed    INTEGER,
    rows_imported     INTEGER NOT NULL DEFAULT 0,
    rows_rejected     INTEGER NOT NULL DEFAULT 0,
    period_start      TEXT,
    period_end        TEXT,
    error_details     TEXT,
    completed_at      TEXT,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_data_imports_file_hash ON data_imports(file_hash);

CREATE TABLE IF NOT EXISTS tickets (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id             INTEGER NOT NULL REFERENCES data_imports(id) ON DELETE CASCADE,
    ticket_ref            TEXT,
    opened_at             TEXT,
    closed_at             TEXT,
    status                TEXT,
    site                  TEXT,
    topic                 TEXT,
    sub_topic             TEXT,
    assignee              TEXT,
    requester             TEXT,
    satisfaction_score    REAL,
    survey_responded      INTEGER,
    resolution_time_hours REAL,
    opened_month          TEXT,
    closed_month          TEXT,
    created_at            TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_tickets_import_id    ON tickets(import_id);
CREATE INDEX IF NOT EXISTS ix_tickets_opened_month ON tickets(opened_month);
CREATE INDEX IF NOT EXISTS ix_tickets_site         ON tickets(site);
CREATE INDEX IF NOT EXISTS ix_tickets_topic        ON tickets(topic);

CREATE TABLE IF NOT EXISTS kpi_snapshots (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    year                        INTEGER NOT NULL,
    month                       INTEGER NOT NULL,
    scope                       TEXT    NOT NULL DEFAULT 'GLOBAL',
    tickets_opened              INTEGER NOT NULL DEFAULT 0,
    tickets_closed              INTEGER NOT NULL DEFAULT 0,
    tickets_opened_and_closed   INTEGER NOT NULL DEFAULT 0,
    tickets_open_eom            INTEGER NOT NULL DEFAULT 0,
    avg_resolution_hours        REAL,
    median_resolution_hours     REAL,
    p90_resolution_hours        REAL,
    avg_satisfaction            REAL,
    satisfaction_responses      INTEGER NOT NULL DEFAULT 0,
    satisfaction_eligible       INTEGER NOT NULL DEFAULT 0,
    participation_rate          REAL,
    performance_index           REAL,
    by_site                     TEXT,
    by_topic                    TEXT,
    created_at                  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at                  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(year, month, scope)
);
CREATE INDEX IF NOT EXISTS ix_kpi_snapshots_period ON kpi_snapshots(year, month);

CREATE TABLE IF NOT EXISTS forecast_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    metric          TEXT    NOT NULL,
    year            INTEGER NOT NULL,
    month           INTEGER NOT NULL,
    predicted_value REAL    NOT NULL,
    lower_bound     REAL    NOT NULL,
    upper_bound     REAL    NOT NULL,
    model_name      TEXT    NOT NULL,
    is_historical   INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(metric, year, month)
);

CREATE TABLE IF NOT EXISTS anomaly_records (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    year             INTEGER NOT NULL,
    month            INTEGER NOT NULL,
    anomaly_type     TEXT    NOT NULL,
    severity         TEXT    NOT NULL,
    scope            TEXT    NOT NULL DEFAULT 'GLOBAL',
    metric_name      TEXT    NOT NULL,
    observed_value   REAL    NOT NULL,
    baseline_value   REAL    NOT NULL,
    deviation_percent REAL   NOT NULL,
    z_score          REAL,
    explanation      TEXT    NOT NULL,
    is_acknowledged  INTEGER NOT NULL DEFAULT 0,
    acknowledged_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_anomaly_records_period   ON anomaly_records(year, month);
CREATE INDEX IF NOT EXISTS ix_anomaly_records_severity ON anomaly_records(severity);

CREATE TABLE IF NOT EXISTS executive_insights (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    year              INTEGER NOT NULL,
    month             INTEGER NOT NULL,
    summary_text      TEXT    NOT NULL,
    key_findings      TEXT    NOT NULL DEFAULT '[]',
    positive_trends   TEXT    NOT NULL DEFAULT '[]',
    critical_alerts   TEXT    NOT NULL DEFAULT '[]',
    risks             TEXT    NOT NULL DEFAULT '[]',
    recommendations   TEXT    NOT NULL DEFAULT '[]',
    performance_index REAL,
    generated_at      TEXT    NOT NULL,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(year, month)
);

CREATE TABLE IF NOT EXISTS app_settings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    key         TEXT UNIQUE NOT NULL,
    value       TEXT,
    description TEXT,
    updated_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _get_db_path() -> Path:
    return get_settings().database_path


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Yield a sqlite3 connection with row_factory=Row and WAL mode."""
    db_path = _get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), detect_types=sqlite3.PARSE_DECLTYPES, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create schema and bootstrap admin account."""
    db_path = _get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.executescript(DDL)
    conn.commit()
    conn.close()
    logger.info("Database schema initialised.")
    _seed_admin_if_empty()


def _seed_admin_if_empty() -> None:
    from src.auth.security import hash_password
    with get_db() as conn:
        row = conn.execute("SELECT COUNT(*) FROM users").fetchone()
        if row[0] == 0:
            conn.execute(
                """INSERT INTO users (username, full_name, email, password_hash, role, is_active, must_change_password)
                   VALUES (?, ?, ?, ?, 'ADMIN', 1, 1)""",
                ("admin", "System Administrator", "admin@rsi.local", hash_password("Admin@RSI2024!"))
            )
            logger.warning("Default admin created: admin / Admin@RSI2024! — CHANGE IMMEDIATELY.")
