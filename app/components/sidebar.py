"""Shared sidebar navigation component."""
import streamlit as st


def render_sidebar(role: str, full_name: str) -> None:
    with st.sidebar:
        st.markdown(f"**👤 {full_name}**")
        st.markdown(f"*Rôle : {role}*")
        st.divider()
        st.page_link("app/pages/executive_overview.py", label="📊 Vue Exécutive")
        st.page_link("app/pages/kpi_dashboard.py", label="📈 Tableau KPI")
        st.page_link("app/pages/trends.py", label="📉 Tendances")
        st.page_link("app/pages/forecasting.py", label="🔮 Prévisions")
        st.page_link("app/pages/site_benchmark.py", label="🏢 Benchmark Sites")
        st.page_link("app/pages/topic_analysis.py", label="🏷️ Analyse Sujets")
        st.page_link("app/pages/anomaly_center.py", label="⚠️ Centre Anomalies")
        st.page_link("app/pages/reports.py", label="📄 Rapports")
        if role == "ADMIN":
            st.divider()
            st.page_link("app/pages/administration.py", label="⚙️ Administration")
        st.divider()
        st.page_link("app/pages/logout.py", label="🚪 Déconnexion")
