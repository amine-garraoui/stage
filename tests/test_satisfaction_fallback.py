import pandas as pd

from core import kpi


def test_satisfaction_fallback_uses_global_when_no_month_response():
    df = pd.DataFrame(
        {
            "ticket_id": ["A"],
            "date_ouverture": pd.to_datetime(["2026-07-01"]),
            "date_fermeture": pd.to_datetime([None]),
            "mois_ouverture": ["2026-07"],
            "mois_fermeture": [pd.NA],
            "delai_resolution_minutes": [pd.NA],
            "site": ["Kram"],
            "categorie": ["VPN"],
        }
    )
    df.attrs["column_sources"] = {"tickets": {"date_ouverture": "Enregistré le"}}
    df.attrs["satisfaction_responses"] = pd.DataFrame(
        {
            "ticket_id": ["OLD"],
            "mois_enquete": ["2026-06"],
            "satisfaction_traitement": [4.0],
            "communication_operateurs": [3.0],
            "satisfaction_temps": [2.0],
        }
    )

    result = kpi.calculate_month_kpi(df, "2026-07")

    assert result.satisfaction.fallback_global is True
    assert result.satisfaction.satisfaction_globale == 4.0
