"""
ASKit file importer using pandas + sqlite3.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from config.settings import get_settings

logger = logging.getLogger(__name__)

COLUMN_MAP: dict[str, str] = {
    "numéro": "ticket_ref", "numero": "ticket_ref",
    "référence": "ticket_ref", "reference": "ticket_ref", "ticket": "ticket_ref",
    "date d'ouverture": "opened_at", "date ouverture": "opened_at",
    "date de création": "opened_at", "date de fermeture": "closed_at",
    "date fermeture": "closed_at", "statut": "status", "état": "status", "etat": "status",
    "site": "site", "localisation": "site",
    "catégorie": "topic", "categorie": "topic", "sujet": "topic", "topic": "topic",
    "sous-catégorie": "sub_topic", "sous-categorie": "sub_topic",
    "technicien": "assignee", "assigné à": "assignee", "assigne a": "assignee",
    "demandeur": "requester", "utilisateur": "requester",
    "satisfaction": "satisfaction_score", "note de satisfaction": "satisfaction_score",
    "avis": "satisfaction_score",
    "réponse enquête": "survey_responded", "reponse enquete": "survey_responded",
    "durée résolution (h)": "resolution_time_hours",
    "duree resolution": "resolution_time_hours", "temps résolution": "resolution_time_hours",
}


class ImportError(Exception):
    pass


class DuplicateImportError(ImportError):
    pass


def _sha256(path: Path) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _parse_date(val: object) -> Optional[str]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, (datetime, pd.Timestamp)):
        if isinstance(val, pd.Timestamp):
            val = val.to_pydatetime()
        return val.replace(tzinfo=UTC).isoformat()
    try:
        parsed = pd.to_datetime(str(val), dayfirst=True, errors="raise")
        return parsed.to_pydatetime().replace(tzinfo=UTC).isoformat()
    except Exception:
        return None


def _month(iso: Optional[str]) -> Optional[str]:
    if not iso:
        return None
    return iso[:7]


def _parse_sat(val: object) -> Optional[float]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        f = float(str(val).replace(",", "."))
        if f > 5:
            f /= 2.0
        return round(max(0.0, min(5.0, f)), 2)
    except (ValueError, TypeError):
        return None


class AskitImporter:
    def __init__(self, conn: sqlite3.Connection, imported_by_user_id: int) -> None:
        self._conn = conn
        self._user_id = imported_by_user_id
        self._settings = get_settings()

    def run(self, file_path: Path, original_filename: str) -> dict:
        suffix = file_path.suffix.lower()
        if suffix not in self._settings.allowed_extensions:
            raise ImportError(f"Type de fichier non autorisé: {suffix}")
        if file_path.stat().st_size > self._settings.max_upload_size_bytes:
            raise ImportError("Fichier trop volumineux.")
        if file_path.stat().st_size == 0:
            raise ImportError("Fichier vide.")

        file_hash = _sha256(file_path)
        existing = self._conn.execute(
            "SELECT id, created_at FROM data_imports WHERE file_hash=? AND status='COMPLETED'",
            (file_hash,)
        ).fetchone()
        if existing:
            raise DuplicateImportError(
                f"Ce fichier a déjà été importé (Import #{existing['id']})."
            )

        stored_name = f"{uuid.uuid4().hex}_{original_filename}"
        stored_path = self._settings.upload_dir / stored_name
        shutil.copy2(file_path, stored_path)

        self._conn.execute(
            """INSERT INTO data_imports (imported_by, original_filename, stored_filename,
               file_hash, file_size_bytes, status) VALUES (?,?,?,?,?,?)""",
            (self._user_id, original_filename, stored_name,
             file_hash, file_path.stat().st_size, "PROCESSING")
        )
        import_id = self._conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        self._audit("IMPORT_STARTED", f"import:{import_id}", f"File: {original_filename}")

        try:
            df = self._read_file(stored_path)
            df = self._normalise_columns(df)
            imported, rejected = self._insert_tickets(df, import_id)

            period_start = None
            period_end = None
            dates_col = [r[0] for r in self._conn.execute(
                "SELECT opened_at FROM tickets WHERE import_id=? AND opened_at IS NOT NULL", (import_id,)
            ).fetchall()]
            if dates_col:
                period_start = min(dates_col)
                period_end = max(dates_col)

            self._conn.execute(
                """UPDATE data_imports SET status='COMPLETED', rows_processed=?,
                   rows_imported=?, rows_rejected=?, period_start=?, period_end=?,
                   completed_at=datetime('now') WHERE id=?""",
                (len(df), imported, rejected, period_start, period_end, import_id)
            )
            self._audit("IMPORT_COMPLETED", f"import:{import_id}",
                        f"{imported} rows imported, {rejected} rejected")
            logger.info(f"Import #{import_id}: {imported} imported, {rejected} rejected.")
            return dict(self._conn.execute(
                "SELECT * FROM data_imports WHERE id=?", (import_id,)
            ).fetchone())

        except Exception as exc:
            self._conn.execute(
                "UPDATE data_imports SET status='FAILED', error_details=? WHERE id=?",
                (str(exc), import_id)
            )
            self._audit("IMPORT_FAILED", f"import:{import_id}", str(exc))
            raise ImportError(str(exc)) from exc

    def _read_file(self, path: Path) -> pd.DataFrame:
        suffix = path.suffix.lower()
        try:
            if suffix in (".xlsx", ".xls"):
                return pd.read_excel(path, dtype=str, engine="openpyxl")
            elif suffix == ".csv":
                for enc in ("utf-8-sig", "utf-8", "latin-1"):
                    try:
                        return pd.read_csv(path, dtype=str, encoding=enc, sep=None, engine="python")
                    except UnicodeDecodeError:
                        continue
                raise ImportError("Encodage CSV non supporté.")
            else:
                raise ImportError(f"Format non supporté: {suffix}")
        except ImportError:
            raise
        except Exception as exc:
            raise ImportError(f"Erreur de lecture: {exc}") from exc

    def _normalise_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        rename = {}
        for col in df.columns:
            key = str(col).strip().lower()
            if key in COLUMN_MAP:
                rename[col] = COLUMN_MAP[key]
        return df.rename(columns=rename)

    def _insert_tickets(self, df: pd.DataFrame, import_id: int) -> tuple[int, int]:
        imported = 0
        rejected = 0
        for _, row in df.iterrows():
            try:
                opened_at = _parse_date(row.get("opened_at"))
                closed_at = _parse_date(row.get("closed_at"))
                res_hours: Optional[float] = None
                raw_res = row.get("resolution_time_hours")
                if raw_res and not pd.isna(raw_res):
                    try:
                        res_hours = float(str(raw_res).replace(",", "."))
                    except (ValueError, TypeError):
                        pass
                elif opened_at and closed_at:
                    from datetime import datetime as dt
                    o = dt.fromisoformat(opened_at)
                    c = dt.fromisoformat(closed_at)
                    if c > o:
                        res_hours = round((c - o).total_seconds() / 3600, 2)

                sat = _parse_sat(row.get("satisfaction_score"))
                survey_val = row.get("survey_responded")
                if survey_val and not (isinstance(survey_val, float) and pd.isna(survey_val)):
                    survey = int(str(survey_val).strip().lower() in
                                 ("oui", "yes", "true", "1", "répondu", "repondu"))
                else:
                    survey = 1 if sat is not None else 0

                self._conn.execute(
                    """INSERT INTO tickets (import_id, ticket_ref, opened_at, closed_at,
                       status, site, topic, sub_topic, assignee, requester,
                       satisfaction_score, survey_responded, resolution_time_hours,
                       opened_month, closed_month) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (import_id,
                     str(row.get("ticket_ref", "") or "").strip() or None,
                     opened_at, closed_at,
                     str(row.get("status", "") or "").strip() or None,
                     str(row.get("site", "") or "").strip() or None,
                     str(row.get("topic", "") or "").strip() or None,
                     str(row.get("sub_topic", "") or "").strip() or None,
                     str(row.get("assignee", "") or "").strip() or None,
                     str(row.get("requester", "") or "").strip() or None,
                     sat, survey, res_hours,
                     _month(opened_at), _month(closed_at))
                )
                imported += 1
            except Exception as exc:
                logger.debug(f"Row rejected: {exc}")
                rejected += 1
        return imported, rejected

    def _audit(self, action: str, resource: str, details: str) -> None:
        self._conn.execute(
            "INSERT INTO audit_logs (user_id, action, resource, details, success) VALUES (?,?,?,?,1)",
            (self._user_id, action, resource, details)
        )
