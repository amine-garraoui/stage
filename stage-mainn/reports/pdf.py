"""
reports/pdf.py
──────────────
Export PDF du rapport KPI mensuel RSI Sagemcom.

Sections du rapport (fidèles au cahier des charges) :
  1. En-tête  — société, mois, date de génération
  2. KPI      — tableau des indicateurs principaux
  3. Satisfaction — taux global + tableau comptage par niveau par rubrique
  4. Par site — tableau nombre de tickets par site
  5. Par site et pôle — croisement site × pôle
  6. Sujets   — répartition types de demandes

Règles confidentialité (section 9 cahier des charges) :
  - Aucun nom, email, téléphone ou identifiant individuel n'est exporté.
  - Toutes les données sont agrégées (site, pôle, mois, sujet).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend
from reportlab.lib.colors import HexColor

from core import kpi

# ── Palette RSI Sagemcom ───────────────────────────────────────────────────
_BLUE_DARK  = colors.HexColor("#1F4E78")
_BLUE_MID   = colors.HexColor("#2E75B6")
_BLUE_LIGHT = colors.HexColor("#DEEAF1")
_GREEN      = colors.HexColor("#375623")
_GREEN_LIGHT= colors.HexColor("#C6EFCE")
_RED_LIGHT  = colors.HexColor("#FFCCCC")
_GREY       = colors.HexColor("#F3F6FA")
_GREY_DARK  = colors.HexColor("#CCCCCC")
_WHITE      = colors.white
_BLACK      = colors.black


def _fmt(value, suffix: str = "") -> str:
    """Formate une valeur pour l'affichage PDF."""
    if value is None:
        return "Donnée indisponible"
    try:
        if pd.isna(value):
            return "Donnée indisponible"
    except (TypeError, ValueError):
        pass
    if isinstance(value, float):
        return f"{value:.2f}{suffix}"
    return f"{value}{suffix}"


def _base_table_style() -> TableStyle:
    return TableStyle([
        ("BACKGROUND",    (0, 0), (-1,  0), _BLUE_DARK),
        ("TEXTCOLOR",     (0, 0), (-1,  0), _WHITE),
        ("FONTNAME",      (0, 0), (-1,  0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1,  0), 9),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [_WHITE, _GREY]),
        ("FONTSIZE",      (0, 1), (-1, -1), 8),
        ("GRID",          (0, 0), (-1, -1), 0.3,  _GREY_DARK),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ])


def _df_to_table(df: pd.DataFrame, max_rows: int = 15, col_widths=None) -> Table:
    """Convertit un DataFrame en Table ReportLab."""
    data = [list(df.columns)]
    for _, row in df.head(max_rows).iterrows():
        data.append([str(v) if not (isinstance(v, float) and pd.isna(v)) else "N/A" for v in row])
    table = Table(data, repeatRows=1, colWidths=col_widths)
    table.setStyle(_base_table_style())
    return table


def _section_heading(text: str, styles) -> list:
    """Retourne un séparateur + titre de section."""
    return [
        Spacer(1, 10),
        HRFlowable(width="100%", thickness=1, color=_BLUE_MID, spaceAfter=4),
        Paragraph(text, styles["Heading3"]),
        Spacer(1, 4),
    ]


def _bar_chart(labels: list[str], values: list[float], title: str, width: float = 470, height: float = 190) -> Drawing:
    drawing = Drawing(width, height)
    chart = VerticalBarChart()
    chart.x = 48
    chart.y = 35
    chart.width = width - 68
    chart.height = height - 65
    chart.data = [values]
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.boxAnchor = "ne"
    chart.categoryAxis.labels.angle = 25
    chart.categoryAxis.labels.fontSize = 7
    chart.valueAxis.valueMin = 0
    chart.valueAxis.labels.fontSize = 8
    chart.bars[0].fillColor = HexColor("#2E75B6")
    chart.bars[0].strokeColor = HexColor("#1F4E78")
    chart.barSpacing = 5
    drawing.add(chart)
    drawing.add(String(0, height - 12, title, fontSize=9, fillColor=_BLUE_DARK))
    return drawing


def _comparison_chart(labels: list[str], previous: list[float], current: list[float], title: str, width: float = 470, height: float = 205) -> Drawing:
    drawing = Drawing(width, height)
    chart = VerticalBarChart()
    chart.x = 48
    chart.y = 38
    chart.width = width - 68
    chart.height = height - 70
    chart.data = [previous, current]
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.boxAnchor = "ne"
    chart.categoryAxis.labels.angle = 25
    chart.categoryAxis.labels.fontSize = 7
    chart.valueAxis.valueMin = 0
    chart.valueAxis.labels.fontSize = 8
    chart.bars[0].fillColor = HexColor("#9DBAD0")
    chart.bars[1].fillColor = HexColor("#2E75B6")
    chart.groupSpacing = 8
    drawing.add(chart)
    drawing.add(String(0, height - 12, title, fontSize=9, fillColor=_BLUE_DARK))
    drawing.add(String(width - 150, 8, "Précédent · Sélectionné", fontSize=7, fillColor=_BLUE_DARK))
    return drawing


def _comparison_table(comparison: pd.DataFrame, styles) -> Table:
    rows = [["Indicateur", "Précédent", "Sélectionné", "Écart", "Variation"]]
    for _, row in comparison.iterrows():
        suffix = row["Suffixe"]
        previous = _fmt(row["Valeur précédente"], suffix)
        current = _fmt(row["Valeur sélectionnée"], suffix)
        delta = _fmt(row["Écart"], suffix)
        variation = _fmt(row["Variation"], " %")
        rows.append([row["Indicateur"], previous, current, delta, variation])
    table = Table(rows, repeatRows=1, colWidths=[150, 85, 85, 75, 75])
    table.setStyle(_base_table_style())
    return table


def _interpretation(result, df_site: pd.DataFrame, df_subj: pd.DataFrame, mois: str, styles) -> list:
    messages = []
    if not df_site.empty:
        top_site = df_site.sort_values("nombre_tickets", ascending=False).iloc[0]
        messages.append(f"Le site le plus sollicité est <b>{top_site['site']}</b> avec {int(top_site['nombre_tickets'])} demandes ouvertes.")
    if not df_subj.empty:
        top_subject = df_subj.sort_values("nombre_tickets", ascending=False).iloc[0]
        messages.append(f"Le sujet dominant est <b>{top_subject['categorie']}</b> ({int(top_subject['nombre_tickets'])} demandes).")
    if result.delai_moyen_jours is not None:
        messages.append(f"Le délai moyen de traitement est de <b>{result.delai_moyen_jours:.2f} jour(s)</b>.")
    if result.satisfaction.satisfaction_globale is not None:
        messages.append(f"La satisfaction globale atteint <b>{result.satisfaction.satisfaction_globale:.1f} %</b>.")
    if not messages:
        messages.append("Les données disponibles ne permettent pas de produire une interprétation pour ce mois.")
    return [Paragraph("<b>Lecture rapide</b> · " + " ".join(messages), styles["Normal"]), Spacer(1, 8)]


def export_month_pdf(
    df: pd.DataFrame,
    mois: str,
    output_dir: str | Path,
    company_name: str = "Sagemcom RSI",
) -> Path:
    """
    Génère le rapport PDF mensuel pour le mois sélectionné.

    Parameters
    ----------
    df           : DataFrame standardisé issu de build_dataset()
    mois         : Mois au format "YYYY-MM"
    output_dir   : Répertoire de destination
    company_name : Nom affiché dans l'en-tête

    Returns
    -------
    Path vers le fichier PDF généré.
    """
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    path = output / f"rapport_kpi_{mois}.pdf"

    styles = getSampleStyleSheet()
    # Style titre principal
    title_style = ParagraphStyle(
        "RSITitle",
        parent=styles["Title"],
        textColor=_BLUE_DARK,
        fontSize=18,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "RSISubtitle",
        parent=styles["Normal"],
        textColor=_BLUE_MID,
        fontSize=11,
        spaceAfter=2,
    )
    styles["Heading3"].textColor = _BLUE_DARK
    styles["Heading3"].spaceBefore = 6

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    result = kpi.calculate_month_kpi(df, mois)
    sat = result.satisfaction
    page_width = A4[0] - 4 * cm  # largeur utilisable

    story = []

    # ── En-tête ────────────────────────────────────────────────────────
    story.append(Paragraph(company_name, title_style))
    story.append(Paragraph(f"Rapport KPI Support IT — {mois}", subtitle_style))
    story.append(Paragraph(f"Généré le {date.today().strftime('%d/%m/%Y')}", styles["Normal"]))
    story.append(Spacer(1, 14))

    # ── 1. KPI principaux ──────────────────────────────────────────────
    story += _section_heading("1. Indicateurs principaux du mois", styles)

    kpi_data = [
        ["Indicateur", "Valeur", "Définition"],
        ["Demandes ouvertes",             str(result.total_ouverts),           "date_ouverture dans le mois"],
        ["Global traitées",               _fmt(result.total_fermes),            "date_fermeture dans le mois"],
        ["Ouvertes ET fermées même mois", _fmt(result.ouverts_et_fermes_meme_mois), "ouverture ET fermeture dans le même mois"],
        ["Délai moyen",                   _fmt(result.delai_moyen_heures, " h"), "mean(fermeture − ouverture) sur fermés du mois"],
    ]
    kpi_table = Table(
        kpi_data,
        colWidths=[page_width * 0.35, page_width * 0.18, page_width * 0.47],
        repeatRows=1,
    )
    kpi_table.setStyle(_base_table_style())
    story.append(kpi_table)
    df_site = kpi.tickets_by_site(df, mois)
    df_subj = kpi.subjects_opened_month(df, mois)
    story += _interpretation(result, df_site, df_subj, mois, styles)
    story.append(_bar_chart(
        ["Ouverts", "Ouverts/fermés", "Fermés"],
        [result.total_ouverts or 0, result.ouverts_et_fermes_meme_mois or 0, result.total_fermes or 0],
        "Indicateurs du mois",
    ))
    story.append(Spacer(1, 8))

    previous_month, comparison = kpi.compare_month_to_previous(df, mois)
    story += _section_heading(
        f"2. Comparaison : {mois} vs {previous_month or 'N/A'}",
        styles,
    )
    story.append(_comparison_table(comparison, styles))
    if previous_month:
        chart_rows = comparison.iloc[:3]
        story.append(Spacer(1, 8))
        story.append(_comparison_chart(
            chart_rows["Indicateur"].tolist(),
            [float(value or 0) for value in chart_rows["Valeur précédente"]],
            [float(value or 0) for value in chart_rows["Valeur sélectionnée"]],
            "Évolution des volumes",
        ))

    # ── 3. Satisfaction ────────────────────────────────────────────────
    story += _section_heading("3. Satisfaction (enquête ASKit)", styles)

    if sat.fallback_global:
        story.append(Paragraph(
            "⚠ Mode fallback : aucune date d'enquête exploitable pour ce mois — "
            "données issues de l'ensemble des réponses disponibles.",
            styles["Normal"],
        ))
        story.append(Spacer(1, 6))

    # Résumé global
    sat_summary = [
        ["Indicateur", "Valeur", "Formule"],
        ["Satisfaction globale",      _fmt(sat.satisfaction_globale, " %"),   "(note≥4) / total réponses combinées × 100"],
        ["Taux de participation",     _fmt(sat.taux_participation,   " %"),   "nb répondants / global traitées × 100"],
        ["Nombre de répondants",      str(sat.nombre_reponses),               "lignes enquête avec ≥1 note"],
        ["Global traitées (dénomina.)",_fmt(result.total_fermes),             "tickets fermés dans le mois"],
        ["Rubrique la moins satis.",  sat.rubrique_moins_satisfaisante or "N/A", "rubrique au taux individuel minimum"],
    ]
    sat_table = Table(
        sat_summary,
        colWidths=[page_width * 0.32, page_width * 0.18, page_width * 0.50],
        repeatRows=1,
    )
    sat_table.setStyle(_base_table_style())
    story.append(sat_table)
    story.append(Spacer(1, 8))

    # Détail par rubrique (comptage par niveau)
    story.append(Paragraph("Détail par rubrique (comptage par niveau 1→5) :", styles["Normal"]))
    story.append(Spacer(1, 4))

    def _rubrique_row(label: str, d: "kpi.RubriqueDetail | None") -> list:
        if d is None:
            return [label, "N/A", "N/A", "N/A", "N/A", "N/A", "N/A"]
        return [
            label,
            str(d.tres_insatisfait),
            str(d.plutot_insatisfait),
            str(d.insatisfait),
            str(d.satisfait),
            str(d.tres_satisfait),
            _fmt(d.taux_satisfaction, " %"),
        ]

    rubrique_headers = [
        "Rubrique",
        "Très insat.",
        "Plutôt insat.",
        "Insatisfait",
        "Satisfait",
        "Très sat.",
        "Taux (%)",
    ]
    rubrique_data = [
        rubrique_headers,
        _rubrique_row("Traitement",    sat.detail_traitement),
        _rubrique_row("Communication", sat.detail_communication),
        _rubrique_row("Temps",         sat.detail_temps),
    ]
    rubrique_table = Table(
        rubrique_data,
        colWidths=[
            page_width * 0.26,
            page_width * 0.10,
            page_width * 0.12,
            page_width * 0.10,
            page_width * 0.10,
            page_width * 0.10,
            page_width * 0.10,  # note: rounding, adjust if needed
        ],
        repeatRows=1,
    )
    rubrique_style = _base_table_style()
    # Colorier la colonne Taux selon le niveau
    for row_idx in range(1, 4):
        taux_cell = rubrique_data[row_idx][-1].replace(" %", "")
        try:
            taux_val = float(taux_cell)
            bg = _GREEN_LIGHT if taux_val >= 80 else (_RED_LIGHT if taux_val < 60 else colors.HexColor("#FFEB9C"))
            rubrique_style.add("BACKGROUND", (6, row_idx), (6, row_idx), bg)
        except ValueError:
            pass
    rubrique_table.setStyle(rubrique_style)
    story.append(rubrique_table)

    # ── 3. Par site ────────────────────────────────────────────────────
    story += _section_heading("4. Tickets ouverts par site", styles)
    df_site = kpi.tickets_by_site(df, mois)
    if df_site.empty:
        story.append(Paragraph("Donnée indisponible", styles["Normal"]))
    else:
        story.append(_bar_chart(
            df_site["site"].astype(str).tolist(),
            df_site["nombre_tickets"].astype(float).tolist(),
            "Demandes ouvertes par site",
        ))
        story.append(Spacer(1, 6))
        story.append(_df_to_table(df_site, max_rows=10, col_widths=[page_width * 0.5, page_width * 0.5]))

    # ── 4. Par site × pôle ────────────────────────────────────────────
    story += _section_heading("5. Tickets ouverts par site et pôle", styles)
    df_sp = kpi.tickets_by_site_pole(df, mois)
    if df_sp.empty:
        story.append(Paragraph("Donnée indisponible — fichier employés non chargé ou colonne pôle absente.", styles["Normal"]))
    else:
        cw = page_width / len(df_sp.columns)
        story.append(_df_to_table(df_sp, max_rows=20, col_widths=[cw] * len(df_sp.columns)))

    # ── 5. Types de demandes ───────────────────────────────────────────
    story += _section_heading("6. Types de demandes (sujets ouverts du mois)", styles)
    df_subj = kpi.subjects_opened_month(df, mois)
    if df_subj.empty:
        story.append(Paragraph("Donnée indisponible", styles["Normal"]))
    else:
        subject_chart = df_subj.head(10)
        story.append(_bar_chart(
            subject_chart["categorie"].astype(str).tolist(),
            subject_chart["nombre_tickets"].astype(float).tolist(),
            "Principaux sujets",
        ))
        story.append(Spacer(1, 6))
        story.append(_df_to_table(df_subj, max_rows=15, col_widths=[page_width * 0.65, page_width * 0.35]))

    # ── Pied de page ───────────────────────────────────────────────────
    story.append(Spacer(1, 18))
    story.append(HRFlowable(width="100%", thickness=0.5, color=_GREY_DARK))
    story.append(Paragraph(
        f"Document généré automatiquement par le dashboard RSI Sagemcom. "
        f"Mois : {mois}. Aucune donnée personnelle identifiante n'est incluse.",
        ParagraphStyle("Footer", parent=styles["Normal"], fontSize=7, textColor=colors.grey),
    ))

    doc.build(story)
    return path
