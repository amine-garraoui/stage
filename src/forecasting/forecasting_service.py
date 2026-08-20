"""
Forecasting using numpy linear/polynomial regression only.
No scipy/statsmodels/sklearn required.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)
METRICS = ["tickets_opened", "avg_resolution_hours", "avg_satisfaction"]


def _next_periods(year: int, month: int, n: int) -> list[tuple[int, int]]:
    result = []
    y, m = year, month
    for _ in range(n):
        m += 1
        if m > 12:
            m = 1
            y += 1
        result.append((y, m))
    return result


def _z_for_ci(ci: float = 0.95) -> float:
    # Approximate z-score without scipy
    z_table = {0.90: 1.645, 0.95: 1.960, 0.99: 2.576}
    return z_table.get(ci, 1.960)


class ForecastingService:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def run_all(self, kpi_df: pd.DataFrame, horizon: int = 6) -> int:
        if kpi_df.empty:
            return 0
        count = 0
        for metric in METRICS:
            if metric not in kpi_df.columns:
                continue
            series = kpi_df[metric].dropna()
            if len(series) < 3:
                continue
            try:
                periods = kpi_df.iloc[series.index]["period"].tolist()
                self._forecast_and_persist(metric, series.values.tolist(), periods, horizon)
                count += horizon
            except Exception as exc:
                logger.error(f"Forecast error for {metric}: {exc}")
        return count

    def get_forecast_df(self, metric: str) -> pd.DataFrame:
        rows = self._conn.execute(
            """SELECT metric, year, month, predicted_value, lower_bound, upper_bound,
                      model_name, is_historical
               FROM forecast_results WHERE metric=?
               ORDER BY year, month""",
            (metric,)
        ).fetchall()
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([{
            "period": f"{r['year']:04d}-{r['month']:02d}",
            "year": r["year"], "month": r["month"],
            "value": r["predicted_value"],
            "lower": r["lower_bound"],
            "upper": r["upper_bound"],
            "model": r["model_name"],
            "is_historical": bool(r["is_historical"]),
        } for r in rows])

    def _forecast_and_persist(self, metric: str, values: list[float],
                               periods: list[str], horizon: int) -> None:
        n = len(values)
        y = np.array(values, dtype=float)
        X = np.arange(n)

        # Polynomial degree 2 if enough data, else linear
        degree = 2 if n >= 6 else 1
        coeffs = np.polyfit(X, y, degree)
        poly = np.poly1d(coeffs)

        X_all = np.arange(n + horizon)
        preds = poly(X_all)

        # Residual std for confidence interval
        residuals = y - poly(X)
        std = float(np.std(residuals)) if len(residuals) > 1 else float(np.std(y) * 0.1)
        z = _z_for_ci()
        model_name = f"Polynomial(deg={degree})"

        # Historical
        for i, period in enumerate(periods):
            yr, mo = int(period[:4]), int(period[5:7])
            margin = z * std * np.sqrt(1 + i / n)
            self._upsert(metric, yr, mo, float(preds[i]),
                         float(preds[i] - margin), float(preds[i] + margin),
                         model_name, is_historical=1)

        # Future
        last_period = periods[-1]
        last_year, last_month = int(last_period[:4]), int(last_period[5:7])
        for j, (yr, mo) in enumerate(_next_periods(last_year, last_month, horizon)):
            idx = n + j
            margin = z * std * np.sqrt(1 + idx / n)
            self._upsert(metric, yr, mo, float(preds[idx]),
                         float(preds[idx] - margin), float(preds[idx] + margin),
                         model_name, is_historical=0)

    def _upsert(self, metric, year, month, predicted, lower, upper, model, is_historical):
        existing = self._conn.execute(
            "SELECT id FROM forecast_results WHERE metric=? AND year=? AND month=?",
            (metric, year, month)
        ).fetchone()
        if existing:
            self._conn.execute(
                """UPDATE forecast_results SET predicted_value=?, lower_bound=?,
                   upper_bound=?, model_name=?, is_historical=? WHERE id=?""",
                (predicted, lower, upper, model, is_historical, existing["id"])
            )
        else:
            self._conn.execute(
                """INSERT INTO forecast_results (metric, year, month, predicted_value,
                   lower_bound, upper_bound, model_name, is_historical) VALUES (?,?,?,?,?,?,?,?)""",
                (metric, year, month, predicted, lower, upper, model, is_historical)
            )
