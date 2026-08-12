from pathlib import Path

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.formatting.rule import ColorScaleRule

from core import kpi


def export_month_excel(df: pd.DataFrame, mois: str, output_dir: str | Path) -> Path:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    path = output / f"rapport_kpi_{mois}.xlsx"

    summary = pd.DataFrame([kpi.calculate_month_kpi(df, mois).as_dict()]).fillna("Donnee indisponible")
    by_site = kpi.distribution(df, mois, "site")
    by_site_pole = kpi.tickets_by_site_pole(df, mois)
    by_subject = kpi.subjects_opened_month(df, mois)

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="KPI", index=False)
        by_site.to_excel(writer, sheet_name="Par site", index=False)
        by_site_pole.to_excel(writer, sheet_name="Par site pole", index=False)
        by_subject.to_excel(writer, sheet_name="Sujets ouverts", index=False)

    wb = load_workbook(path)
    header_fill = PatternFill("solid", fgColor="1F4E78")
    header_font = Font(color="FFFFFF", bold=True)
    for sheet in wb.worksheets:
        for cell in sheet[1]:
            cell.fill = header_fill
            cell.font = header_font
        for column_cells in sheet.columns:
            max_len = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column_cells)
            sheet.column_dimensions[column_cells[0].column_letter].width = min(max(max_len + 2, 12), 45)
        if sheet.max_row > 1 and sheet.max_column > 1:
            sheet.auto_filter.ref = sheet.dimensions
            sheet.freeze_panes = "A2"
    if "KPI" in wb.sheetnames:
        ws = wb["KPI"]
        ws.conditional_formatting.add("D2:F2", ColorScaleRule(start_type="min", start_color="63BE7B", end_type="max", end_color="F8696B"))
    wb.save(path)
    return path
