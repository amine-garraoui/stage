"""
tests/test_anonymisation.py
────────────────────────────
Tests de la fonction anonymiser() et de son intégration dans le pipeline.
"""

import pandas as pd
import pytest

from core.anonymisation import anonymiser, colonnes_sensibles_presentes


class TestAnonymiser:
    def test_supprime_nom(self):
        df = pd.DataFrame({"nom": ["Jean Dupont"], "ticket_id": ["T1"]})
        result = anonymiser(df)
        assert "nom" not in result.columns
        assert "ticket_id" in result.columns

    def test_supprime_email(self):
        df = pd.DataFrame({"email": ["j@example.com"], "ticket_id": ["T1"]})
        result = anonymiser(df)
        assert "email" not in result.columns

    def test_supprime_telephone(self):
        df = pd.DataFrame({"telephone": ["0600000000"], "site": ["Kram"]})
        result = anonymiser(df)
        assert "telephone" not in result.columns
        assert "site" in result.columns

    def test_supprime_commentaire(self):
        df = pd.DataFrame({"commentaire": ["Très satisfait"], "ticket_id": ["T1"]})
        result = anonymiser(df)
        assert "commentaire" not in result.columns

    def test_supprime_prenom(self):
        df = pd.DataFrame({"prenom": ["Jean"], "ticket_id": ["T1"]})
        result = anonymiser(df)
        assert "prenom" not in result.columns

    def test_conserve_id_technique(self):
        """beneficiaire_id (ID technique) ne doit PAS être supprimé."""
        df = pd.DataFrame({"beneficiaire_id": ["USR001"], "nom": ["Jean"]})
        result = anonymiser(df)
        assert "beneficiaire_id" in result.columns
        assert "nom" not in result.columns

    def test_conserve_directeur(self):
        """La colonne directeur (nom de directeur pour mapping pôle) est conservée."""
        df = pd.DataFrame({
            "directeur": ["SAMANDI, Sami"],
            "beneficiaire_id": ["USR001"],
            "nom": ["Jean"],
        })
        result = anonymiser(df)
        assert "directeur" in result.columns
        assert "nom" not in result.columns

    def test_df_vide_inchange(self):
        df = pd.DataFrame()
        result = anonymiser(df)
        assert result.empty

    def test_pas_de_colonnes_sensibles(self):
        df = pd.DataFrame({"ticket_id": ["T1"], "site": ["Kram"], "statut": ["Ferme"]})
        result = anonymiser(df)
        assert list(result.columns) == list(df.columns)

    def test_insensible_majuscules_accents(self):
        """Doit supprimer 'Prénom', 'EMAIL', 'Téléphone' etc."""
        df = pd.DataFrame({
            "Prénom": ["Marie"],
            "EMAIL": ["m@x.com"],
            "Téléphone": ["060"],
            "ticket_id": ["T1"],
        })
        result = anonymiser(df)
        assert "Prénom" not in result.columns
        assert "EMAIL" not in result.columns
        assert "Téléphone" not in result.columns
        assert "ticket_id" in result.columns

    def test_renvoie_copie(self):
        """anonymiser() ne modifie pas le DataFrame original."""
        df = pd.DataFrame({"nom": ["Jean"], "ticket_id": ["T1"]})
        original_cols = list(df.columns)
        _ = anonymiser(df)
        assert list(df.columns) == original_cols


class TestColonnesSensiblesPresentes:
    def test_detecte_colonnes(self):
        df = pd.DataFrame({"nom": ["A"], "email": ["b@c.com"], "site": ["Kram"]})
        detected = colonnes_sensibles_presentes(df)
        assert "nom" in detected
        assert "email" in detected
        assert "site" not in detected

    def test_df_propre(self):
        df = pd.DataFrame({"ticket_id": ["T1"], "site": ["Kram"]})
        assert colonnes_sensibles_presentes(df) == []


class TestIntegrationTransformation:
    """Vérifie que anonymiser() est bien appelé dans le pipeline de transformation."""

    def test_standardize_tickets_retire_nom(self):
        from core.transformation import standardize_tickets
        raw = pd.DataFrame({
            "N° ticket": ["T1"],
            "Enregistré le": ["2026-06-01"],
            "Date de résolution": ["2026-06-10"],
            "nom": ["Jean Dupont"],       # doit être supprimé
            "email": ["j@x.com"],         # doit être supprimé
            "Meta Statut": ["Fermé"],
            "Bénéficiaire : Localisation": ["Kram"],
            "Sujet": ["VPN"],
        })
        df = standardize_tickets(raw)
        assert "nom" not in df.columns
        assert "email" not in df.columns
        assert "ticket_id" in df.columns

    def test_standardize_satisfaction_retire_commentaire(self):
        from core.transformation import standardize_satisfaction
        raw = pd.DataFrame({
            "N° ticket": ["T1"],
            "Satisfaction de traitement": [5.0],
            "Communication des opérateurs": [4.0],
            "Satisfaction du temps de traitement": [5.0],
            "commentaire": ["Super service"],   # doit être supprimé
        })
        df = standardize_satisfaction(raw)
        assert "commentaire" not in df.columns
        assert "satisfaction_traitement" in df.columns
