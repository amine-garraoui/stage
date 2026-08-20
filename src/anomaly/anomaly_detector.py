"""Anomaly detection using numpy — no scipy/statsmodels required."""

from __future__ import annotations

import logging
import sqlite3
from collections import defaultdict
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def _classify_severity(pct: float) -> str:
    if pct >= 75: return "CRITICAL"
    if pct >= 50: return "HIGH"
    if pct >= 25: return "MEDIUM"
    return "LOW"


class AnomalyDetector:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def detect_all(self, kpi_df: pd.DataFrame) -> list[dict]:
        if kpi_df.empty or len(kpi_df) < 3:
            return []

        # Clear unacknowledged
        self._conn.execute(
            "DELETE FROM anomaly_records WHERE is_acknowledged=0"
        )

        anomalies: list[dict] = []
        anomalies.extend(self._detect_metric(kpi_df, "tickets_opened", "TICKET_SPIKE", "high",
            "Le volume de tickets ouverts en {period} était de {obs:.0f}, "
            "soit {dev:+.1f}% par rapport à la moyenne des 6 derniers mois ({base:.0f})."))
        anomalies.extend(self._detect_metric(kpi_df, "avg_satisfaction", "SATISFACTION_DROP", "low",
            "Le score de satisfaction en {period} était de {obs:.2f}/5, "
            "soit {dev:+.1f}% par rapport à la référence ({base:.2f}/5)."))
        anomalies.extend(self._detect_metric(kpi_df, "avg_resolution_hours", "RESOLUTION_DELAY", "high",
            "Le délai moyen de résolution en {period} était de {obs:.1f}h, "
            "soit {dev:+.1f}% au-dessus de la référence ({base:.1f}h)."))
        anomalies.extend(self._detect_breakdown("by_site", "SITE_ANOMALY"))
        anomalies.extend(self._detect_breakdown("by_topic", "TOPIC_ANOMALY"))

        for a in anomalies:
            self._conn.execute(
                """INSERT INTO anomaly_records (year, month, anomaly_type, severity, scope,
                   metric_name, observed_value, baseline_value, deviation_percent,
                   z_score, explanation) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (a["year"], a["month"], a["anomaly_type"], a["severity"],
                 a["scope"], a["metric_name"], a["observed_value"],
                 a["baseline_value"], a["deviation_percent"],
                 a.get("z_score"), a["explanation"])
            )
        logger.info(f"Anomaly detection: {len(anomalies)} found.")
        return anomalies

    def _detect_metric(self, df, col, atype, direction, template) -> list[dict]:
        if col not in df.columns:
            return []
        results = []
        vals = df[col].dropna().values.astype(float)
        if len(vals) < 3:
            return []
        from config.settings import get_settings
        settings = get_settings()
        thresh_pct = settings.anomaly_spike_percent
        thresh_z = settings.anomaly_zscore_threshold

        for i in range(2, len(vals)):
            window = vals[max(0, i-6):i]
            base = float(np.mean(window))
            obs = float(vals[i])
            if base == 0:
                continue
            dev = ((obs - base) / base) * 100
            triggered = (direction == "high" and dev >= thresh_pct) or \
                        (direction == "low" and dev <= -thresh_pct)
            if not triggered:
                continue
            std = float(np.std(window)) if len(window) > 1 else 0.0
            z = float((obs - base) / std) if std > 0 else 0.0
            if abs(z) < thresh_z:
                continue
            row = df.dropna(subset=[col]).iloc[i]
            period = f"{int(row['year']):04d}-{int(row['month']):02d}"
            results.append({
                "year": int(row["year"]), "month": int(row["month"]),
                "anomaly_type": atype, "severity": _classify_severity(abs(dev)),
                "scope": "GLOBAL", "metric_name": col,
                "observed_value": obs, "baseline_value": base,
                "deviation_percent": dev, "z_score": z,
                "explanation": template.format(period=period, obs=obs, base=base, dev=dev),
            })
        return results

    def _detect_breakdown(self, col: str, atype: str) -> list[dict]:
        rows = self._conn.execute(
            f"SELECT year, month, {col} FROM kpi_snapshots WHERE scope='GLOBAL' ORDER BY year, month"
        ).fetchall()
        import json
        series_map: dict[str, list[tuple[int, int, int]]] = defaultdict(list)
        for r in rows:
            data = json.loads(r[col]) if r[col] else {}
            for key, cnt in data.items():
                series_map[key].append((r["year"], r["month"], int(cnt)))

        results = []
        from config.settings import get_settings
        thresh = get_settings().anomaly_spike_percent
        for key, data in series_map.items():
            if len(data) < 3:
                continue
            vals = [d[2] for d in data]
            last = data[-1]
            base = float(np.mean(vals[:-1][-6:]))
            if base == 0:
                continue
            obs = float(last[2])
            dev = ((obs - base) / base) * 100
            if abs(dev) < thresh:
                continue
            period = f"{last[0]:04d}-{last[1]:02d}"
            label = "site" if col == "by_site" else "catégorie"
            results.append({
                "year": last[0], "month": last[1],
                "anomaly_type": atype, "severity": _classify_severity(abs(dev)),
                "scope": key, "metric_name": "tickets_opened",
                "observed_value": obs, "baseline_value": base,
                "deviation_percent": dev, "z_score": None,
                "explanation": (
                    f"Le {label} « {key} » a enregistré {obs:.0f} tickets en {period}, "
                    f"soit {dev:+.1f}% par rapport à la moyenne de référence ({base:.0f})."
                ),
            })
        return results
