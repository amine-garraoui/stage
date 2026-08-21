"""Forecasting - Page 4."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import streamlit as st
from app.session_state import get_current_role, get_current_full_name, require_auth
from app.components.charts import line_chart_with_forecast
from app.components.sidebar import render_sidebar
from src.database.connection import get_db
from src.engine.kpi_engine import KpiEngine
from src.forecasting.forecasting_service import ForecastingService, METRICS


def render() -> None:
    require_auth()
    role = get_current_role()
    full_name = get_current_full_name()
    render_sidebar(role, full_name)
    st.title("Module de Previsions")
    st.caption("Previsions basees sur l'historique mensuel. Les bandes grises = intervalle de confiance 95%.")

    LABELS = {
        "tickets_opened": "Volume de Tickets",
        "avg_resolution_hours": "Delai Moyen (h)",
        "avg_satisfaction": "Satisfaction Moy."
    }

    with get_db() as conn:
        kpi_df = KpiEngine(conn).get_monthly_dataframe()
        if kpi_df.empty:
            st.info("Aucune donnee.")
            st.stop()
        if role == "ADMIN":
            if st.button("Recalculer les previsions", type="primary"):
                svc = ForecastingService(conn)
                n = svc.run_all(kpi_df)
                st.success(f"{n} points generes.")
                st.rerun()
        for metric in METRICS:
            label = LABELS.get(metric, metric)
            st.subheader(f"{label}")
            svc = ForecastingService(conn)
            fdf = svc.get_forecast_df(metric)
            if fdf.empty:
                st.info(f"Aucune prevision pour '{label}'. Lancez un recalcul.")
                continue
            if metric in kpi_df.columns:
                actual_map = dict(zip(kpi_df["period"], kpi_df[metric]))
                fdf.loc[fdf["is_historical"], "value"] = fdf.loc[fdf["is_historical"], "period"].map(actual_map)
            st.plotly_chart(line_chart_with_forecast(fdf, label, label), use_container_width=True)
            future = fdf[~fdf["is_historical"]][["period", "value", "lower", "upper", "model"]].round(2)
            future.columns = ["Periode", "Predit", "Borne Inf.", "Borne Sup.", "Modele"]
            with st.expander("Donnees"):
                st.dataframe(future, hide_index=True, use_container_width=True)
            st.divider()
