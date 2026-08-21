"""Executive Insights Engine — sqlite3 version."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import UTC, datetime
from typing import Optional

logger = logging.getLogger(__name__)


def _prev(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


class InsightsEngine:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def generate_for_period(self, year: int, month: int) -> dict:
        snap = self._conn.execute(
            "SELECT * FROM kpi_snapshots WHERE year=? AND month=? AND scope='GLOBAL'",
            (year, month)
        ).fetchone()
        if snap is None:
            raise ValueError(f"Pas de snapshot KPI pour {year:04d}-{month:02d}.")
        snap = dict(snap)

        py, pm = _prev(year, month)
        prev = self._conn.execute(
            "SELECT * FROM kpi_snapshots WHERE year=? AND month=? AND scope='GLOBAL'",
            (py, pm)
        ).fetchone()
        prev = dict(prev) if prev else None

        anomalies = [dict(r) for r in self._conn.execute(
            "SELECT * FROM anomaly_records WHERE year=? AND month=?", (year, month)
        ).fetchall()]

        findings = self._findings(snap, prev)
        positives = self._positives(snap, prev)
        alerts = self._alerts(anomalies)
        risks = self._risks(snap, anomalies)
        recs = self._recommendations(snap, anomalies)
        summary = self._summary(snap, prev, anomalies)
        period_str = f"{year:04d}-{month:02d}"

        generated_at = datetime.now(UTC).isoformat()

        existing = self._conn.execute(
            "SELECT id FROM executive_insights WHERE year=? AND month=?", (year, month)
        ).fetchone()

        data = (json.dumps(findings), json.dumps(positives), json.dumps(alerts),
                json.dumps(risks), json.dumps(recs), summary,
                snap.get("performance_index"), generated_at, year, month)

        if existing:
            self._conn.execute(
                """UPDATE executive_insights SET key_findings=?, positive_trends=?,
                   critical_alerts=?, risks=?, recommendations=?, summary_text=?,
                   performance_index=?, generated_at=? WHERE year=? AND month=?""",
                data
            )
        else:
            self._conn.execute(
                """INSERT INTO executive_insights (key_findings, positive_trends, critical_alerts,
                   risks, recommendations, summary_text, performance_index, generated_at, year, month)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                data
            )
        logger.info(f"Insights generated for {period_str}.")
        return {"year": year, "month": month, "summary_text": summary,
                "key_findings": findings, "positive_trends": positives,
                "critical_alerts": alerts, "risks": risks, "recommendations": recs,
                "performance_index": snap.get("performance_index")}

    def _summary(self, snap: dict, prev: Optional[dict], anomalies: list) -> str:
        period = f"{snap['year']:04d}-{snap['month']:02d}"
        perf = f"{snap['performance_index']:.1f}/100" if snap.get("performance_index") else "N/D"
        sat = f"{snap['avg_satisfaction']:.2f}/5" if snap.get("avg_satisfaction") else "N/D"
        res = f"{snap['avg_resolution_hours']:.1f}h" if snap.get("avg_resolution_hours") else "N/D"
        critical = sum(1 for a in anomalies if a["severity"] == "CRITICAL")
        trend = ""
        if prev and prev.get("tickets_opened") and snap.get("tickets_opened"):
            delta = ((snap["tickets_opened"] - prev["tickets_opened"]) / prev["tickets_opened"]) * 100
            trend = f" Le volume de tickets a {'augmenté' if delta > 0 else 'diminué'} de {abs(delta):.1f}%."
        alert = f" ⚠️ {critical} anomalie(s) critique(s) détectée(s)." if critical > 0 else ""
        return (f"Performance IT Support RSI — Période : {period}. Indice de Performance : {perf}. "
                f"Satisfaction : {sat}. Délai moyen : {res}.{trend}{alert}").strip()

    def _findings(self, snap: dict, prev: Optional[dict]) -> list[str]:
        f = [f"Volume : {snap['tickets_opened']} ouverts, {snap['tickets_closed']} fermés, "
             f"{snap['tickets_open_eom']} en cours (EOM)."]
        if snap.get("avg_satisfaction"):
            pr = f" (participation : {snap['participation_rate']:.1f}%)" if snap.get("participation_rate") else ""
            f.append(f"Satisfaction : {snap['avg_satisfaction']:.2f}/5{pr}.")
        if snap.get("avg_resolution_hours"):
            f.append(f"Délai moyen : {snap['avg_resolution_hours']:.1f}h.")
        if snap.get("performance_index"):
            f.append(f"Indice Performance RSI : {snap['performance_index']:.1f}/100.")
        if prev and prev.get("tickets_opened"):
            delta = snap["tickets_opened"] - prev["tickets_opened"]
            f.append(f"Évolution vs mois précédent : {delta:+d} tickets.")
        return f

    def _positives(self, snap: dict, prev: Optional[dict]) -> list[str]:
        p = []
        if prev:
            if snap.get("avg_satisfaction") and prev.get("avg_satisfaction") and \
               snap["avg_satisfaction"] > prev["avg_satisfaction"]:
                p.append(f"Satisfaction en hausse : {prev['avg_satisfaction']:.2f} → {snap['avg_satisfaction']:.2f}/5.")
            if snap.get("avg_resolution_hours") and prev.get("avg_resolution_hours") and \
               snap["avg_resolution_hours"] < prev["avg_resolution_hours"]:
                p.append(f"Délai réduit : {prev['avg_resolution_hours']:.1f}h → {snap['avg_resolution_hours']:.1f}h.")
        if snap.get("tickets_closed") and snap.get("tickets_opened") and \
           snap["tickets_closed"] >= snap["tickets_opened"]:
            p.append("Backlog maîtrisé : tickets fermés ≥ tickets ouverts.")
        return p or ["Aucune tendance positive significative ce mois-ci."]

    def _alerts(self, anomalies: list) -> list[str]:
        alerts = [a["explanation"] for a in anomalies if a["severity"] in ("CRITICAL", "HIGH")]
        return alerts or ["Aucune alerte critique ce mois-ci."]

    def _risks(self, snap: dict, anomalies: list) -> list[str]:
        r = []
        if snap.get("participation_rate") and snap["participation_rate"] < 30:
            r.append(f"Taux de participation faible ({snap['participation_rate']:.1f}%) — données peu représentatives.")
        if snap.get("avg_resolution_hours") and snap["avg_resolution_hours"] > 120:
            r.append(f"Délai critique ({snap['avg_resolution_hours']:.1f}h) — risque de dépassement SLA.")
        if snap.get("tickets_open_eom") and snap.get("tickets_opened") and \
           snap["tickets_open_eom"] > snap["tickets_opened"]:
            r.append(f"Backlog important : {snap['tickets_open_eom']} tickets en attente.")
        return r or ["Aucun risque majeur identifié."]

    def _recommendations(self, snap: dict, anomalies: list) -> list[str]:
        r = []
        if snap.get("participation_rate") and snap["participation_rate"] < 50:
            r.append("Renforcer les campagnes de sensibilisation aux enquêtes de satisfaction.")
        if snap.get("avg_resolution_hours") and snap["avg_resolution_hours"] > 72:
            r.append("Analyser les tickets à délai élevé et identifier les goulots d'étranglement.")
        site_anom = [a for a in anomalies if a["anomaly_type"] == "SITE_ANOMALY"]
        if site_anom:
            r.append(f"Investiguer les sites anormaux : {', '.join({a['scope'] for a in site_anom[:3]})}.")
        topic_anom = [a for a in anomalies if a["anomaly_type"] == "TOPIC_ANOMALY"]
        if topic_anom:
            r.append(f"Planifier des actions sur les catégories à croissance : {', '.join({a['scope'] for a in topic_anom[:3]})}.")
        return r or ["Maintenir le niveau de performance actuel."]
