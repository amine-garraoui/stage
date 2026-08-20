"""Trends Analysis - Page 3."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import streamlit as st
import plotly.graph_objects as go
from app.session_state import get_current_role, get_current_full_name, require_auth
from app.components.sidebar import render_sidebar
from src.database.connection import get_db
from src.engine.kpi_engine import KpiEngine


def render() -> None:
    require_auth()
    role = get_current_role()
    full_name = get_current_full_name()
    render_sidebar(role, full_name)
    st.title("Analyse des Tendances")

    with get_db() as conn:
        kpi_df = KpiEngine(conn).get_monthly_dataframe()

    if kpi_df.empty:
        st.info("Aucune donnee.")
        st.stop()

    st.subheader("Derniers 12 mois")
    roll = kpi_df.tail(12)
    c1, c2 = st.columns(2)
    with c1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=roll["period"], y=roll["tickets_opened"], mode="lines+markers", name="Ouverts", line=dict(color="#003366")))
        fig.add_trace(go.Scatter(x=roll["period"], y=roll["tickets_closed"], mode="lines+markers", name="Fermes", line=dict(color="#0066CC")))
        fig.update_layout(title="Volume Tickets (12 mois)", template="plotly_white", hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=roll["period"], y=roll["avg_satisfaction"], mode="lines+markers",
                                   name="Satisfaction", line=dict(color="#006633")))
        fig2.update_layout(title="Satisfaction (12 mois)", template="plotly_white",
                            yaxis=dict(range=[0, 5], title="Score /5"))
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Comparaison Annee/Annee")
    if len(kpi_df) >= 13:
        years = sorted(kpi_df["year"].unique(), reverse=True)[:3]
        yoy = go.Figure()
        colors = ["#003366", "#0066CC", "#66AADD"]
        for i, yr in enumerate(years):
            d = kpi_df[kpi_df["year"] == yr].sort_values("month")
            yoy.add_trace(go.Scatter(x=d["month"].astype(str), y=d["tickets_opened"],
                                      mode="lines+markers", name=str(yr), line=dict(color=colors[i % 3])))
        yoy.update_layout(title="Volume par Mois - Comparaison Annuelle", xaxis_title="Mois",
                           yaxis_title="Tickets", template="plotly_white")
        st.plotly_chart(yoy, use_container_width=True)
    else:
        st.info("Minimum 13 mois requis pour la comparaison annuelle.")

    st.subheader("Evolution Mois/Mois")
    if len(kpi_df) >= 2:
        df_mom = kpi_df.copy()
        df_mom["Delta Tickets%"] = df_mom["tickets_opened"].pct_change() * 100
        df_mom["Delta Satisfaction%"] = df_mom["avg_satisfaction"].pct_change() * 100
        display = df_mom.tail(12)[["period", "tickets_opened", "Delta Tickets%", "avg_satisfaction", "Delta Satisfaction%"]].round(2)
        display.columns = ["Periode", "Tickets Ouverts", "Delta Tickets %", "Satisfaction", "Delta Satisfaction %"]
        st.dataframe(display, use_container_width=True, hide_index=True)
