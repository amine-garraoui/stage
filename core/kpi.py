from dataclasses import dataclass, field

import pandas as pd


DATA_UNAVAILABLE = "Donnee indisponible"


@dataclass(frozen=True)
class SatisfactionResult:
    satisfaction_globale: float | None
    communication: float | None
    temps_percu: float | None
    taux_participation: float | None
    rubrique_moins_satisfaisante: str | None
    nombre_reponses: int
    fallback_global: bool

    def as_dict(self) -> dict:
        return {
            "satisfaction_globale": self.satisfaction_globale,
            "communication": self.communication,
            "temps_percu": self.temps_percu,
            "taux_participation": self.taux_participation,
            "rubrique_moins_satisfaisante": self.rubrique_moins_satisfaisante,
            "nombre_reponses": self.nombre_reponses,
            "fallback_global": self.fallback_global,
        }


@dataclass(frozen=True)
class KpiResult:
    mois: str
    total_ouverts: int
    total_fermes: int | None
    ouverts_et_fermes_meme_mois: int | None
    delai_moyen_minutes: float | None
    delai_moyen_heures: float | None
    delai_moyen_jours: float | None
    satisfaction: SatisfactionResult = field(default_factory=lambda: SatisfactionResult(None, None, None, None, None, 0, False))

    @property
    def actifs_fin_mois(self) -> int | None:
        return None

    @property
    def satisfaction_moyenne(self) -> float | None:
        return self.satisfaction.satisfaction_globale

    def as_dict(self) -> dict:
        return {
            "mois": self.mois,
            "total_ouverts": self.total_ouverts,
            "total_fermes": self.total_fermes,
            "actifs_fin_mois": None,
            "ouverts_et_fermes_meme_mois": self.ouverts_et_fermes_meme_mois,
            "delai_moyen_minutes": self.delai_moyen_minutes,
            "delai_moyen_heures": self.delai_moyen_heures,
            "delai_moyen_jours": self.delai_moyen_jours,
            "satisfaction_moyenne": self.satisfaction.satisfaction_globale,
            "communication": self.satisfaction.communication,
            "temps_percu": self.satisfaction.temps_percu,
            "taux_participation": self.satisfaction.taux_participation,
            "rubrique_moins_satisfaisante": self.satisfaction.rubrique_moins_satisfaisante,
            "satisfaction_fallback_global": self.satisfaction.fallback_global,
        }


def available_months(df: pd.DataFrame) -> list[str]:
    months_parts = []
    if "mois_ouverture" in df.columns:
        months_parts.append(pd.Series(df["mois_ouverture"].dropna().to_numpy()))
    if "mois_fermeture" in df.columns:
        months_parts.append(pd.Series(df["mois_fermeture"].dropna().to_numpy()))
    if not months_parts:
        return []
    months = pd.Series(pd.concat(months_parts).unique()).dropna()
    return sorted(months.astype(str).tolist())


def filter_opened_month(df: pd.DataFrame, mois: str) -> pd.DataFrame:
    if "mois_ouverture" not in df.columns:
        return pd.DataFrame(columns=df.columns)
    result = df[df["mois_ouverture"].eq(mois)].copy()
    result.attrs = df.attrs.copy()
    return result


def filter_closed_month(df: pd.DataFrame, mois: str) -> pd.DataFrame:
    if "mois_fermeture" not in df.columns:
        return pd.DataFrame(columns=df.columns)
    result = df[df["mois_fermeture"].eq(mois)].copy()
    result.attrs = df.attrs.copy()
    return result


def _nullable_mean(series: pd.Series) -> float | None:
    value = pd.to_numeric(series, errors="coerce").mean()
    if pd.isna(value):
        return None
    return float(value)


def _column_available(df: pd.DataFrame, group: str, column: str) -> bool:
    return column in df.attrs.get("column_sources", {}).get(group, {})


def satisfaction_summary(df: pd.DataFrame, mois: str, opened_count: int) -> SatisfactionResult:
    responses = df.attrs.get("satisfaction_responses")
    if responses is None or responses.empty:
        return SatisfactionResult(None, None, None, None, None, 0, False)

    required = ["satisfaction_traitement", "communication_operateurs", "satisfaction_temps"]
    if not any(column in responses.columns for column in required):
        return SatisfactionResult(None, None, None, None, None, 0, False)

    has_date = "mois_enquete" in responses.columns and responses["mois_enquete"].notna().any()
    if has_date:
        scoped = responses[responses["mois_enquete"].eq(mois)].copy()
        fallback_global = scoped.empty
        if fallback_global:
            scoped = responses.copy()
    else:
        scoped = responses.copy()
        fallback_global = True

    valid_responses = scoped[required].apply(pd.to_numeric, errors="coerce")
    rows_with_answer = valid_responses.dropna(how="all")
    if rows_with_answer.empty:
        return SatisfactionResult(None, None, None, None, None, 0, fallback_global)

    means = {
        "Satisfaction de traitement": _nullable_mean(rows_with_answer["satisfaction_traitement"]),
        "Communication des operateurs": _nullable_mean(rows_with_answer["communication_operateurs"]),
        "Satisfaction du temps de traitement": _nullable_mean(rows_with_answer["satisfaction_temps"]),
    }
    available_means = {name: value for name, value in means.items() if value is not None}
    least_satisfying = min(available_means, key=available_means.get) if available_means else None
    participation = (len(rows_with_answer) / opened_count * 100) if opened_count else None

    return SatisfactionResult(
        satisfaction_globale=means["Satisfaction de traitement"],
        communication=means["Communication des operateurs"],
        temps_percu=means["Satisfaction du temps de traitement"],
        taux_participation=participation,
        rubrique_moins_satisfaisante=least_satisfying,
        nombre_reponses=int(len(rows_with_answer)),
        fallback_global=fallback_global,
    )


def calculate_month_kpi(df: pd.DataFrame, mois: str) -> KpiResult:
    opened = filter_opened_month(df, mois)
    opened_count = int(len(opened))

    has_resolution_date = _column_available(df, "tickets", "date_fermeture")
    closed = filter_closed_month(df, mois) if has_resolution_date else pd.DataFrame(columns=df.columns)
    closed_count = int(len(closed)) if has_resolution_date else None
    same_month_count = (
        int(len(closed[closed["mois_ouverture"].eq(mois)]))
        if has_resolution_date and "mois_ouverture" in closed.columns
        else None
    )

    has_delay = _column_available(df, "tickets", "delai_source") or has_resolution_date
    delay_minutes = _nullable_mean(closed["delai_resolution_minutes"]) if has_delay and not closed.empty else None
    delay_hours = delay_minutes / 60 if delay_minutes is not None else None
    delay_days = delay_minutes / 1440 if delay_minutes is not None else None

    return KpiResult(
        mois=mois,
        total_ouverts=opened_count,
        total_fermes=closed_count,
        ouverts_et_fermes_meme_mois=same_month_count,
        delai_moyen_minutes=delay_minutes,
        delai_moyen_heures=delay_hours,
        delai_moyen_jours=delay_days,
        satisfaction=satisfaction_summary(df, mois, opened_count),
    )


def monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = [calculate_month_kpi(df, month).as_dict() for month in available_months(df)]
    return pd.DataFrame(rows)


def distribution(df: pd.DataFrame, mois: str, column: str, top: int | None = None) -> pd.DataFrame:
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


def subjects_opened_month(df: pd.DataFrame, mois: str, top: int | None = None) -> pd.DataFrame:
    return distribution(df, mois, "categorie", top)


def recurrent_requesters(df: pd.DataFrame, mois: str | None = None, minimum: int = 5) -> pd.DataFrame:
    data = filter_opened_month(df, mois) if mois else df
    result = (
        data.groupby(["beneficiaire_id", "beneficiaire"], dropna=False, as_index=False)
        .size()
        .rename(columns={"size": "nombre_tickets"})
        .sort_values("nombre_tickets", ascending=False)
    )
    return result[result["nombre_tickets"] >= minimum]


def kpi_by_dimension(df: pd.DataFrame, mois: str, dimension: str) -> pd.DataFrame:
    opened = filter_opened_month(df, mois)
    if dimension not in opened.columns:
        return pd.DataFrame(columns=[dimension, "tickets_ouverts", "satisfaction_moyenne"])
    return (
        opened.groupby(dimension, dropna=False)
        .agg(tickets_ouverts=("ticket_id", "count"))
        .reset_index()
        .sort_values("tickets_ouverts", ascending=False)
    )


def tickets_by_site_pole(df: pd.DataFrame, mois: str) -> pd.DataFrame:
    opened = filter_opened_month(df, mois)
    pole_column = "pole" if "pole" in opened.columns else "department"
    if "site" not in opened.columns or pole_column not in opened.columns:
        return pd.DataFrame(columns=["site", "pole", "nombre_tickets"])
    result = (
        opened.groupby(["site", pole_column], dropna=False, as_index=False)
        .size()
        .rename(columns={pole_column: "pole", "size": "nombre_tickets"})
        .sort_values("nombre_tickets", ascending=False)
    )
    return result
