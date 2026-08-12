from pathlib import Path

from fastapi import FastAPI, HTTPException

from core import anomalies, kpi
from core.config import load_config, resolve_path, setup_logging
from core.exceptions import KpiError
from core.service import load_dataset_cached
from reports.excel import export_month_excel
from reports.pdf import export_month_pdf


setup_logging()
config = load_config()
app = FastAPI(title=config.api_title, version="1.0.0")


def _dataset():
    try:
        return load_dataset_cached("config.yaml")
    except KpiError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/months")
def months() -> dict:
    return {"months": kpi.available_months(_dataset())}


@app.get("/kpi/{mois}")
def month_kpi(mois: str) -> dict:
    df = _dataset()
    if mois not in kpi.available_months(df):
        raise HTTPException(status_code=404, detail=f"Month not found: {mois}")
    summary = kpi.monthly_summary(df)
    return {
        "kpi": kpi.calculate_month_kpi(df, mois).as_dict(),
        "comparison": anomalies.compare_months(summary, mois),
        "anomalies": anomalies.detect_anomalies(
            summary,
            mois,
            config.thresholds.anomaly_std_multiplier,
            config.thresholds.anomaly_window_months,
        ),
    }


@app.get("/kpi/{mois}/par-site")
def kpi_by_site(mois: str) -> list[dict]:
    return kpi.distribution(_dataset(), mois, "site").to_dict(orient="records")


@app.get("/kpi/{mois}/sujets")
def kpi_by_subject(mois: str) -> list[dict]:
    return kpi.subjects_opened_month(_dataset(), mois).to_dict(orient="records")


@app.get("/satisfaction/{mois}")
def satisfaction(mois: str) -> dict:
    result = kpi.calculate_month_kpi(_dataset(), mois)
    return {"mois": mois, **result.satisfaction.as_dict()}


@app.get("/export/{mois}")
def export(mois: str) -> dict:
    df = _dataset()
    exports_dir = resolve_path(config.data.exports_dir) or Path("data/exports")
    pdf_path = export_month_pdf(df, mois, exports_dir, config.company_name)
    excel_path = export_month_excel(df, mois, exports_dir)
    return {"mois": mois, "pdf": str(pdf_path), "excel": str(excel_path)}
