"""Site Benchmark - Page 5."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import streamlit as st
from app.session_state import get_current_role, get_current_full_name, require_auth
from app.components.charts import bar_chart_breakdown
from app.components.sidebar import render_sidebar
from src.database.connection import get_db


def render() -> None:
    require_auth()
    role = get_current_role()
    full_name = get_current_full_name()
    render_sidebar(role, full_name)
    st.title("Benchmark par Site")

    with get_db() as conn:
        rows = conn.execute(
            "SELECT year, month, by_site FROM kpi_snapshots WHERE scope='GLOBAL' AND by_site IS NOT NULL ORDER BY year DESC, month DESC"
        ).fetchall()

    if not rows:
        st.info("Aucune donnee.")
        st.stop()

    periods = [f"{r['year']:04d}-{r['month']:02d}" for r in rows]
    sel = st.selectbox("Periode", periods)
    snap = next((r for r in rows if f"{r['year']:04d}-{r['month']:02d}" == sel), None)

    if snap:
        by_site = json.loads(snap["by_site"]) if snap["by_site"] else {}
        if by_site:
            col1, col2 = st.columns([2, 1])
            with col1:
                st.plotly_chart(bar_chart_breakdown(by_site, f"Tickets par Site - {sel}"), use_container_width=True)
            with col2:
                st.subheader("Top Sites")
                total = sum(by_site.values())
                for site, cnt in sorted(by_site.items(), key=lambda x: -x[1])[:10]:
                    pct = cnt / total * 100 if total else 0
                    st.metric(site, f"{cnt}", f"{pct:.1f}%")
