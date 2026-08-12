import pandas as pd


def compare_months(summary: pd.DataFrame, mois: str) -> dict:
    if summary.empty or mois not in set(summary["mois"]):
        return {}

    current = summary[summary["mois"].eq(mois)].iloc[0]
    months = sorted(summary["mois"].astype(str).tolist())
    index = months.index(mois)
    if index == 0:
        return {"mois": mois, "previous_month": None, "metrics": {}}

    previous_month = months[index - 1]
    previous = summary[summary["mois"].eq(previous_month)].iloc[0]
    metrics = {}
    for column in ["total_ouverts", "total_fermes", "actifs_fin_mois", "delai_moyen_jours", "satisfaction_moyenne"]:
        cur = current[column]
        prev = previous[column]
        if pd.isna(cur) or pd.isna(prev) or prev == 0:
            variation = None
        else:
            variation = float((cur - prev) / prev * 100)
        metrics[column] = {
            "current": None if pd.isna(cur) else float(cur),
            "previous": None if pd.isna(prev) else float(prev),
            "variation_percent": variation,
            "trend": "up" if variation is not None and variation > 0 else "down" if variation is not None and variation < 0 else "flat",
        }

    return {"mois": mois, "previous_month": previous_month, "metrics": metrics}


def detect_anomalies(
    summary: pd.DataFrame,
    mois: str,
    multiplier: float = 1.5,
    window_months: int = 6,
) -> list[dict]:
    if summary.empty or mois not in set(summary["mois"]):
        return []

    summary = summary.sort_values("mois").reset_index(drop=True)
    target_index = summary.index[summary["mois"].eq(mois)].tolist()[0]
    history = summary.iloc[max(0, target_index - window_months) : target_index]
    target = summary.iloc[target_index]
    anomalies = []

    for metric in ["delai_moyen_jours", "satisfaction_moyenne"]:
        values = pd.to_numeric(history[metric], errors="coerce").dropna()
        value = target[metric]
        if values.empty or pd.isna(value):
            continue
        mean = values.mean()
        std = values.std(ddof=0)
        if std == 0:
            is_anomaly = abs(float(value) - float(mean)) > 0
        else:
            is_anomaly = abs(float(value) - float(mean)) > multiplier * float(std)
        if is_anomaly:
            anomalies.append(
                {
                    "mois": mois,
                    "metric": metric,
                    "value": float(value),
                    "baseline_mean": float(mean),
                    "baseline_std": float(std),
                    "severity": "orange" if metric == "satisfaction_moyenne" else "red",
                }
            )

    return anomalies
