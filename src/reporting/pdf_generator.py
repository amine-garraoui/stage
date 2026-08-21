"""PDF Report Generator — reportlab is installed."""

from __future__ import annotations

import io
import json
from datetime import datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

PRIMARY = colors.HexColor("#003366")
ACCENT = colors.HexColor("#0066CC")
LIGHT = colors.HexColor("#F5F5F5")
GREY = colors.HexColor("#CCCCCC")
RED = colors.HexColor("#CC3300")
GREEN = colors.HexColor("#006633")
WATERMARK = colors.Color(0.85, 0.85, 0.85, alpha=0.3)


class WatermarkCanvas(Canvas):
    def showPage(self):
        self._stamp()
        super().showPage()

    def save(self):
        self._stamp()
        super().save()

    def _stamp(self):
        self.saveState()
        self.setFont("Helvetica-Bold", 48)
        self.setFillColor(WATERMARK)
        w, h = A4
        self.translate(w / 2, h / 2)
        self.rotate(45)
        self.drawCentredString(0, 0, "CONFIDENTIEL - RSI SAGEMCOM")
        self.restoreState()
        # Footer
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(GREY)
        self.drawString(2*cm, 1.2*cm, "RSI Sagemcom IT Support — Rapport confidentiel")
        self.drawRightString(w - 2*cm, 1.2*cm, f"Page {self._pageNumber}")
        self.restoreState()


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("T", parent=base["Title"], textColor=PRIMARY, fontSize=20, fontName="Helvetica-Bold"),
        "heading": ParagraphStyle("H", parent=base["Heading2"], textColor=PRIMARY, fontSize=12, fontName="Helvetica-Bold"),
        "sub": ParagraphStyle("S", parent=base["Normal"], textColor=ACCENT, fontSize=11, fontName="Helvetica-Bold"),
        "body": ParagraphStyle("B", parent=base["Normal"], fontSize=10, fontName="Helvetica"),
        "bullet": ParagraphStyle("BL", parent=base["Normal"], fontSize=9, leftIndent=12, fontName="Helvetica"),
        "alert": ParagraphStyle("AL", parent=base["Normal"], fontSize=9, textColor=RED, fontName="Helvetica-Bold", leftIndent=12),
        "ok": ParagraphStyle("OK", parent=base["Normal"], fontSize=9, textColor=GREEN, fontName="Helvetica", leftIndent=12),
        "small": ParagraphStyle("SM", parent=base["Normal"], fontSize=8, textColor=colors.grey),
    }


class PdfReportGenerator:
    def generate(self, data: dict) -> bytes:
        buf = io.BytesIO()
        s = _styles()
        doc = SimpleDocTemplate(buf, pagesize=A4,
                                leftMargin=2*cm, rightMargin=2*cm,
                                topMargin=2.5*cm, bottomMargin=2.5*cm,
                                title=f"Rapport KPI RSI — {data.get('period','')}",
                                author="RSI Sagemcom IT Support")
        story = []

        # Cover
        story += [Spacer(1, 3*cm),
                  Paragraph("RSI SAGEMCOM", s["title"]),
                  Paragraph("IT Support — Tableau de Bord KPI", s["sub"]),
                  HRFlowable(width="100%", thickness=2, color=PRIMARY, spaceAfter=10),
                  Spacer(1, 1*cm),
                  Paragraph(f"Période : {data.get('period','')}", s["heading"]),
                  Spacer(1, 0.5*cm)]
        if data.get("performance_index"):
            story.append(Paragraph(f"<b>Indice de Performance RSI :</b> {data['performance_index']:.1f}/100", s["body"]))
        story += [Spacer(1, 2*cm),
                  Paragraph(f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}", s["small"]),
                  Paragraph("Document confidentiel — Usage interne uniquement",
                             ParagraphStyle("conf", parent=s["small"], textColor=RED, fontName="Helvetica-Bold")),
                  PageBreak()]

        # Summary
        story += [Paragraph("Résumé Exécutif", s["heading"]), Spacer(1, 0.3*cm),
                  Paragraph(data.get("summary_text", ""), s["body"]), Spacer(1, 0.5*cm)]
        for item in data.get("key_findings", []):
            story.append(Paragraph(f"• {item}", s["bullet"]))
        story.append(Spacer(1, 0.4*cm))
        for item in data.get("positive_trends", []):
            story.append(Paragraph(f"✓ {item}", s["ok"]))
        story.append(PageBreak())

        # KPIs
        story += [Paragraph("Indicateurs de Performance", s["heading"]), Spacer(1, 0.3*cm)]
        rows = [["Indicateur", "Valeur"],
                ["Tickets ouverts", str(data.get("tickets_opened", 0))],
                ["Tickets fermés", str(data.get("tickets_closed", 0))],
                ["Ouverts+Fermés même mois", str(data.get("tickets_same_month", 0))],
                ["Tickets en cours (EOM)", str(data.get("tickets_open_eom", 0))],
                ["Délai moyen résolution",
                 f"{data['avg_resolution_hours']:.1f}h" if data.get("avg_resolution_hours") else "N/D"],
                ["Satisfaction moyenne",
                 f"{data['avg_satisfaction']:.2f}/5" if data.get("avg_satisfaction") else "N/D"],
                ["Taux de participation",
                 f"{data['participation_rate']:.1f}%" if data.get("participation_rate") else "N/D"]]
        tbl = Table(rows, colWidths=[9*cm, 6*cm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), PRIMARY), ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("FONTSIZE", (0,0), (-1,-1), 9),
            ("ALIGN", (1,1), (-1,-1), "CENTER"),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, LIGHT]),
            ("GRID", (0,0), (-1,-1), 0.5, GREY),
            ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ]))
        story.append(tbl)
        story.append(PageBreak())

        # Anomalies
        story += [Paragraph("Anomalies Détectées", s["heading"]), Spacer(1, 0.3*cm)]
        for exp in (data.get("anomaly_explanations") or ["Aucune anomalie significative."]):
            story.append(Paragraph(f"⚠ {exp}", s["alert"]))
            story.append(Spacer(1, 0.2*cm))
        story.append(PageBreak())

        # Recommendations
        story += [Paragraph("Recommandations", s["heading"]), Spacer(1, 0.3*cm)]
        for r in (data.get("risks") or []):
            story.append(Paragraph(f"▸ {r}", s["bullet"]))
        story.append(Spacer(1, 0.3*cm))
        for i, rec in enumerate(data.get("recommendations") or [], 1):
            story.append(Paragraph(f"{i}. {rec}", s["bullet"]))

        doc.build(story, canvasmaker=lambda *a, **kw: WatermarkCanvas(*a, **kw))
        return buf.getvalue()
