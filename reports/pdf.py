from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from core import kpi


def _fmt(value) -> str:
    if value is None or pd.isna(value):
        return "Donnee indisponible"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def _table_from_df(df: pd.DataFrame, max_rows: int = 10) -> Table:
    data = [list(df.columns)] + df.head(max_rows).fillna("N/A").astype(str).values.tolist()
    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F6FA")]),
            ]
        )
    )
    return table


def export_month_pdf(df: pd.DataFrame, mois: str, output_dir: str | Path, company_name: str = "Sagemcom RSI") -> Path:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    path = output / f"rapport_kpi_{mois}.pdf"

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=24, leftMargin=24, topMargin=28, bottomMargin=28)
    result = kpi.calculate_month_kpi(df, mois)
    story = [
        Paragraph(company_name, styles["Title"]),
        Paragraph(f"Rapport KPI support IT - {mois}", styles["Heading2"]),
        Spacer(1, 12),
    ]

    summary_data = [
        ["Indicateur", "Valeur"],
        ["Tickets ouverts", result.total_ouverts],
        ["Tickets fermes", result.total_fermes],
        ["Ouverts et fermes meme mois", _fmt(result.ouverts_et_fermes_meme_mois)],
        ["Delai moyen heures", _fmt(result.delai_moyen_heures)],
        ["Satisfaction traitement", _fmt(result.satisfaction.satisfaction_globale)],
        ["Communication", _fmt(result.satisfaction.communication)],
        ["Temps percu", _fmt(result.satisfaction.temps_percu)],
        ["Taux participation", _fmt(result.satisfaction.taux_participation)],
        ["Rubrique moins satisfaisante", _fmt(result.satisfaction.rubrique_moins_satisfaisante)],
    ]
    story.append(Table(summary_data, style=[
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ]))
    story.append(Spacer(1, 16))

    story.append(Paragraph("Repartition par site", styles["Heading3"]))
    story.append(_table_from_df(kpi.distribution(df, mois, "site"), max_rows=8))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Sujets ouverts du mois", styles["Heading3"]))
    story.append(_table_from_df(kpi.subjects_opened_month(df, mois), max_rows=8))

    doc.build(story)
    return path
