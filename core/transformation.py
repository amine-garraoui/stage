import logging
import unicodedata

import pandas as pd

from core.exceptions import SchemaError


LOGGER = logging.getLogger(__name__)

TICKET_REQUIRED_ALIASES = {
    "ticket_id": ["ticket_id", "id ticket", "n ticket", "numero ticket", "ticket"],
    "beneficiaire": ["beneficiaire", "demandeur", "utilisateur"],
    "beneficiaire_id": ["beneficiaire id", "login", "matricule"],
    "date_ouverture": ["date ouverture", "date d ouverture", "enregistre le", "date de creation"],
    "date_fermeture": ["date fermeture", "date de cloture", "date cloture", "date de resolution", "date resolution"],
    "categorie": ["categorie", "sujet", "subject", "type"],
    "priorite": ["priorite", "priority"],
    "site": ["site", "localisation", "beneficiaire localisation"],
    "groupe_traitant": ["groupe courant", "resolu par groupe", "group lng", "groupe traitant"],
    "intervenant": ["resolu par intervenant", "intervenant"],
    "statut": ["meta statut", "statut", "etat", "status"],
    "statut_detail": ["statut ticket"],
    "delai_source": ["delai de resolution min", "delai resolution min", "delai de resolution"],
}

TICKET_REQUIRED = [
    "ticket_id",
    "date_ouverture",
]

TICKET_OPTIONAL_DEFAULTS = {
    "beneficiaire": "Non renseigne",
    "beneficiaire_id": "",
    "date_fermeture": pd.NaT,
    "categorie": "Donnee indisponible",
    "site": "Donnee indisponible",
    "statut": "Donnee indisponible",
    "priorite": pd.NA,
    "groupe_traitant": "Donnee indisponible",
    "intervenant": "Donnee indisponible",
    "statut_detail": pd.NA,
    "delai_source": pd.NA,
}

SATISFACTION_ALIASES = {
    "ticket_id": ["ticket_id", "id ticket", "n ticket", "numero ticket", "ticket"],
    "date_enquete": ["date de creation", "date creation", "date enquete"],
    "satisfaction_traitement": ["satisfaction de traitement", "note traitement", "notes par criteres"],
    "communication_operateurs": ["communication des operateurs", "note communication"],
    "satisfaction_temps": ["satisfaction du temps de traitement", "note temps traitement", "note delai"],
    "commentaire": ["commentaire enquete", "commentaire"],
}

EMPLOYEE_ALIASES = {
    "beneficiaire": ["nom", "nom et prenom", "nom prenom"],
    "beneficiaire_id": ["login", "matricule"],
    "fonction": ["fonction"],
    "localisation_employe": ["localisation dernier niveau", "localisation"],
    "department": ["department", "departement"],
    "manager": ["manager"],
    "directeur": ["directeur"],
}

CLOSED_STATUSES = {
    "ferme",
    "fermee",
    "clos",
    "cloture",
    "cloturee",
    "resolu",
    "resolue",
    "termine",
    "terminee",
    "closed",
    "done",
}
OPEN_STATUSES = {"ouvert", "ouverte", "open", "nouveau", "nouvelle", "new"}
IN_PROGRESS_STATUSES = {
    "en cours",
    "en cours de traitement",
    "encours",
    "traitement",
    "en attente",
    "redirige",
    "redirigee",
    "pending",
    "in progress",
}


def normalize_text(value: object) -> str:
    text = str(value).replace("\ufeff", "").replace("\u00a0", " ").strip().strip('"').lower()
    text = text.replace("°", " ").replace("$", " ")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.replace("_", " ").replace(":", " ").replace("(", " ").replace(")", " ").split())


def _rename_with_aliases(df: pd.DataFrame, aliases: dict[str, list[str]]) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).replace("\ufeff", "").strip().strip('"') for col in df.columns]
    normalized = {normalize_text(col): col for col in df.columns}
    rename_map = {}
    column_sources = {}

    for standard, names in aliases.items():
        for name in names:
            key = normalize_text(name)
            if key in normalized:
                original = normalized[key]
                rename_map[original] = standard
                column_sources[standard] = original
                break

    renamed = df.rename(columns=rename_map)
    renamed.attrs["column_sources"] = column_sources
    return renamed


def validate_source_columns(
    raw: pd.DataFrame,
    aliases: dict[str, list[str]],
    required: list[str],
) -> dict[str, object]:
    renamed = _rename_with_aliases(raw, aliases)
    found_sources = renamed.attrs.get("column_sources", {})
    missing = [column for column in required if column not in found_sources]
    return {
        "ok": not missing,
        "missing": missing,
        "found": found_sources,
        "columns": list(raw.columns),
    }


def validate_tickets_source(raw: pd.DataFrame) -> dict[str, object]:
    return validate_source_columns(
        raw,
        TICKET_REQUIRED_ALIASES,
        ["date_ouverture", "date_fermeture", "site"],
    )


def validate_satisfaction_source(raw: pd.DataFrame) -> dict[str, object]:
    return validate_source_columns(
        raw,
        SATISFACTION_ALIASES,
        ["satisfaction_traitement", "communication_operateurs", "satisfaction_temps"],
    )


def validate_employees_source(raw: pd.DataFrame) -> dict[str, object]:
    return validate_source_columns(
        raw,
        EMPLOYEE_ALIASES,
        ["beneficiaire_id", "beneficiaire"],
    )


def detect_source_type(raw: pd.DataFrame) -> dict[str, object]:
    validations = {
        "demandes": validate_tickets_source(raw),
        "satisfaction": validate_satisfaction_source(raw),
        "employes": validate_employees_source(raw),
    }
    scores = {}
    for name, result in validations.items():
        found = result["found"]
        score = len(found) - (len(result["missing"]) * 2)
        if name == "satisfaction" and any(
            col in found for col in ["satisfaction_traitement", "communication_operateurs", "satisfaction_temps"]
        ):
            score += 10
        if name == "employes" and {"beneficiaire_id", "beneficiaire"}.issubset(set(found)):
            score += 10
        if name == "demandes" and {"date_ouverture", "date_fermeture", "site"}.issubset(set(found)):
            score += 8
        scores[name] = score
    detected = max(scores, key=scores.get)
    return {
        "detected": detected if scores[detected] > 0 else None,
        "scores": scores,
        "validations": validations,
    }


def _require_columns(df: pd.DataFrame, required: list[str], label: str) -> None:
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise SchemaError(f"Missing columns in {label}: {', '.join(missing)}")


def parse_dates(series: pd.Series) -> pd.Series:
    text = series.astype(str).str.strip()
    iso_mask = text.str.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}")
    dates = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    dates.loc[iso_mask] = pd.to_datetime(series.loc[iso_mask], errors="coerce", yearfirst=True)
    dates.loc[~iso_mask] = pd.to_datetime(series.loc[~iso_mask], errors="coerce", dayfirst=True)
    return dates


def normalize_status(status: object) -> str:
    key = normalize_text(status)
    if key in CLOSED_STATUSES:
        return "Ferme"
    if key in OPEN_STATUSES:
        return "Ouvert"
    if key in IN_PROGRESS_STATUSES:
        return "En cours"
    if not key or key == "nan":
        return "Non renseigne"
    return str(status).strip().title()


def parse_number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.replace(",", ".", regex=False), errors="coerce")


def parse_duration_minutes(series: pd.Series) -> pd.Series:
    text = series.astype(str).str.strip()
    result = pd.to_numeric(text.str.replace(",", ".", regex=False), errors="coerce")

    mask_hhmm = text.str.match(r"^\d+:\d{2}$")
    parts = text[mask_hhmm].str.split(":", expand=True)
    if not parts.empty:
        result.loc[mask_hhmm] = pd.to_numeric(parts[0], errors="coerce") * 60 + pd.to_numeric(
            parts[1], errors="coerce"
        )

    return result


def standardize_tickets(raw: pd.DataFrame) -> pd.DataFrame:
    df = _rename_with_aliases(raw, TICKET_REQUIRED_ALIASES)
    column_sources = df.attrs.get("column_sources", {})
    _require_columns(df, TICKET_REQUIRED, "tickets")

    for col, default in TICKET_OPTIONAL_DEFAULTS.items():
        if col not in df.columns:
            df[col] = default

    keep = TICKET_REQUIRED + [col for col in TICKET_OPTIONAL_DEFAULTS if col not in TICKET_REQUIRED]
    df = df[keep].copy()
    df["ticket_id"] = df["ticket_id"].astype(str).str.strip()
    df["beneficiaire"] = df["beneficiaire"].fillna("Non renseigne").astype(str).str.strip()
    df["beneficiaire_id"] = df["beneficiaire_id"].fillna("").astype(str).str.strip().str.upper()
    df["date_ouverture"] = parse_dates(df["date_ouverture"])
    df["date_fermeture"] = parse_dates(df["date_fermeture"])
    df["statut"] = df["statut"].map(normalize_status)
    df["site"] = df["site"].fillna("Non renseigne").astype(str).str.strip().replace("", "Non renseigne")
    df["categorie"] = df["categorie"].fillna("Non renseigne").astype(str).str.strip().replace("", "Non renseigne")
    df["priorite"] = parse_number(df["priorite"])
    df["groupe_traitant"] = df["groupe_traitant"].fillna("Non renseigne").astype(str).str.strip()
    df["intervenant"] = df["intervenant"].fillna("Non renseigne").astype(str).str.strip()
    df["statut_detail"] = df["statut_detail"].fillna("").astype(str).str.strip()

    df = df.dropna(subset=["date_ouverture"]).copy()
    df["mois_ouverture"] = df["date_ouverture"].dt.to_period("M").astype(str)
    df["mois_fermeture"] = df["date_fermeture"].dt.to_period("M").astype(str)
    df.loc[df["date_fermeture"].isna(), "mois_fermeture"] = pd.NA
    df["est_ferme"] = df["statut"].eq("Ferme")

    df["delai_resolution_minutes"] = parse_duration_minutes(df["delai_source"])
    date_delta_minutes = (df["date_fermeture"] - df["date_ouverture"]).dt.total_seconds() / 60
    df["delai_resolution_minutes"] = df["delai_resolution_minutes"].fillna(date_delta_minutes)
    df.loc[df["delai_resolution_minutes"] < 0, "delai_resolution_minutes"] = pd.NA
    df["delai_resolution_jours"] = df["delai_resolution_minutes"] / 1440
    df.attrs["column_sources"] = {"tickets": column_sources}

    return df


def standardize_satisfaction(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame(columns=["ticket_id", "satisfaction", "communication", "satisfaction_temps"])

    df = _rename_with_aliases(raw, SATISFACTION_ALIASES)
    column_sources = df.attrs.get("column_sources", {})
    _require_columns(df, ["ticket_id"], "satisfaction")

    for col in ["satisfaction_traitement", "communication_operateurs", "satisfaction_temps"]:
        if col not in df.columns:
            df[col] = pd.NA
    if "date_enquete" not in df.columns:
        df["date_enquete"] = pd.NaT

    df["ticket_id"] = df["ticket_id"].astype(str).str.strip()
    df["date_enquete"] = parse_dates(df["date_enquete"])
    df["mois_enquete"] = df["date_enquete"].dt.to_period("M").astype(str)
    df.loc[df["date_enquete"].isna(), "mois_enquete"] = pd.NA
    df["satisfaction_traitement"] = parse_number(df["satisfaction_traitement"])
    df["communication_operateurs"] = parse_number(df["communication_operateurs"])
    df["satisfaction_temps"] = parse_number(df["satisfaction_temps"])
    df["satisfaction"] = df[
        ["satisfaction_traitement", "communication_operateurs", "satisfaction_temps"]
    ].mean(axis=1)

    result = df[
        [
            "ticket_id",
            "date_enquete",
            "mois_enquete",
            "satisfaction",
            "satisfaction_traitement",
            "communication_operateurs",
            "satisfaction_temps",
        ]
    ].copy()
    result.attrs["column_sources"] = {"satisfaction": column_sources}
    return result


def standardize_employees(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame(columns=["beneficiaire_id", "fonction", "localisation_employe", "department", "manager", "directeur"])

    df = _rename_with_aliases(raw, EMPLOYEE_ALIASES)
    column_sources = df.attrs.get("column_sources", {})
    _require_columns(df, ["beneficiaire_id"], "employees")

    for col in ["fonction", "localisation_employe", "department", "manager", "directeur"]:
        if col not in df.columns:
            df[col] = "Non renseigne"

    df["beneficiaire_id"] = df["beneficiaire_id"].fillna("").astype(str).str.strip().str.upper()
    for col in ["fonction", "localisation_employe", "department", "manager", "directeur"]:
        df[col] = df[col].fillna("Non renseigne").astype(str).str.strip().replace("", "Non renseigne")

    result = df[["beneficiaire_id", "fonction", "localisation_employe", "department", "manager", "directeur"]].drop_duplicates(
        "beneficiaire_id"
    )
    result.attrs["column_sources"] = {"employees": column_sources}
    return result


def build_dataset(
    tickets_raw: pd.DataFrame,
    satisfaction_raw: pd.DataFrame | None = None,
    employees_raw: pd.DataFrame | None = None,
) -> pd.DataFrame:
    tickets = standardize_tickets(tickets_raw)
    satisfaction = standardize_satisfaction(satisfaction_raw if satisfaction_raw is not None else pd.DataFrame())
    employees = standardize_employees(employees_raw if employees_raw is not None else pd.DataFrame())

    df = tickets.merge(satisfaction, on="ticket_id", how="left")
    df = df.merge(employees, on="beneficiaire_id", how="left")

    for col in ["fonction", "localisation_employe", "department", "manager", "directeur"]:
        if col not in df.columns:
            df[col] = "Non renseigne"
        df[col] = df[col].fillna("Non renseigne")

    df.attrs["satisfaction_responses"] = satisfaction
    df.attrs["column_sources"] = {
        **tickets.attrs.get("column_sources", {}),
        **satisfaction.attrs.get("column_sources", {}),
        **employees.attrs.get("column_sources", {}),
    }
    return df
