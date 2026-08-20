"""KPI Dashboard - Page 2."""
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
    st.title("Tableau de Bord KPI")

    with get_db() as conn:
        kpi_df = KpiEngine(conn).get_monthly_dataframe()

    if kpi_df.empty:
        st.info("Aucune donnee disponible.")
        st.stop()

    n = st.selectbox("Derniers N mois", [3, 6, 12, 24, len(kpi_df)], index=2, key="n_months")
    df = kpi_df.tail(n)

    tab1, tab2, tab3, tab4 = st.tabs(["Volume", "Resolution", "Satisfaction", "Performance"])

    with tab1:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=df["period"], y=df["tickets_opened"], name="Ouverts", marker_color="#003366"))
        fig.add_trace(go.Bar(x=df["period"], y=df["tickets_closed"], name="Fermes", marker_color="#0066CC"))
        fig.add_trace(go.Scatter(x=df["period"], y=df["tickets_open_eom"], mode="lines+markers",
                                  name="En cours EOM", line=dict(color="#FF8800", dash="dot")))
        fig.update_layout(barmode="group", template="plotly_white", hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)
        display = df[["period", "tickets_opened", "tickets_closed", "tickets_opened_and_closed", "tickets_open_eom"]].copy()
        display.columns = ["Periode", "Ouverts", "Fermes", "Ouverts+Fermes", "EOM"]
        st.dataframe(display, use_container_width=True, hide_index=True)

    with tab2:
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=df["period"], y=df["avg_resolution_hours"], mode="lines+markers", name="Moyenne"))
        fig2.add_trace(go.Scatter(x=df["period"], y=df["median_resolution_hours"], mode="lines", name="Mediane", line=dict(dash="dash")))
        fig2.add_trace(go.Scatter(x=df["period"], y=df["p90_resolution_hours"], mode="lines", name="P90", line=dict(dash="dot", color="#CC3300")))
        fig2.add_hline(y=72, line_dash="dash", line_color="green", annotation_text="Objectif 72h")
        fig2.update_layout(template="plotly_white", yaxis_title="Heures", hovermode="x unified")
        st.plotly_chart(fig2, use_container_width=True)

    with tab3:
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=df["period"], y=df["avg_satisfaction"], mode="lines+markers",
                                   name="Satisfaction", line=dict(color="#006633"),
                                   fill="tozeroy", fillcolor="rgba(0,102,51,0.1)"))
        fig3.add_trace(go.Scatter(x=df["period"], y=df["participation_rate"], mode="lines+markers",
                                   name="Participation %", yaxis="y2", line=dict(color="#0066CC", dash="dash")))
        fig3.update_layout(template="plotly_white",
                            yaxis=dict(title="Satisfaction /5", range=[0, 5]),
                            yaxis2=dict(title="Participation %", overlaying="y", side="right", range=[0, 100]))
        st.plotly_chart(fig3, use_container_width=True)

    with tab4:
        fig4 = go.Figure()
        fig4.add_trace(go.Scatter(x=df["period"], y=df["performance_index"], mode="lines+markers+text",
                                   text=df["performance_index"].round(1), textposition="top center",
                                   line=dict(color="#003366", width=3),
                                   fill="tozeroy", fillcolor="rgba(0,51,102,0.1)"))
        fig4.add_hline(y=70, line_dash="dash", line_color="green", annotation_text="Objectif 70")
        fig4.add_hline(y=50, line_dash="dash", line_color="orange", annotation_text="Seuil alerte")
        fig4.update_layout(template="plotly_white", yaxis=dict(range=[0, 100]), yaxis_title="Score /100")
        st.plotly_chart(fig4, use_container_width=True)
