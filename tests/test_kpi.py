import pandas as pd

from core import kpi


def _sample():
    df = pd.DataFrame(
        {
            "ticket_id": ["A", "B", "C"],
            "beneficiaire_id": ["U1", "U1", "U2"],
            "beneficiaire": ["One", "One", "Two"],
            "date_ouverture": pd.to_datetime(["2026-06-01", "2026-06-03", "2026-05-25"]),
            "date_fermeture": pd.to_datetime(["2026-06-02", None, "2026-06-10"]),
            "mois_ouverture": ["2026-06", "2026-06", "2026-05"],
            "mois_fermeture": ["2026-06", pd.NA, "2026-06"],
            "delai_resolution_minutes": [60.0, pd.NA, 180.0],
            "delai_resolution_jours": [1.0 / 24, pd.NA, 3.0 / 24],
            "site": ["Kram", "Kram", "Megrine"],
            "categorie": ["VPN", "VPN", "PC"],
            "manager": ["M1", "M1", "M2"],
        }
    )
    df.attrs["column_sources"] = {
        "tickets": {
            "ticket_id": "N° ticket",
            "date_ouverture": "Enregistré le",
            "date_fermeture": "Date de résolution",
            "delai_source": "Délai de résolution (min)",
            "site": "Bénéficiaire : Localisation",
            "categorie": "Sujet",
        }
    }
    df.attrs["satisfaction_responses"] = pd.DataFrame(
        {
            "ticket_id": ["A", "B"],
            "date_enquete": pd.to_datetime(["2026-06-03", "2026-06-04"]),
            "mois_enquete": ["2026-06", "2026-06"],
            "satisfaction_traitement": [5.0, 3.0],
            "communication_operateurs": [4.0, 4.0],
            "satisfaction_temps": [2.0, 3.0],
        }
    )
    return df


def test_calculate_month_kpi_exact_formulas():
    result = kpi.calculate_month_kpi(_sample(), "2026-06")

    assert result.total_ouverts == 2
    assert result.total_fermes == 2
    assert result.ouverts_et_fermes_meme_mois == 1
    assert result.delai_moyen_minutes == 120.0
    assert result.delai_moyen_heures == 2.0
    assert result.satisfaction.satisfaction_globale == 4.0
    assert result.satisfaction.communication == 4.0
    assert result.satisfaction.temps_percu == 2.5
    assert result.satisfaction.taux_participation == 100.0
    assert result.satisfaction.rubrique_moins_satisfaisante == "Satisfaction du temps de traitement"


def test_recurrent_requesters():
    result = kpi.recurrent_requesters(_sample(), "2026-06", minimum=2)

    assert len(result) == 1
    assert result.iloc[0]["beneficiaire_id"] == "U1"
