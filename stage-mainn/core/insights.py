from __future__ import annotations

import pandas as pd

from core import kpi


def quality_report(df: pd.DataFrame, required_columns: list[str]) -> dict[str, object]:
    missing = [column for column in required_columns if column not in df.columns]
    return {
        "ok": not missing,
        "missing_columns": missing,
        "row_count": int(len(df)),
    }


def generate_month_insights(
    df: pd.DataFrame,
    mois: str,
    dmt_threshold_days: float = 3.0,
    satisfaction_threshold: float = 3.5,
) -> list[dict[str, str]]:
    result = kpi.calculate_month_kpi(df, mois)
    insights: list[dict[str, str]] = []

    if result.delai_moyen_jours is not None and result.delai_moyen_jours > dmt_threshold_days:
        insights.append(
            {
                "level": "red",
                "title": "DMT critique",
                "message": (
                    f"Le delai moyen de traitement est de {result.delai_moyen_jours:.2f} jours, "
                    f"au-dessus du seuil de {dmt_threshold_days:.1f} jours."
                ),
            }
        )

    satisfaction = result.satisfaction.satisfaction_globale
    if satisfaction is not None and satisfaction < satisfaction_threshold:
        insights.append(
            {
                "level": "red",
                "title": "Satisfaction faible",
                "message": (
                    f"La satisfaction moyenne est de {satisfaction:.2f}/5, "
                    f"sous le seuil de {satisfaction_threshold:.1f}/5."
                ),
            }
        )

    if not insights:
        insights.append(
            {
                "level": "green",
                "title": "Situation stable",
                "message": "Aucune alerte critique detectee sur les seuils DMT et satisfaction.",
            }
        )

    return insights

