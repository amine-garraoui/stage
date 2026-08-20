"""
KPI Engine — pure Python + pandas + numpy, no SQLAlchemy.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

PERF_INDEX_WEIGHTS = {
    "satisfaction": 0.40,
    "resolution_time": 0.30,
    "closure_rate": 0.20,
    "participation_rate": 0.10,
}
RESOLUTION_TARGET_HOURS = 72.0
RESOLUTION_MAX_HOURS = 336.0


class KpiEngine:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def recalculate_all(self) -> int:
        df = self._load_tickets()
        if df.empty:
            return 0
        months = sorted(df["opened_month"].dropna().unique().tolist())
        for m in months:
            year, month = (int(p) for p in m.split("-"))
            self._write_snapshot(year, month, df)
        logger.info(f"KPI recalculation: {len(months)} snapshots.")
        return len(months)

    def recalculate_month(self, year: int, month: int) -> None:
        df = self._load_tickets()
        self._write_snapshot(year, month, df)

    def get_monthly_dataframe(self) -> pd.DataFrame:
        rows = self._conn.execute(
            """SELECT year, month, tickets_opened, tickets_closed,
                      tickets_opened_and_closed, tickets_open_eom,
                      avg_resolution_hours, median_resolution_hours, p90_resolution_hours,
                      avg_satisfaction, participation_rate, performance_index,
                      by_site, by_topic
               FROM kpi_snapshots WHERE scope='GLOBAL'
               ORDER BY year, month"""
        ).fetchall()
        if not rows:
            return pd.DataFrame()
        records = []
        for r in rows:
            d = dict(r)
            d["period"] = f"{d['year']:04d}-{d['month']:02d}"
            d["by_site"] = json.loads(d["by_site"]) if d.get("by_site") else {}
            d["by_topic"] = json.loads(d["by_topic"]) if d.get("by_topic") else {}
            records.append(d)
        return pd.DataFrame(records)

    def _load_tickets(self) -> pd.DataFrame:
        rows = self._conn.execute(
            """SELECT opened_month, closed_month, site, topic,
                      satisfaction_score, survey_responded, resolution_time_hours
               FROM tickets"""
        ).fetchall()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([dict(r) for r in rows])

    def _write_snapshot(self, year: int, month: int, df: pd.DataFrame) -> None:
        period = f"{year:04d}-{month:02d}"
        opened = df[df["opened_month"] == period]
        closed = df[df["closed_month"] == period]
        same = df[(df["opened_month"] == period) & (df["closed_month"] == period)]
        eom = df[
            (df["opened_month"] <= period) &
            (df["closed_month"].isna() | (df["closed_month"] > period))
        ]

        res = closed["resolution_time_hours"].dropna()
        avg_res = float(res.mean()) if not res.empty else None
        med_res = float(res.median()) if not res.empty else None
        p90_res = float(np.percentile(res, 90)) if not res.empty else None

        sat = closed["satisfaction_score"].dropna()
        avg_sat = float(sat.mean()) if not sat.empty else None
        responses = int(closed["survey_responded"].sum()) if "survey_responded" in closed.columns else 0
        eligible = len(closed)
        participation = (responses / eligible * 100) if eligible > 0 else None

        perf = self._perf_index(avg_sat, avg_res, len(opened), len(closed), participation)

        by_site = json.dumps(self._breakdown(opened, "site"))
        by_topic = json.dumps(self._breakdown(opened, "topic"))

        existing = self._conn.execute(
            "SELECT id FROM kpi_snapshots WHERE year=? AND month=? AND scope='GLOBAL'",
            (year, month)
        ).fetchone()

        if existing:
            self._conn.execute(
                """UPDATE kpi_snapshots SET
                   tickets_opened=?, tickets_closed=?, tickets_opened_and_closed=?,
                   tickets_open_eom=?, avg_resolution_hours=?, median_resolution_hours=?,
                   p90_resolution_hours=?, avg_satisfaction=?, satisfaction_responses=?,
                   satisfaction_eligible=?, participation_rate=?, performance_index=?,
                   by_site=?, by_topic=?, updated_at=datetime('now')
                   WHERE year=? AND month=? AND scope='GLOBAL'""",
                (len(opened), len(closed), len(same), len(eom),
                 avg_res, med_res, p90_res, avg_sat, responses,
                 eligible, participation, perf, by_site, by_topic, year, month)
            )
        else:
            self._conn.execute(
                """INSERT INTO kpi_snapshots
                   (year, month, scope, tickets_opened, tickets_closed,
                    tickets_opened_and_closed, tickets_open_eom,
                    avg_resolution_hours, median_resolution_hours, p90_resolution_hours,
                    avg_satisfaction, satisfaction_responses, satisfaction_eligible,
                    participation_rate, performance_index, by_site, by_topic)
                   VALUES ('GLOBAL',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (year, month, "GLOBAL", len(opened), len(closed), len(same), len(eom),
                 avg_res, med_res, p90_res, avg_sat, responses,
                 eligible, participation, perf, by_site, by_topic)
            )

    def _perf_index(self, avg_sat, avg_res, n_open, n_closed, participation) -> Optional[float]:
        if n_open == 0:
            return None
        sat_score = (avg_sat / 5.0) * 100 if avg_sat else 50.0
        if avg_res is not None:
            if avg_res <= RESOLUTION_TARGET_HOURS:
                res_score = 100.0
            elif avg_res >= RESOLUTION_MAX_HOURS:
                res_score = 0.0
            else:
                res_score = max(0.0, (1 - (avg_res - RESOLUTION_TARGET_HOURS) /
                                      (RESOLUTION_MAX_HOURS - RESOLUTION_TARGET_HOURS)) * 100)
        else:
            res_score = 50.0
        closure_score = min(100.0, (n_closed / n_open) * 100)
        part_score = min(100.0, participation or 0.0)
        index = (PERF_INDEX_WEIGHTS["satisfaction"] * sat_score +
                 PERF_INDEX_WEIGHTS["resolution_time"] * res_score +
                 PERF_INDEX_WEIGHTS["closure_rate"] * closure_score +
                 PERF_INDEX_WEIGHTS["participation_rate"] * part_score)
        return round(index, 1)

    @staticmethod
    def _breakdown(df: pd.DataFrame, col: str) -> dict[str, int]:
        if df.empty or col not in df.columns:
            return {}
        return {str(k): int(v) for k, v in df[col].value_counts().items()}
