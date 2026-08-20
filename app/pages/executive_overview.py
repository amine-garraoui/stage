"""Executive Overview - Page 1."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import json
import streamlit as st
from app.session_state import get_current_role, get_current_full_name, require_auth
from app.components.charts import satisfaction_gauge, performance_gauge, bar_chart_breakdown
from app.components.sidebar import render_sidebar
from src.database.connection import get_db
from src.engine.kpi_engine import KpiEngine
import plotly.graph_objects as go


def render() -> None:
    require_auth()
    role = get_current_role()
    full_name = get_current_full_name()
    render_sidebar(role, full_name)

    st.title("Vue Executive - RSI Sagemcom IT Support")

    with get_db() as conn:
        engine = KpiEngine(conn)
        kpi_df = engine.get_monthly_dataframe()
        insight = conn.execute(
            "SELECT * FROM executive_insights ORDER BY year DESC, month DESC LIMIT 1"
        ).fetchone()
        insight = dict(insight) if insight else None
        critical = conn.execute(
            "SELECT COUNT(*) FROM anomaly_records WHERE severity='CRITICAL'"
        ).fetchone()[0]

    if kpi_df.empty:
        st.info("Aucune donnee. Importez un fichier ASKit depuis Administration.")
        st.stop()

    periods = kpi_df["period"].tolist()
    selected = st.selectbox("Periode", periods, index=len(periods)-1)
    sel = kpi_df[kpi_df["period"] == selected].iloc[0]
    prev_rows = kpi_df[kpi_df["period"] < selected]
    prev = prev_rows.iloc[-1] if not prev_rows.empty else None

    def delta(cur, prv, fmt="{:+.0f}"):
        if cur is None or prv is None or prv == 0:
            return None
        return fmt.format(cur - prv)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Tickets Ouverts", int(sel["tickets_opened"] or 0),
              delta=delta(sel["tickets_opened"], prev["tickets_opened"] if prev is not None else None))
    c2.metric("Tickets Fermes", int(sel["tickets_closed"] or 0),
              delta=delta(sel["tickets_closed"], prev["tickets_closed"] if prev is not None else None))
    c3.metric("Delai Moyen (h)", f"{sel['avg_resolution_hours']:.1f}h" if sel.get("avg_resolution_hours") else "N/D",
              delta=delta(sel.get("avg_resolution_hours"),
                          prev.get("avg_resolution_hours") if prev is not None else None, "{:+.1f}h"),
              delta_color="inverse")
    c4.metric("Satisfaction", f"{sel['avg_satisfaction']:.2f}/5" if sel.get("avg_satisfaction") else "N/D",
              delta=delta(sel.get("avg_satisfaction"),
                          prev.get("avg_satisfaction") if prev is not None else None, "{:+.2f}"))
    c5.metric("Indice Perf.", f"{sel['performance_index']:.1f}/100" if sel.get("performance_index") else "N/D")

    if critical > 0:
        st.error(f"{critical} anomalie(s) critique(s) - consultez le Centre Anomalies.")

    g1, g2 = st.columns(2)
    with g1:
        if sel.get("avg_satisfaction"):
            st.plotly_chart(satisfaction_gauge(float(sel["avg_satisfaction"])), use_container_width=True)
    with g2:
        if sel.get("performance_index"):
            st.plotly_chart(performance_gauge(float(sel["performance_index"])), use_container_width=True)

    st.subheader("Evolution du Volume")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=kpi_df["period"], y=kpi_df["tickets_opened"],
                              mode="lines+markers", name="Ouverts", line=dict(color="#003366")))
    fig.add_trace(go.Scatter(x=kpi_df["period"], y=kpi_df["tickets_closed"],
                              mode="lines+markers", name="Fermes", line=dict(color="#0066CC", dash="dash")))
    fig.update_layout(template="plotly_white", xaxis_title="Periode", yaxis_title="Tickets", hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    with get_db() as conn:
        snap = conn.execute(
            "SELECT by_site FROM kpi_snapshots WHERE year=? AND month=? AND scope='GLOBAL'",
            (int(sel["year"]), int(sel["month"]))
        ).fetchone()
        if snap and snap["by_site"]:
            by_site = json.loads(snap["by_site"])
            if by_site:
                st.subheader("Repartition par Site")
                st.plotly_chart(bar_chart_breakdown(by_site, f"Tickets par Site - {selected}"),
                                 use_container_width=True)

    if insight:
        st.subheader("Resume Executif")
        st.info(insight["summary_text"])
        alerts = json.loads(insight["critical_alerts"]) if insight.get("critical_alerts") else []
        recs = json.loads(insight["recommendations"]) if insight.get("recommendations") else []
        if alerts and alerts != ["Aucune alerte critique ce mois-ci."]:
            with st.expander("Alertes"):
                for a in alerts:
                    st.error(f"- {a}")
        if recs:
            with st.expander("Recommandations"):
                for r in recs:
                    st.write(f"> {r}")
