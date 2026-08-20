"""
RSI Sagemcom KPI Platform — Main entry point.
Run: streamlit run main.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import logging
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s")

from config.settings import get_settings
from src.database.connection import init_db

get_settings()
init_db()

import streamlit as st

st.set_page_config(
    page_title="RSI Sagemcom KPI Platform",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "RSI Sagemcom IT Support KPI Platform v1.0.0"},
)

from app.session_state import is_authenticated, get_current_role

# Import page render functions
from app.pages.login import render as render_login
from app.pages.logout import render as render_logout
from app.pages.change_password import render as render_change_password
from app.pages.executive_overview import render as render_overview
from app.pages.kpi_dashboard import render as render_kpi
from app.pages.trends import render as render_trends
from app.pages.forecasting import render as render_forecasting
from app.pages.site_benchmark import render as render_sites
from app.pages.topic_analysis import render as render_topics
from app.pages.anomaly_center import render as render_anomalies
from app.pages.reports import render as render_reports
from app.pages.administration import render as render_admin

if not is_authenticated():
    # Unauthenticated: show only login
    pages = [st.Page(render_login, title="Connexion", icon="🔐", default=True)]
    nav = st.navigation(pages, position="hidden")
    nav.run()
else:
    role = get_current_role()
    main_pages = [
        st.Page(render_overview,    title="Vue Exécutive",     icon="📊", default=True),
        st.Page(render_kpi,         title="Tableau KPI",       icon="📈"),
        st.Page(render_trends,      title="Tendances",         icon="📉"),
        st.Page(render_forecasting, title="Prévisions",        icon="🔮"),
        st.Page(render_sites,       title="Benchmark Sites",   icon="🏢"),
        st.Page(render_topics,      title="Analyse Sujets",    icon="🏷️"),
        st.Page(render_anomalies,   title="Centre Anomalies",  icon="⚠️"),
        st.Page(render_reports,     title="Rapports",          icon="📄"),
    ]
    account_pages = [
        st.Page(render_change_password, title="Changer Mot de Passe", icon="🔑"),
        st.Page(render_logout,          title="Déconnexion",          icon="🚪"),
    ]
    page_groups: dict = {"Navigation": main_pages, "Compte": account_pages}
    if role == "ADMIN":
        page_groups["Administration"] = [
            st.Page(render_admin, title="Administration", icon="⚙️"),
        ]
    nav = st.navigation(page_groups)
    nav.run()
