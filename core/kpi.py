"""
core/kpi.py
───────────
Calcul des indicateurs KPI mensuels pour le service RSI Sagemcom.

Règles métier (source : cahier des charges + valeurs de référence juin 2026) :
  - demandes_ouvertes       : date_ouverture dans le mois sélectionné
  - ouverts_et_fermes       : date_ouverture ET date_fermeture dans le même mois
  - global_traites          : date_fermeture dans le mois (quelle que soit l'ouverture)
  - delai_moyen             : moyenne(date_fermeture - date_ouverture) sur les
                              tickets clôturés dans le mois
  - taux_participation      : nb_réponses / global_traites × 100
  - satisfaction_globale    : (satisfait + très_satisfait) / total_réponses
                              toutes rubriques combinées (≠ moyenne des moyennes)
  - note → catégorie        : 1=très insatisfait, 2=plutôt insatisfait,
                              3=insatisfait, 4=satisfait, 5=très satisfait
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


DATA_UNAVAILABLE = "Donnee indisponible"

# ── Correspondance note numérique → catégorie textuelle ───────────────────
NOTE_VERS_CATEGORIE: dict[int, str] = {
    1: "Très insatisfait",
    2: "Plutôt insatisfait",
    3: "Insatisfait",
    4: "Satisfait",
    5: "Très satisfait",
}
CATEGORIES_POSITIVES = {"Satisfait", "Très satisfait"}
CATEGORIES_ORDONNEES = [
    "Très insatisfait",
    "Plutôt insatisfait",
    "Insatisfait",
    "Satisfait",
    "Très satisfait",
]


# ── Dataclasses résultat ───────────────────────────────────────────────────

@dataclass(frozen=True)
class RubriqueDetail:
    """Distribution par niveau pour une rubrique de satisfaction."""
    tres_insatisfait: int
    plutot_insatisfait: int
    insatisfait: int
    satisfait: int
    tres_satisfait: int
    taux_satisfaction: float | None  # % (satisfait + très satisfait) / total

    def as_dict(self) -> dict:
        return {
            "très insatisfait": self.tres_insatisfait,
            "plutôt insatisfait": self.plutot_insatisfait,
            "insatisfait": self.insatisfait,
            "satisfait": self.satisfait,
            "très satisfait": self.tres_satisfait,
            "taux_satisfaction": self.taux_satisfaction,
        }


@dataclass(frozen=True)
class SatisfactionResult:
    """Résultat complet du bloc satisfaction pour un mois donné."""
    satisfaction_globale: float | None   # taux % combiné (toutes rubriques)
    taux_participation: float | None     # nb_réponses / global_traites × 100
    nombre_reponses: int                 # nb répondants (lignes avec au moins 1 note)
    rubrique_moins_satisfaisante: str | None
    fallback_global: bool                # True si pas de date dans les réponses

    # Détail par rubrique
    detail_traitement: RubriqueDetail | None = None
    detail_communication: RubriqueDetail | None = None
    detail_temps: RubriqueDetail | None = None

    @property
    def satisfaction_moyenne(self) -> float | None:
        """Alias de compatibilité avec l'ancienne interface."""
        return self.satisfaction_globale

    @property
    def communication(self) -> float | None:
        return self.detail_communication.taux_satisfaction if self.detail_communication else None

    @property
    def temps_percu(self) -> float | None:
        return self.detail_temps.taux_satisfaction if self.detail_temps else None

    def as_dict(self) -> dict:
        return {
            "satisfaction_globale": self.satisfaction_globale,
            "taux_participation": self.taux_participation,
            "nombre_reponses": self.nombre_reponses,
            "rubrique_moins_satisfaisante": self.rubrique_moins_satisfaisante,
            "fallback_global": self.fallback_global,
            "detail_traitement": self.detail_traitement.as_dict() if self.detail_traitement else None,
            "detail_communication": self.detail_communication.as_dict() if self.detail_communication else None,
            "detail_temps": self.detail_temps.as_dict() if self.detail_temps else None,
        }


@dataclass(frozen=True)
class KpiResult:
    """Résultat KPI complet pour un mois donné."""
    mois: str
    total_ouverts: int
    total_fermes: int | None          # global traitées = fermés ce mois
    ouverts_et_fermes_meme_mois: int | None
    delai_moyen_minutes: float | None
    delai_moyen_heures: float | None
    delai_moyen_jours: float | None
    satisfaction: SatisfactionResult = field(
        default_factory=lambda: SatisfactionResult(None, None, 0, None, False)
    )

    @property
    def satisfaction_moyenne(self) -> float | None:
        return self.satisfaction.satisfaction_globale

    def as_dict(self) -> dict:
        return {
            "mois": self.mois,
            "total_ouverts": self.total_ouverts,
            "total_fermes": self.total_fermes,
            "actifs_fin_mois": None,          # compatibilité anomalies.py
            "ouverts_et_fermes_meme_mois": self.ouverts_et_fermes_meme_mois,
            "delai_moyen_minutes": self.delai_moyen_minutes,
            "delai_moyen_heures": self.delai_moyen_heures,
            "delai_moyen_jours": self.delai_moyen_jours,
            # Clé de compatibilité pour anomalies.py / show_comparison
            "satisfaction_moyenne": self.satisfaction.satisfaction_globale,
            **self.satisfaction.as_dict(),
        }


# ── Helpers ────────────────────────────────────────────────────────────────

def _nullable_mean(series: pd.Series) -> float | None:
    value = pd.to_numeric(series, errors="coerce").mean()
    return None if pd.isna(value) else float(value)


def _column_available(df: pd.DataFrame, group: str, column: str) -> bool:
    return column in df.attrs.get("column_sources", {}).get(group, {})


def _note_to_category(note: float | None) -> str | None:
    """Convertit une note numérique (1-5) en catégorie textuelle."""
    if note is None or pd.isna(note):
        return None
    try:
        return NOTE_VERS_CATEGORIE.get(int(round(float(note))))
    except (ValueError, TypeError):
        return None


def _build_rubrique_detail(series: pd.Series) -> RubriqueDetail:
    """Calcule la distribution et le taux pour une colonne de notes 1-5."""
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    categories = numeric.map(lambda n: NOTE_VERS_CATEGORIE.get(int(round(n))))
    counts = categories.value_counts()

    def c(label: str) -> int:
        return int(counts.get(label, 0))

    total = len(numeric)
    positifs = c("Satisfait") + c("Très satisfait")
    taux = (positifs / total * 100) if total > 0 else None

    return RubriqueDetail(
        tres_insatisfait=c("Très insatisfait"),
        plutot_insatisfait=c("Plutôt insatisfait"),
        insatisfait=c("Insatisfait"),
        satisfait=c("Satisfait"),
        tres_satisfait=c("Très satisfait"),
        taux_satisfaction=taux,
    )


# ── Filtres de base ────────────────────────────────────────────────────────

def available_months(df: pd.DataFrame) -> list[str]:
    """Liste triée de tous les mois présents (ouverture ou fermeture)."""
    parts = []
    if "mois_ouverture" in df.columns:
        parts.append(pd.Series(df["mois_ouverture"].dropna().to_numpy()))
    if "mois_fermeture" in df.columns:
        parts.append(pd.Series(df["mois_fermeture"].dropna().to_numpy()))
    if not parts:
        return []
    months = pd.Series(pd.concat(parts).unique()).dropna()
    return sorted(months.astype(str).tolist())


def filter_opened_month(df: pd.DataFrame, mois: str) -> pd.DataFrame:
    """Tickets dont la date d'ouverture est dans le mois sélectionné."""
    if "mois_ouverture" not in df.columns:
        return pd.DataFrame(columns=df.columns)
    result = df[df["mois_ouverture"].eq(mois)].copy()
    result.attrs = df.attrs.copy()
    return result


def filter_closed_month(df: pd.DataFrame, mois: str) -> pd.DataFrame:
    """Tickets dont la date de fermeture est dans le mois sélectionné (global traités)."""
    if "mois_fermeture" not in df.columns:
        return pd.DataFrame(columns=df.columns)
    result = df[df["mois_fermeture"].eq(mois)].copy()
    result.attrs = df.attrs.copy()
    return result


# ── Calcul satisfaction ─────────────────────────────────────────────────────

def satisfaction_summary(
    df: pd.DataFrame,
    mois: str,
    global_traites: int,
) -> SatisfactionResult:
    """
    Calcule les indicateurs de satisfaction pour un mois donné.

    Méthode officielle (validée sur les données juin 2026) :
    - Taux global = (satisfait + très satisfait sur les 3 rubriques combinées)
                   / (total réponses × 3 rubriques)
    - Rubrique faible = celle qui a le taux individuel le plus bas.
    - Participation = nb_répondants / global_traites × 100.
    """
    responses = df.attrs.get("satisfaction_responses")
    if responses is None or responses.empty:
        return SatisfactionResult(None, None, 0, None, False)

    required_cols = ["satisfaction_traitement", "communication_operateurs", "satisfaction_temps"]
    if not any(col in responses.columns for col in required_cols):
        return SatisfactionResult(None, None, 0, None, False)

    # Scope par mois
    has_date = "mois_enquete" in responses.columns and responses["mois_enquete"].notna().any()
    if has_date:
        scoped = responses[responses["mois_enquete"].eq(mois)].copy()
        fallback_global = scoped.empty
        if fallback_global:
            scoped = responses.copy()
    else:
        scoped = responses.copy()
        fallback_global = True

    # Lignes avec au moins 1 réponse
    notes = scoped[required_cols].apply(pd.to_numeric, errors="coerce")
    rows_with_answer = notes.dropna(how="all")
    nb_reponses = len(rows_with_answer)

    if nb_reponses == 0:
        return SatisfactionResult(None, None, 0, None, fallback_global)

    # Détail par rubrique
    detail_traitement = _build_rubrique_detail(rows_with_answer["satisfaction_traitement"])
    detail_communication = _build_rubrique_detail(rows_with_answer["communication_operateurs"])
    detail_temps = _build_rubrique_detail(rows_with_answer["satisfaction_temps"])

    # Taux global combiné (toutes rubriques, toutes réponses)
    toutes_notes = pd.concat([
        rows_with_answer["satisfaction_traitement"].dropna(),
        rows_with_answer["communication_operateurs"].dropna(),
        rows_with_answer["satisfaction_temps"].dropna(),
    ])
    total_combiné = len(toutes_notes)
    positifs_combinés = int((toutes_notes.round().isin([4, 5])).sum())
    taux_global = (positifs_combinés / total_combiné * 100) if total_combiné > 0 else None

    # Rubrique la moins satisfaisante (taux individuel le plus bas)
    taux_rubriques = {
        "Satisfaction de traitement": detail_traitement.taux_satisfaction,
        "Communication des opérateurs": detail_communication.taux_satisfaction,
        "Satisfaction du temps de traitement": detail_temps.taux_satisfaction,
    }
    taux_disponibles = {k: v for k, v in taux_rubriques.items() if v is not None}
    rubrique_faible = min(taux_disponibles, key=taux_disponibles.get) if taux_disponibles else None

    # Taux de participation = nb_répondants / global_traites
    participation = (nb_reponses / global_traites * 100) if global_traites > 0 else None

    return SatisfactionResult(
        satisfaction_globale=taux_global,
        taux_participation=participation,
        nombre_reponses=nb_reponses,
        rubrique_moins_satisfaisante=rubrique_faible,
        fallback_global=fallback_global,
        detail_traitement=detail_traitement,
        detail_communication=detail_communication,
        detail_temps=detail_temps,
    )


# ── KPI mensuel principal ──────────────────────────────────────────────────

def calculate_month_kpi(df: pd.DataFrame, mois: str) -> KpiResult:
    """
    Calcule l'ensemble des KPI pour le mois sélectionné.

    Indicateurs :
      total_ouverts             : ouverts dans le mois
      total_fermes              : global traités (fermés ce mois, quelle que soit ouverture)
      ouverts_et_fermes_meme_mois : ouverts ET fermés dans le même mois
      delai_moyen               : calculé sur les fermés du mois
    """
    opened = filter_opened_month(df, mois)
    opened_count = int(len(opened))

    has_resolution_date = _column_available(df, "tickets", "date_fermeture")
    closed = filter_closed_month(df, mois) if has_resolution_date else pd.DataFrame(columns=df.columns)
    global_traites = int(len(closed)) if has_resolution_date else None

    # Ouverts ET fermés dans le même mois
    same_month_count = (
        int(len(closed[closed["mois_ouverture"].eq(mois)]))
        if has_resolution_date and "mois_ouverture" in closed.columns
        else None
    )

    # Délai moyen sur les fermés du mois
    has_delay = _column_available(df, "tickets", "delai_source") or has_resolution_date
    delay_minutes = (
        _nullable_mean(closed["delai_resolution_minutes"])
        if has_delay and not closed.empty
        else None
    )
    delay_hours = delay_minutes / 60 if delay_minutes is not None else None
    delay_days = delay_minutes / 1440 if delay_minutes is not None else None

    sat = satisfaction_summary(df, mois, global_traites or opened_count)

    return KpiResult(
        mois=mois,
        total_ouverts=opened_count,
        total_fermes=global_traites,
        ouverts_et_fermes_meme_mois=same_month_count,
        delai_moyen_minutes=delay_minutes,
        delai_moyen_heures=delay_hours,
        delai_moyen_jours=delay_days,
        satisfaction=sat,
    )


def monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = [calculate_month_kpi(df, month).as_dict() for month in available_months(df)]
    return pd.DataFrame(rows)


# ── Distributions ──────────────────────────────────────────────────────────

def distribution(
    df: pd.DataFrame, mois: str, column: str, top: int | None = None
) -> pd.DataFrame:
    """Distribution par colonne sur les tickets ouverts du mois."""
    opened = filter_opened_month(df, mois)
    if column not in opened.columns:
        return pd.DataFrame(columns=[column, "nombre_tickets"])
    result = (
        opened.groupby(column, dropna=False, as_index=False)
        .size()
        .rename(columns={"size": "nombre_tickets"})
        .sort_values("nombre_tickets", ascending=False)
    )
    return result.head(top) if top else result


def tickets_by_site(df: pd.DataFrame, mois: str) -> pd.DataFrame:
    """Nombre de tickets ouverts par site pour le mois sélectionné."""
    return distribution(df, mois, "site")


def subjects_opened_month(df: pd.DataFrame, mois: str, top: int | None = None) -> pd.DataFrame:
    """Répartition des types de demandes (par sujet) pour le mois."""
    return distribution(df, mois, "categorie", top)


def tickets_by_site_pole(df: pd.DataFrame, mois: str) -> pd.DataFrame:
    """
    Croisement site × pôle pour les tickets ouverts du mois.
    Utilise la colonne 'pole' (alimentée par build_dataset via mapping directeur).
    """
    opened = filter_opened_month(df, mois)
    pole_col = "pole" if "pole" in opened.columns else "department"
    if "site" not in opened.columns or pole_col not in opened.columns:
        return pd.DataFrame(columns=["site", "pole", "nombre_tickets"])
    result = (
        opened.groupby(["site", pole_col], dropna=False, as_index=False)
        .size()
        .rename(columns={pole_col: "pole", "size": "nombre_tickets"})
        .sort_values(["site", "nombre_tickets"], ascending=[True, False])
    )
    return result


def kpi_by_dimension(df: pd.DataFrame, mois: str, dimension: str) -> pd.DataFrame:
    """KPI agrégés par une dimension arbitraire (site, pole, categorie...)."""
    opened = filter_opened_month(df, mois)
    if dimension not in opened.columns:
        return pd.DataFrame(columns=[dimension, "tickets_ouverts"])
    return (
        opened.groupby(dimension, dropna=False)
        .agg(tickets_ouverts=("ticket_id", "count"))
        .reset_index()
        .sort_values("tickets_ouverts", ascending=False)
    )


def recurrent_requesters(
    df: pd.DataFrame, mois: str | None = None, minimum: int = 5
) -> pd.DataFrame:
    """
    Tickets par beneficiaire_id (ID technique uniquement — pas de nom).
    Résultat agrégé, jamais de données nominatives.
    """
    data = filter_opened_month(df, mois) if mois else df
    result = (
        data.groupby("beneficiaire_id", dropna=False, as_index=False)
        .size()
        .rename(columns={"size": "nombre_tickets"})
        .sort_values("nombre_tickets", ascending=False)
    )
    return result[result["nombre_tickets"] >= minimum]
