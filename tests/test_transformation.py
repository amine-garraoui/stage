import pandas as pd

from core.transformation import build_dataset


def test_build_dataset_normalizes_askit_ticket_columns():
    raw = pd.DataFrame(
        {
            "N° ticket": ["S1"],
            "Bénéficiaire": ["USER, Test"],
            "Bénéficiaire ID": ["g123"],
            "Enregistré le": ["01/06/2026 08:00:00"],
            "Date de résolution": ["02/06/2026 08:00:00"],
            "Sujet": ["VPN"],
            "Priorité": ["3"],
            "Bénéficiaire : Localisation": ["Tunisie/Kram"],
            "Meta Statut": ["Terminé"],
        }
    )
    df = build_dataset(raw)

    assert len(df) == 1
    assert df.iloc[0]["ticket_id"] == "S1"
    assert df.iloc[0]["statut"] == "Ferme"
    assert df.iloc[0]["beneficiaire_id"] == "G123"
