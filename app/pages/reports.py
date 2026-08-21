"""Reports - Page 8."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from datetime import UTC, datetime
import pandas as pd
import streamlit as st
from app.session_state import get_current_role, get_current_full_name, get_current_user_id, require_auth
from app.components.sidebar import render_sidebar
from src.database.connection import get_db
from src.engine.kpi_engine import KpiEngine
from src.forecasting.forecasting_service import ForecastingService
from src.reporting.pdf_generator import PdfReportGenerator
from src.reporting.excel_generator import ExcelReportGenerator


def render() -> None:
    require_auth()
    role = get_current_role()
    full_name = get_current_full_name()
    uid = get_current_user_id()
    render_sidebar(role, full_name)
    st.title("Generation de Rapports")

    with get_db() as conn:
        kpi_df = KpiEngine(conn).get_monthly_dataframe()

    if kpi_df.empty:
        st.info("Aucune donnee.")
        st.stop()

    periods = kpi_df["period"].tolist()
    sel_period = st.selectbox("Periode du rapport", periods, index=len(periods) - 1)
    year, month = (int(p) for p in sel_period.split("-"))

    if role != "ADMIN":
        st.warning("Export reserve aux administrateurs.")
        st.stop()

    col_pdf, col_excel = st.columns(2)

    with col_pdf:
        st.subheader("Rapport PDF Executif")
        st.caption("Filigrane CONFIDENTIEL - RSI SAGEMCOM sur chaque page.")
        if st.button("Generer PDF", type="primary", use_container_width=True):
            with st.spinner("Generation..."):
                with get_db() as conn:
                    snap = conn.execute(
                        "SELECT * FROM kpi_snapshots WHERE year=? AND month=? AND scope='GLOBAL'",
                        (year, month)
                    ).fetchone()
                    snap = dict(snap) if snap else {}
                    insight = conn.execute(
                        "SELECT * FROM executive_insights WHERE year=? AND month=?", (year, month)
                    ).fetchone()
                    insight = dict(insight) if insight else {}
                    anomalies = [dict(r) for r in conn.execute(
                        "SELECT * FROM anomaly_records WHERE year=? AND month=?", (year, month)
                    ).fetchall()]
                    data = {
                        "period": sel_period,
                        "performance_index": snap.get("performance_index"),
                        "summary_text": insight.get("summary_text", "N/D"),
                        "key_findings": json.loads(insight.get("key_findings", "[]")),
                        "positive_trends": json.loads(insight.get("positive_trends", "[]")),
                        "tickets_opened": snap.get("tickets_opened", 0),
                        "tickets_closed": snap.get("tickets_closed", 0),
                        "tickets_same_month": snap.get("tickets_opened_and_closed", 0),
                        "tickets_open_eom": snap.get("tickets_open_eom", 0),
                        "avg_resolution_hours": snap.get("avg_resolution_hours"),
                        "avg_satisfaction": snap.get("avg_satisfaction"),
                        "participation_rate": snap.get("participation_rate"),
                        "anomaly_explanations": [a["explanation"] for a in anomalies],
                        "risks": json.loads(insight.get("risks", "[]")),
                        "recommendations": json.loads(insight.get("recommendations", "[]")),
                    }
                    pdf = PdfReportGenerator().generate(data)
                    conn.execute(
                        "INSERT INTO audit_logs (user_id, action, resource, details, success) VALUES (?,?,?,?,1)",
                        (uid, "EXPORT_PDF", f"period:{sel_period}", f"{len(pdf):,} bytes")
                    )
            st.download_button("Telecharger PDF", pdf,
                               f"RSI_KPI_{sel_period}.pdf", "application/pdf",
                               use_container_width=True)
            st.success("PDF genere.")

    with col_excel:
        st.subheader("Rapport Excel Detaille")
        st.caption("Historique complet, anomalies, previsions.")
        if st.button("Generer Excel", type="primary", use_container_width=True):
            with st.spinner("Generation..."):
                with get_db() as conn:
                    insight = conn.execute(
                        "SELECT * FROM executive_insights WHERE year=? AND month=?", (year, month)
                    ).fetchone()
                    insight_dict = {"summary_text": dict(insight)["summary_text"]} if insight else {}
                    anom_rows = [dict(r) for r in conn.execute("SELECT * FROM anomaly_records").fetchall()]
                    anom_df = pd.DataFrame(anom_rows) if anom_rows else None
                    svc = ForecastingService(conn)
                    fdf = svc.get_forecast_df("tickets_opened")
                    excel = ExcelReportGenerator().generate(
                        kpi_df=kpi_df, insight_data=insight_dict,
                        anomaly_df=anom_df, forecast_df=fdf if not fdf.empty else None,
                    )
                    conn.execute(
                        "INSERT INTO audit_logs (user_id, action, resource, details, success) VALUES (?,?,?,?,1)",
                        (uid, "EXPORT_EXCEL", f"period:{sel_period}", f"{len(excel):,} bytes")
                    )
            st.download_button("Telecharger Excel", excel,
                               f"RSI_KPI_{sel_period}.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               use_container_width=True)
            st.success("Excel genere.")
