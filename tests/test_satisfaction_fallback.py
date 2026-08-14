"""
tests/test_satisfaction_fallback.py
─────────────────────────────────────
Vérifie le comportement fallback : si aucune réponse d'enquête n'existe
pour le mois demandé, on utilise l'ensemble des réponses disponibles
(fallback_global=True).

Notes de l'enquête fallback :
  traitement   = [4]  → 1 positif / 1 = 100%
  communication= [3]  → 0 positif / 1 = 0%  (note 3 = "insatisfait")
  temps        = [2]  → 0 positif / 1 = 0%  (note 2 = "plutôt insatisfait")

  Taux global combiné = 1 positif / 3 réponses = 33.33%
"""

import pandas as pd

from core import kpi


def test_satisfaction_fallback_uses_global_when_no_month_response():
    """
    Aucune réponse enquête pour juillet 2026 → utilisation des réponses
    de juin 2026 en fallback. fallback_global doit être True.
    """
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
            "satisfaction_traitement": [4.0],    # satisfait → positif
            "communication_operateurs": [3.0],   # insatisfait → négatif
            "satisfaction_temps": [2.0],         # plutôt insatisfait → négatif
        }
    )

    result = kpi.calculate_month_kpi(df, "2026-07")

    assert result.satisfaction.fallback_global is True
    # Taux global combiné : 1 positif (note 4) / 3 réponses = 33.33%
    assert abs(result.satisfaction.satisfaction_globale - 100 / 3) < 0.01
    # Communication et temps ont 0% de satisfaction (notes 3 et 2)
    assert result.satisfaction.detail_communication.taux_satisfaction == 0.0
    assert result.satisfaction.detail_temps.taux_satisfaction == 0.0
    # Traitement a 100% (note 4 = satisfait)
    assert result.satisfaction.detail_traitement.taux_satisfaction == 100.0
