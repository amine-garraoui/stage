"""
core/anonymisation.py
─────────────────────
Centralise la suppression des colonnes personnelles identifiantes.

Règle d'usage : appeler `anonymiser(raw_df)` immédiatement après chaque
lecture de fichier (pd.read_csv / read_excel), avant toute autre opération.
Aucune donnée nominative ne doit transiter au-delà de cette barrière.
"""

import logging
import unicodedata

import pandas as pd

LOGGER = logging.getLogger(__name__)

# ── Colonnes à supprimer dès l'ingestion ───────────────────────────────────
# Liste canonique (formes normalisées, sans accents, en minuscules).
# Si un alias ou une variante doit être ajouté, c'est ici — nulle part ailleurs.
_SENSITIVE_NORMALIZED = frozenset(
    {
        # Noms
        "nom",
        "prenom",
        "nom prenom",
        "nom et prenom",
        "nomprenom",
        "nom complet",
        "fullname",
        "full name",
        "name",
        # Emails
        "email",
        "e mail",
        "mail",
        "adresse mail",
        "adresse email",
        "courriel",
        # Téléphones
        "telephone",
        "tel",
        "phone",
        "mobile",
        "gsm",
        "numero de telephone",
        "phone number",
        # Adresses physiques
        "adresse",
        "address",
        "rue",
        "code postal",
        # Identifiants indirects (conservés seulement sous forme d'ID technique)
        "nom beneficiaire",
        "beneficiaire nom",
        "demandeur nom",
        # Commentaires libres (risque d'identification par le contenu)
        "commentaire",
        "commentaire enquete",
        "commentaires",
        "comment",
        "notes libres",
        "observations",
        "remarques",
    }
)


def _normalize(text: str) -> str:
    """Normalise un nom de colonne pour la comparaison : minuscules, sans accents, sans doubles espaces."""
    text = str(text).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.split())


def anonymiser(df: pd.DataFrame) -> pd.DataFrame:
    """
    Supprime immédiatement et de façon irréversible toutes les colonnes
    contenant des données personnelles identifiantes.

    Doit être appelée juste après chaque pd.read_csv() / pd.read_excel(),
    avant toute autre transformation ou calcul.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame brut issu d'une lecture de fichier.

    Returns
    -------
    pd.DataFrame
        Copie du DataFrame sans aucune colonne sensible.
    """
    colonnes_a_supprimer = [
        col for col in df.columns
        if _normalize(col) in _SENSITIVE_NORMALIZED
    ]

    if colonnes_a_supprimer:
        LOGGER.info(
            "anonymiser() — suppression de %d colonne(s) sensible(s) : %s",
            len(colonnes_a_supprimer),
            colonnes_a_supprimer,
        )

    return df.drop(columns=colonnes_a_supprimer, errors="ignore")


def colonnes_sensibles_presentes(df: pd.DataFrame) -> list[str]:
    """
    Retourne la liste des colonnes sensibles détectées dans df.
    Utile pour les tests et la journalisation — ne supprime rien.
    """
    return [
        col for col in df.columns
        if _normalize(col) in _SENSITIVE_NORMALIZED
    ]
