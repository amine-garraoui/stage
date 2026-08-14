import logging
import unicodedata

import pandas as pd

from core.anonymisation import anonymiser
from core.exceptions import SchemaError


LOGGER = logging.getLogger(__name__)

# ── Mapping Directeur → Pôle (source : cahier des charges) ────────────────
# GAVOILLE, Laurent : ambiguite dans les donnees juin 2026.
# Le rapport officiel classe son ticket Kram en E&T et son ticket Megrine en supports.
DIRECTEUR_POLE: dict[str, str] = {
    "MASMOUDI, Oussema": "BBS",
    "MAROUFI, Walid":    "E&T",
    "SAMANDI, Sami":     "AVS",
    "BEN ABDALLAH, Mehdi": "supports",
    "JANNOT, Christian": "supports",
    "BEN SALAH, Naoufel": "BBS",
    "GAVOILLE, Laurent": "supports",
}

EXCLUDED_SERVICE_CATEGORIES = {
    "on boarding sst/krm",
    "off boarding",
    "materiel avs",
}

OFFICIAL_POLES = {"avs", "bbs", "e&t", "supports"}


def directeur_vers_pole(directeur: str) -> str:
    """Retourne le pôle correspondant au directeur, ou 'Non déterminé' si inconnu."""
    if not directeur or directeur == "Non renseigne":
        return "Non déterminé"
    return DIRECTEUR_POLE.get(directeur.strip(), "Non déterminé")

TICKET_REQUIRED_ALIASES = {
    "ticket_id": ["ticket_id", "id ticket", "n ticket", "numero ticket", "ticket"],
    "beneficiaire": ["beneficiaire", "demandeur", "utilisateur"],
    "beneficiaire_id": ["beneficiaire id", "login", "matricule"],
    "directeur": ["directeur"],
    "date_ouverture": ["date ouverture", "date d ouverture", "enregistre le", "date de creation"],
    "date_fermeture": ["date fermeture", "date de cloture", "date cloture", "date de resolution", "date resolution"],
    "categorie": ["categorie", "sujet", "subject", "type"],
    "priorite": ["priorite", "priority"],
    "e_reponses": ["e reponses", "e_reponses"],
    "description": ["description"],
    "vip_level": ["beneficiaire niveau de vip", "niveau de vip"],
    "site": ["site", "localisation", "beneficiaire localisation"],
    "group_lng": ["group lng"],
    "groupe_resolu": ["resolu par groupe"],
    "groupe_traitant": ["groupe courant", "resolu par groupe", "group lng", "groupe traitant"],
    "intervenant": ["resolu par intervenant", "intervenant"],
    "group_lng_resolution": ["group lng 1"],
    "statut": ["meta statut", "statut", "etat", "status"],
    "statut_detail": ["statut ticket"],
    "delai_source": ["delai de resolution min", "delai resolution min", "delai de resolution"],
    "workflow": ["workflow"],
}

TICKET_REQUIRED = [
    "ticket_id",
    "date_ouverture",
]

TICKET_OPTIONAL_DEFAULTS = {
    "beneficiaire": "Non renseigne",
    "beneficiaire_id": "",
    "directeur": "Non renseigne",
    "date_fermeture": pd.NaT,
    "categorie": "Donnee indisponible",
    "priorite": pd.NA,
    "e_reponses": "",
    "description": "",
    "vip_level": "",
    "site": "Donnee indisponible",
    "group_lng": "",
    "groupe_resolu": "Donnee indisponible",
    "groupe_traitant": "Donnee indisponible",
    "intervenant": "Donnee indisponible",
    "group_lng_resolution": "",
    "statut": "Donnee indisponible",
    "statut_detail": pd.NA,
    "delai_source": pd.NA,
    "workflow": "",
}

SATISFACTION_ALIASES = {
    "ticket_id": ["ticket_id", "id ticket", "n ticket", "numero ticket", "ticket"],
    "date_enquete": ["date de creation", "date creation", "date enquete"],
    "date_resolution": ["date de resolution", "date resolution"],
    "groupe_resolu": ["resolu par groupe"],
    "intervenant": ["resolu par intervenant", "intervenant"],
    "categorie": ["sujet", "categorie", "subject", "type"],
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
        TICKET_REQUIRED,
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
        if name == "demandes" and set(TICKET_REQUIRED).issubset(set(found)):
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


def _is_informative_text(value: object) -> bool:
    key = normalize_text(value)
    return bool(key and key not in {"nan", "-", "non renseigne", "non determine"})


def _is_official_pole(value: object) -> bool:
    return normalize_text(value) in OFFICIAL_POLES


def standardize_tickets(raw: pd.DataFrame) -> pd.DataFrame:
    raw = anonymiser(raw)  # ← suppression immédiate des colonnes sensibles
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
    df = df[~df["categorie"].map(normalize_text).isin(EXCLUDED_SERVICE_CATEGORIES)].copy()
    df["priorite"] = parse_number(df["priorite"])
    for col in ["directeur", "e_reponses", "description", "vip_level", "group_lng", "groupe_resolu", "group_lng_resolution", "workflow"]:
        df[col] = df[col].fillna("").astype(str).str.strip()
    df["groupe_traitant"] = df["groupe_traitant"].fillna("Non renseigne").astype(str).str.strip()
    df["intervenant"] = df["intervenant"].fillna("Non renseigne").astype(str).str.strip()
    df["statut_detail"] = df["statut_detail"].fillna("").astype(str).str.strip()

    df = df.dropna(subset=["date_ouverture"]).drop_duplicates("ticket_id", keep="last").copy()
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

    raw = anonymiser(raw)  # ← suppression immédiate des colonnes sensibles
    df = _rename_with_aliases(raw, SATISFACTION_ALIASES)
    column_sources = df.attrs.get("column_sources", {})
    _require_columns(df, ["ticket_id"], "satisfaction")

    for col in ["satisfaction_traitement", "communication_operateurs", "satisfaction_temps"]:
        if col not in df.columns:
            df[col] = pd.NA
    if "date_enquete" not in df.columns:
        df["date_enquete"] = pd.NaT
    if "date_resolution" not in df.columns:
        df["date_resolution"] = pd.NaT
    for col in ["groupe_resolu", "intervenant", "categorie"]:
        if col not in df.columns:
            df[col] = ""

    df["ticket_id"] = df["ticket_id"].astype(str).str.strip()
    df["date_enquete"] = parse_dates(df["date_enquete"])
    df["date_resolution"] = parse_dates(df["date_resolution"])
    month_source = df["date_resolution"].where(df["date_resolution"].notna(), df["date_enquete"])
    df["mois_enquete"] = month_source.dt.to_period("M").astype(str)
    df.loc[month_source.isna(), "mois_enquete"] = pd.NA
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
            "date_resolution",
            "groupe_resolu",
            "intervenant",
            "categorie",
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
        return pd.DataFrame(columns=["beneficiaire_id", "fonction", "localisation_employe", "department", "manager", "directeur", "pole"])

    # Renommer d'abord (pour récupérer beneficiaire_id / directeur),
    # puis anonymiser uniquement les colonnes non encore standardisées.
    df = _rename_with_aliases(raw, EMPLOYEE_ALIASES)
    column_sources = df.attrs.get("column_sources", {})
    # Supprimer les colonnes sensibles brutes qui ne sont pas encore renommées
    # (les colonnes déjà renommées en beneficiaire_id / directeur sont conservées).
    colonnes_brutes_restantes = [c for c in df.columns if c not in EMPLOYEE_ALIASES]
    df_anon = anonymiser(df[colonnes_brutes_restantes].copy())
    df = pd.concat([df[[c for c in EMPLOYEE_ALIASES if c in df.columns]], df_anon], axis=1)
    df.attrs["column_sources"] = column_sources
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

    satisfaction_for_join = satisfaction.drop_duplicates("ticket_id", keep="last")
    df = tickets.merge(satisfaction_for_join, on="ticket_id", how="left", suffixes=("", "_satisfaction"))
    df = df.merge(employees, on="beneficiaire_id", how="left", suffixes=("", "_employe"))

    if "directeur_employe" in df.columns:
        df["directeur"] = df["directeur"].where(
            df["directeur"].map(_is_informative_text),
            df["directeur_employe"],
        )

    for col in ["fonction", "localisation_employe", "department", "manager", "directeur"]:
        if col not in df.columns:
            df[col] = "Non renseigne"
        df[col] = df[col].fillna("Non renseigne")

    # ── Colonne pôle ──────────────────────────────────────────────────────
    # Priorité 1 : colonne "pole" déjà présente (export ASKit enrichi).
    # Priorité 2 : colonne "department" déjà présente (export ASKit).
    # Priorité 3 : calcul depuis le mapping Directeur → Pôle.
    if "pole" not in df.columns or df["pole"].isna().all() or df["pole"].eq("Non renseigne").all():
        if "department" in df.columns and df["department"].map(_is_official_pole).any():
            df["pole"] = df["department"].where(
                df["department"].map(_is_official_pole),
                df["directeur"].map(lambda d: directeur_vers_pole(str(d))),
            )
        else:
            df["pole"] = df["directeur"].map(lambda d: directeur_vers_pole(str(d)))
    df["pole"] = df["pole"].fillna("Non déterminé")
    gavoille = df["directeur"].astype(str).str.strip().eq("GAVOILLE, Laurent")
    df.loc[gavoille & df["site"].astype(str).str.casefold().eq("Tunisie/Kram".casefold()), "pole"] = "E&T"
    df.loc[gavoille & df["site"].astype(str).str.casefold().eq("Tunisie/Megrine".casefold()), "pole"] = "supports"

    df.attrs["satisfaction_responses"] = satisfaction
    df.attrs["column_sources"] = {
        **tickets.attrs.get("column_sources", {}),
        **satisfaction.attrs.get("column_sources", {}),
        **employees.attrs.get("column_sources", {}),
    }
    return df
