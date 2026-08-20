"""Anomaly Center - Page 7."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import streamlit as st
from app.session_state import get_current_role, get_current_full_name, require_auth
from app.components.charts import anomaly_pie
from app.components.sidebar import render_sidebar
from src.database.connection import get_db
from src.engine.kpi_engine import KpiEngine
from src.anomaly.anomaly_detector import AnomalyDetector


def render() -> None:
    require_auth()
    role = get_current_role()
    full_name = get_current_full_name()
    render_sidebar(role, full_name)
    st.title("Centre de Detection des Anomalies")

    with get_db() as conn:
        kpi_df = KpiEngine(conn).get_monthly_dataframe()
        if role == "ADMIN":
            if st.button("Relancer la detection", type="primary"):
                with st.spinner("Analyse..."):
                    found = AnomalyDetector(conn).detect_all(kpi_df)
                st.success(f"{len(found)} anomalie(s) detectee(s).")
                st.rerun()
        records = [dict(r) for r in conn.execute(
            "SELECT * FROM anomaly_records ORDER BY year DESC, month DESC, severity"
        ).fetchall()]

    if not records:
        st.success("Aucune anomalie detectee.")
        st.stop()

    sev_counts = {}
    for r in records:
        sev_counts[r["severity"]] = sev_counts.get(r["severity"], 0) + 1

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total", len(records))
    c2.metric("Critique", sev_counts.get("CRITICAL", 0))
    c3.metric("Haute", sev_counts.get("HIGH", 0))
    c4.metric("Moyenne", sev_counts.get("MEDIUM", 0))

    st.plotly_chart(anomaly_pie(sev_counts), use_container_width=False)

    sev_filter = st.multiselect("Severite", ["CRITICAL", "HIGH", "MEDIUM", "LOW"], default=["CRITICAL", "HIGH"])
    type_filter = st.multiselect("Type", list({r["anomaly_type"] for r in records}), default=[])

    filtered = [r for r in records
                if (not sev_filter or r["severity"] in sev_filter)
                and (not type_filter or r["anomaly_type"] in type_filter)]

    ICONS = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}
    for r in filtered:
        period = f"{r['year']:04d}-{r['month']:02d}"
        with st.expander(f"{ICONS.get(r['severity'], '⚪')} [{r['severity']}] {r['anomaly_type']} - {period} - {r['scope']}",
                         expanded=r["severity"] == "CRITICAL"):
            st.write(r["explanation"])
            a, b, c = st.columns(3)
            a.metric("Observe", f"{r['observed_value']:.2f}")
            b.metric("Reference", f"{r['baseline_value']:.2f}")
            c.metric("Ecart", f"{r['deviation_percent']:+.1f}%")
            if r.get("z_score"):
                st.caption(f"Score Z : {r['z_score']:.2f}")
