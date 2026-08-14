"""
tests/test_kpi.py
─────────────────
Tests unitaires des calculs KPI.

Inclut :
  - Tests sur des données synthétiques (formules exactes)
  - Tests de validation sur les valeurs de référence juin 2026
    (source : export ASKit officiel, section 6 du cahier des charges)
    Ces valeurs servent à VÉRIFIER les formules, jamais affichées en dur
    dans le dashboard.
"""

import pandas as pd
import pytest

from core import kpi


# ── Fixture données synthétiques ──────────────────────────────────────────

def _sample() -> pd.DataFrame:
    """
    3 tickets :
      A : ouvert 01/06, fermé 02/06  → ouvert ET fermé juin (délai 60 min)
      B : ouvert 03/06, non fermé    → ouvert juin, pas fermé
      C : ouvert 25/05, fermé 10/06  → global traité juin (pas même mois)

    Juin 2026 :
      total_ouverts             = 2 (A, B)
      total_fermes (global)     = 2 (A, C)
      ouverts_et_fermes_meme_mois = 1 (A seulement)
      delai_moyen               = (60 + 180) / 2 = 120 min = 2 h

    Satisfaction (2 répondants, 3 rubriques = 6 notes combinées) :
      traitement   : [5, 3]  → satisfait/très_satisfait = 1/2 (note 5) → 1 positif
      communication: [4, 4]  → 2 positifs
      temps        : [2, 3]  → 0 positif
      Total positifs = 1 + 2 + 0 = 3 sur 6 → taux global = 50%
      Rubrique faible : temps (0 %)
    """
    df = pd.DataFrame(
        {
            "ticket_id": ["A", "B", "C"],
            "beneficiaire_id": ["U1", "U1", "U2"],
            "date_ouverture": pd.to_datetime(["2026-06-01", "2026-06-03", "2026-05-25"]),
            "date_fermeture": pd.to_datetime(["2026-06-02", None, "2026-06-10"]),
            "mois_ouverture": ["2026-06", "2026-06", "2026-05"],
            "mois_fermeture": ["2026-06", pd.NA, "2026-06"],
            "delai_resolution_minutes": [60.0, pd.NA, 180.0],
            "delai_resolution_jours": [60.0 / 1440, pd.NA, 180.0 / 1440],
            "site": ["Kram", "Kram", "Megrine"],
            "categorie": ["VPN", "VPN", "PC"],
            "statut": ["Ferme", "Ouvert", "Ferme"],
            "est_ferme": [True, False, True],
            "pole": ["E&T", "E&T", "AVS"],
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


# ── Tests formules exactes (données synthétiques) ─────────────────────────

class TestCalculateMonthKpi:
    def test_total_ouverts(self):
        r = kpi.calculate_month_kpi(_sample(), "2026-06")
        assert r.total_ouverts == 2

    def test_total_fermes_global(self):
        """total_fermes = tickets fermés ce mois (A + C = 2, quelle que soit l'ouverture)."""
        r = kpi.calculate_month_kpi(_sample(), "2026-06")
        assert r.total_fermes == 2

    def test_ouverts_et_fermes_meme_mois(self):
        """Seul A est ouvert ET fermé en juin."""
        r = kpi.calculate_month_kpi(_sample(), "2026-06")
        assert r.ouverts_et_fermes_meme_mois == 1

    def test_delai_moyen_minutes(self):
        """Délai calculé sur les fermés du mois : (60 + 180) / 2 = 120 min."""
        r = kpi.calculate_month_kpi(_sample(), "2026-06")
        assert r.delai_moyen_minutes == pytest.approx(120.0)

    def test_delai_moyen_heures(self):
        r = kpi.calculate_month_kpi(_sample(), "2026-06")
        assert r.delai_moyen_heures == pytest.approx(2.0)

    def test_satisfaction_globale_taux_combine(self):
        """
        Taux global combiné :
          traitement [5,3]   → positifs (note≥4) = 1
          communication [4,4]→ positifs = 2
          temps [2,3]        → positifs = 0
          Total = 3/6 = 50.0%
        """
        r = kpi.calculate_month_kpi(_sample(), "2026-06")
        assert r.satisfaction.satisfaction_globale == pytest.approx(50.0)

    def test_satisfaction_rubrique_faible(self):
        """Temps de traitement a 0% de satisfaction → rubrique la moins satisfaisante."""
        r = kpi.calculate_month_kpi(_sample(), "2026-06")
        assert "temps" in r.satisfaction.rubrique_moins_satisfaisante.lower()

    def test_satisfaction_participation(self):
        """2 répondants / 2 fermés (global traités) × 100 = 100%."""
        r = kpi.calculate_month_kpi(_sample(), "2026-06")
        assert r.satisfaction.taux_participation == pytest.approx(100.0)

    def test_nombre_reponses(self):
        r = kpi.calculate_month_kpi(_sample(), "2026-06")
        assert r.satisfaction.nombre_reponses == 2


class TestRubriqueDetail:
    def test_detail_traitement_counts(self):
        """Traitement [5, 3] → très satisfait=1, insatisfait=1."""
        r = kpi.calculate_month_kpi(_sample(), "2026-06")
        d = r.satisfaction.detail_traitement
        assert d.tres_satisfait == 1
        assert d.insatisfait == 1
        assert d.satisfait == 0
        assert d.tres_insatisfait == 0

    def test_detail_communication_counts(self):
        """Communication [4, 4] → satisfait=2."""
        r = kpi.calculate_month_kpi(_sample(), "2026-06")
        d = r.satisfaction.detail_communication
        assert d.satisfait == 2
        assert d.tres_satisfait == 0

    def test_detail_temps_counts(self):
        """Temps [2, 3] → plutôt insatisfait=1, insatisfait=1."""
        r = kpi.calculate_month_kpi(_sample(), "2026-06")
        d = r.satisfaction.detail_temps
        assert d.plutot_insatisfait == 1
        assert d.insatisfait == 1
        assert d.taux_satisfaction == pytest.approx(0.0)

    def test_detail_traitement_taux(self):
        """Traitement : 1 positif / 2 = 50%."""
        r = kpi.calculate_month_kpi(_sample(), "2026-06")
        assert r.satisfaction.detail_traitement.taux_satisfaction == pytest.approx(50.0)


# ── Tests de validation valeurs de référence juin 2026 ────────────────────
# Source : export ASKit officiel (cahier des charges, section 6).
# Ces valeurs permettent de VÉRIFIER les formules sans jamais être
# affichées en dur dans le dashboard.


def _make_juin_2026_df(
    n_ouverts_juin: int,
    n_ouverts_et_fermes_meme_mois: int,
    n_fermes_mois_precedent_clos_juin: int,
    delai_moyen_minutes: float,
) -> pd.DataFrame:
    """
    Construit un DataFrame représentant les données de juin 2026
    à partir des valeurs de référence du cahier des charges.

    n_ouverts_juin = 277
    n_ouverts_et_fermes = 228  (ouverts en juin ET fermés en juin)
    n_fermes_mois_prec  = 80   (fermés en juin mais ouverts avant = 308 - 228)
    delai_moyen         = 72.71 h → 4362.6 min
    """
    rows = []
    # Tickets ouverts ET fermés en juin (228)
    for i in range(n_ouverts_et_fermes_meme_mois):
        rows.append({
            "ticket_id": f"OF_{i}",
            "beneficiaire_id": "USR",
            "mois_ouverture": "2026-06",
            "mois_fermeture": "2026-06",
            "date_ouverture": pd.Timestamp("2026-06-01"),
            "date_fermeture": pd.Timestamp("2026-06-15"),
            "delai_resolution_minutes": delai_moyen_minutes,
            "site": "Megrine",
            "categorie": "Informatique",
            "statut": "Ferme",
            "est_ferme": True,
        })
    # Tickets ouverts en juin mais NON fermés (277 - 228 = 49)
    n_ouverts_seulement = n_ouverts_juin - n_ouverts_et_fermes_meme_mois
    for i in range(n_ouverts_seulement):
        rows.append({
            "ticket_id": f"OO_{i}",
            "beneficiaire_id": "USR",
            "mois_ouverture": "2026-06",
            "mois_fermeture": pd.NA,
            "date_ouverture": pd.Timestamp("2026-06-01"),
            "date_fermeture": pd.NaT,
            "delai_resolution_minutes": pd.NA,
            "site": "Kram",
            "categorie": "Informatique",
            "statut": "Ouvert",
            "est_ferme": False,
        })
    # Tickets ouverts avant juin, fermés en juin (308 - 228 = 80)
    for i in range(n_fermes_mois_precedent_clos_juin):
        rows.append({
            "ticket_id": f"PF_{i}",
            "beneficiaire_id": "USR",
            "mois_ouverture": "2026-05",
            "mois_fermeture": "2026-06",
            "date_ouverture": pd.Timestamp("2026-05-15"),
            "date_fermeture": pd.Timestamp("2026-06-05"),
            "delai_resolution_minutes": delai_moyen_minutes,
            "site": "Sousse",
            "categorie": "Réseau",
            "statut": "Ferme",
            "est_ferme": True,
        })

    df = pd.DataFrame(rows)
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
    # Satisfaction juin 2026 : 46 répondants, 3 rubriques
    # Traitement    : 0/0/0/9/37   → 46 réponses, 46 positifs (9+37)
    # Communication : 0/0/0/8/38   → 46 réponses, 46 positifs (8+38)
    # Temps         : 0/1/0/8/37   → 46 réponses, 45 positifs (8+37)
    # Total combiné : 138 réponses, 137 positifs → 137/138 = 99.28%
    sat_rows = []
    # Traitement : 9×note4 + 37×note5
    notes_traitement = [4] * 9 + [5] * 37
    # Communication : 8×note4 + 38×note5
    notes_communication = [4] * 8 + [5] * 38
    # Temps : 1×note2 + 8×note4 + 37×note5
    notes_temps = [2] * 1 + [4] * 8 + [5] * 37
    for j in range(46):
        sat_rows.append({
            "ticket_id": f"OF_{j}",
            "date_enquete": pd.Timestamp("2026-06-20"),
            "mois_enquete": "2026-06",
            "satisfaction_traitement": float(notes_traitement[j]),
            "communication_operateurs": float(notes_communication[j]),
            "satisfaction_temps": float(notes_temps[j]),
        })
    df.attrs["satisfaction_responses"] = pd.DataFrame(sat_rows)
    return df


# Valeurs de référence (cahier des charges, section 6)
REF_JUIN = _make_juin_2026_df(
    n_ouverts_juin=277,
    n_ouverts_et_fermes_meme_mois=228,
    n_fermes_mois_precedent_clos_juin=80,   # 308 - 228
    delai_moyen_minutes=72.71 * 60,         # 72.71 h → 4362.6 min
)


class TestValeursReferenceJuin2026:
    """
    Validation des formules contre les chiffres officiels du rapport juin 2026.
    Ces tests échouent si les formules de calcul s'écartent des définitions métier.
    """

    def test_demandes_ouvertes(self):
        r = kpi.calculate_month_kpi(REF_JUIN, "2026-06")
        assert r.total_ouverts == 277, (
            f"Attendu 277 demandes ouvertes, obtenu {r.total_ouverts}"
        )

    def test_global_traites(self):
        """global traités = tous les fermés en juin = 308 (228 + 80)."""
        r = kpi.calculate_month_kpi(REF_JUIN, "2026-06")
        assert r.total_fermes == 308, (
            f"Attendu 308 global traités, obtenu {r.total_fermes}"
        )

    def test_ouverts_et_fermes_meme_mois(self):
        r = kpi.calculate_month_kpi(REF_JUIN, "2026-06")
        assert r.ouverts_et_fermes_meme_mois == 228, (
            f"Attendu 228 ouverts ET fermés juin, obtenu {r.ouverts_et_fermes_meme_mois}"
        )

    def test_delai_moyen_heures(self):
        r = kpi.calculate_month_kpi(REF_JUIN, "2026-06")
        assert r.delai_moyen_heures == pytest.approx(72.71, abs=0.01), (
            f"Attendu ≈72.71 h, obtenu {r.delai_moyen_heures}"
        )

    def test_satisfaction_globale(self):
        """137 positifs / 138 réponses combinées = 99.275..% ≈ 99.28%."""
        r = kpi.calculate_month_kpi(REF_JUIN, "2026-06")
        assert r.satisfaction.satisfaction_globale == pytest.approx(137 / 138 * 100, abs=0.01), (
            f"Attendu ≈99.28%, obtenu {r.satisfaction.satisfaction_globale}"
        )

    def test_nombre_reponses(self):
        r = kpi.calculate_month_kpi(REF_JUIN, "2026-06")
        assert r.satisfaction.nombre_reponses == 46

    def test_taux_participation(self):
        """46 répondants / 308 global traités × 100 = 14.94%."""
        r = kpi.calculate_month_kpi(REF_JUIN, "2026-06")
        assert r.satisfaction.taux_participation == pytest.approx(14.935, abs=0.01), (
            f"Attendu ≈14.94%, obtenu {r.satisfaction.taux_participation}"
        )

    def test_detail_traitement_counts(self):
        """Traitement juin 2026 : 0/0/0/9/37."""
        r = kpi.calculate_month_kpi(REF_JUIN, "2026-06")
        d = r.satisfaction.detail_traitement
        assert d.tres_insatisfait == 0
        assert d.plutot_insatisfait == 0
        assert d.insatisfait == 0
        assert d.satisfait == 9
        assert d.tres_satisfait == 37

    def test_detail_communication_counts(self):
        """Communication juin 2026 : 0/0/0/8/38."""
        r = kpi.calculate_month_kpi(REF_JUIN, "2026-06")
        d = r.satisfaction.detail_communication
        assert d.tres_insatisfait == 0
        assert d.plutot_insatisfait == 0
        assert d.insatisfait == 0
        assert d.satisfait == 8
        assert d.tres_satisfait == 38

    def test_detail_temps_counts(self):
        """Temps juin 2026 : 0/1/0/8/37."""
        r = kpi.calculate_month_kpi(REF_JUIN, "2026-06")
        d = r.satisfaction.detail_temps
        assert d.tres_insatisfait == 0
        assert d.plutot_insatisfait == 1
        assert d.insatisfait == 0
        assert d.satisfait == 8
        assert d.tres_satisfait == 37

    def test_rubrique_moins_satisfaisante(self):
        """Temps de traitement a le taux le plus bas (45/46 < 46/46)."""
        r = kpi.calculate_month_kpi(REF_JUIN, "2026-06")
        assert "temps" in r.satisfaction.rubrique_moins_satisfaisante.lower()


# ── Tests complémentaires ─────────────────────────────────────────────────

class TestDistributions:
    def test_tickets_by_site(self):
        result = kpi.tickets_by_site(_sample(), "2026-06")
        assert "site" in result.columns
        assert "nombre_tickets" in result.columns
        assert result[result["site"] == "Kram"]["nombre_tickets"].values[0] == 2

    def test_tickets_by_site_pole(self):
        result = kpi.tickets_by_site_pole(_sample(), "2026-06")
        assert "site" in result.columns
        assert "pole" in result.columns
        assert "nombre_tickets" in result.columns

    def test_subjects_opened_month(self):
        result = kpi.subjects_opened_month(_sample(), "2026-06")
        assert result.iloc[0]["categorie"] == "VPN"
        assert result.iloc[0]["nombre_tickets"] == 2

    def test_recurrent_requesters_no_names(self):
        """La fonction ne retourne que beneficiaire_id — jamais de colonne 'nom'."""
        result = kpi.recurrent_requesters(_sample(), "2026-06", minimum=2)
        assert "beneficiaire_id" in result.columns
        assert "beneficiaire" not in result.columns
        assert len(result) == 1
        assert result.iloc[0]["beneficiaire_id"] == "U1"

    def test_available_months(self):
        months = kpi.available_months(_sample())
        assert "2026-06" in months
        assert "2026-05" in months
