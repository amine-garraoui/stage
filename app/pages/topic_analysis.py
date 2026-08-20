"""Topic Analysis - Page 6."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import streamlit as st
import plotly.express as px
from app.session_state import get_current_role, get_current_full_name, require_auth
from app.components.charts import bar_chart_breakdown
from app.components.sidebar import render_sidebar
from src.database.connection import get_db


def render() -> None:
    require_auth()
    role = get_current_role()
    full_name = get_current_full_name()
    render_sidebar(role, full_name)
    st.title("Analyse par Sujet")

    with get_db() as conn:
        rows = conn.execute(
            "SELECT year, month, by_topic FROM kpi_snapshots WHERE scope='GLOBAL' AND by_topic IS NOT NULL ORDER BY year DESC, month DESC"
        ).fetchall()

    if not rows:
        st.info("Aucune donnee.")
        st.stop()

    periods = [f"{r['year']:04d}-{r['month']:02d}" for r in rows]
    sel = st.selectbox("Periode", periods)
    snap = next((r for r in rows if f"{r['year']:04d}-{r['month']:02d}" == sel), None)

    if snap:
        by_topic = json.loads(snap["by_topic"]) if snap["by_topic"] else {}
        if by_topic:
            col1, col2 = st.columns([2, 1])
            with col1:
                st.plotly_chart(bar_chart_breakdown(by_topic, f"Tickets par Sujet - {sel}", max_items=20), use_container_width=True)
            with col2:
                top8 = sorted(by_topic.items(), key=lambda x: -x[1])[:8]
                pie = px.pie(names=[t[0] for t in top8], values=[t[1] for t in top8], title="Top 8 Sujets", hole=0.3)
                st.plotly_chart(pie, use_container_width=True)
