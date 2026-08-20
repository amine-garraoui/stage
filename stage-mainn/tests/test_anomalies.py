import pandas as pd

from core.anomalies import detect_anomalies


def test_detect_anomaly_on_delay():
    summary = pd.DataFrame(
        {
            "mois": ["2026-01", "2026-02", "2026-03", "2026-04"],
            "total_ouverts": [10, 10, 10, 10],
            "total_fermes": [10, 10, 10, 10],
            "actifs_fin_mois": [0, 0, 0, 0],
            "delai_moyen_jours": [1.0, 1.1, 0.9, 5.0],
            "satisfaction_moyenne": [4.0, 4.1, 4.0, 4.0],
        }
    )

    alerts = detect_anomalies(summary, "2026-04", multiplier=1.5, window_months=3)

    assert any(alert["metric"] == "delai_moyen_jours" for alert in alerts)
