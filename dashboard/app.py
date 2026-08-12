from pathlib import Path
import base64

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core import anomalies, insights, kpi
from core.config import load_config, resolve_path, setup_logging
from core.exceptions import SchemaError
from core.ingestion import load_tabular
from core.transformation import (
    build_dataset,
    detect_source_type,
    validate_employees_source,
    validate_satisfaction_source,
    validate_tickets_source,
)
from reports.excel import export_month_excel
from reports.pdf import export_month_pdf


setup_logging()

COLORS = {
    "blue": "#5eeac0",
    "purple": "#7c9cff",
    "pink": "#38bdf8",
    "yellow": "#e0b563",
    "green": "#3fb99a",
    "orange": "#ff8f66",
    "red": "#ef4444",
    "ink": "#eef7f4",
    "muted": "#7fa39c",
    "line": "#1f4444",
}
PALETTE = ["#5eeac0", "#3fb99a", "#7c9cff", "#ff8f66", "#e0b563", "#4a7d78"]
UPLOAD_FLOW_VERSION = "satisfaction_audit_logo_v3"
LOGO_PATH = Path("assets/sagemcom_logo.png")


def image_data_uri(path: Path) -> str:
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def inject_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        #MainMenu,
        footer,
        header,
        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        [data-testid="stStatusWidget"],
        [data-testid="StyledFullScreenButton"] {
            display: none !important;
        }
        html,
        body,
        [class*="css"],
        .stApp,
        .stMarkdown,
        .stText,
        label,
        p,
        span,
        div {
            font-family: "Inter", "Segoe UI", Roboto, Arial, sans-serif;
            letter-spacing: 0;
        }
        h1 {
            color: #0f172a !important;
            font-size: 24px !important;
            font-weight: 800 !important;
            line-height: 1.25 !important;
            margin: 0 0 12px 0 !important;
        }
        h2,
        h3 {
            color: #0284c7 !important;
            font-size: 18px !important;
            font-weight: 700 !important;
            line-height: 1.3 !important;
        }
        .stApp {
            background: #eef3f8;
            color: #334155;
        }
        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 2rem;
            max-width: 1540px;
        }
        [data-testid="stSidebar"],
        [data-testid="collapsedControl"] {
            display: none;
        }
        .control-panel {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 18px;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
            height: 100%;
        }
        .control-title {
            color: #0f172a;
            font-size: 20px;
            font-weight: 800;
            margin-bottom: 2px;
        }
        .control-subtitle {
            color: #64748b;
            font-size: 14px;
            font-weight: 400;
            margin-bottom: 14px;
        }
        .side-menu {
            margin: 12px 0 16px 0;
            display: grid;
            gap: 7px;
        }
        .side-menu-item {
            display: flex;
            align-items: center;
            gap: 9px;
            color: #6b7280;
            font-size: 13px;
            font-weight: 760;
            padding: 10px 11px;
            border-radius: 11px;
        }
        .side-menu-item.active {
            color: #ffffff;
            background: linear-gradient(90deg, #8b5cf6, #a855f7);
            box-shadow: 0 12px 24px rgba(139, 92, 246, .28);
        }
        .side-menu-icon {
            width: 18px;
            text-align: center;
            font-size: 14px;
        }
        .app-shell {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 18px;
            box-shadow: 0 14px 42px rgba(15, 23, 42, 0.08);
        }
        .top-nav {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            padding: 6px 6px 18px 6px;
            border-bottom: 1px solid #e2e8f0;
            margin-bottom: 18px;
        }
        .brand {
            display: flex;
            align-items: center;
            gap: 9px;
            color: #0f172a;
            font-size: 20px;
            font-weight: 800;
        }
        .brand-mark {
            width: 40px;
            height: 40px;
            border-radius: 8px;
            display: grid;
            place-items: center;
            color: #ffffff;
            background: #0284c7;
            font-size: 20px;
        }
        .nav-links {
            display: flex;
            gap: 10px;
            align-items: center;
            color: #7b8194;
            font-size: 13px;
            font-weight: 700;
        }
        .nav-link {
            padding: 13px 20px;
            border-radius: 11px;
        }
        .nav-link.active {
            color: #6d4aff;
            background: #f0edff;
            box-shadow: 0 10px 22px rgba(109, 74, 255, .13);
        }
        .nav-tools {
            color: #334155;
            font-size: 14px;
            font-weight: 600;
            display: flex;
            gap: 12px;
        }
        .nav-button-strip {
            margin: 2px 0 18px 0;
            padding: 8px;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            background: #f8fafc;
        }
        button[kind="primary"] {
            background: #0284c7 !important;
            color: #ffffff !important;
            border: 1px solid #0284c7 !important;
            box-shadow: 0 8px 18px rgba(2, 132, 199, .18) !important;
        }
        button[kind="secondary"] {
            background: #ffffff !important;
            color: #334155 !important;
            border: 1px solid #e2e8f0 !important;
        }
        button[kind="secondary"]:hover,
        button[kind="primary"]:hover {
            color: #0284c7 !important;
            border-color: #38bdf8 !important;
        }
        .section-title {
            color: #0284c7;
            font-size: 18px;
            font-weight: 700;
            margin: 0 0 10px 0;
        }
        .page-header {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 16px;
            margin: 0 0 16px 0;
        }
        .page-subtitle {
            color: #334155;
            font-size: 14px;
            font-weight: 400;
        }
        .month-pill {
            color: #0f172a;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 9px 12px;
            font-size: 14px;
            font-weight: 700;
            white-space: nowrap;
        }
        .kpi-card {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            min-height: 108px;
            padding: 18px 16px 15px 16px;
            box-shadow: 0 8px 22px rgba(15, 23, 42, 0.06);
        }
        .kpi-head {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 10px;
        }
        .kpi-value {
            color: #0f172a;
            font-size: 30px;
            font-weight: 800;
            line-height: 1.1;
        }
        .kpi-label {
            color: #334155;
            margin-top: 8px;
            font-size: 14px;
            font-weight: 500;
        }
        .kpi-icon {
            width: 38px;
            height: 38px;
            border-radius: 8px;
            display: grid;
            place-items: center;
            color: #ffffff;
            font-weight: 900;
            font-size: 15px;
        }
        .chart-card {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 17px;
            min-height: 100%;
            box-shadow: 0 8px 22px rgba(15, 23, 42, 0.06);
        }
        .mini-note {
            color: #64748b;
            font-size: 14px;
            font-weight: 400;
        }
        .source-ok {
            background: #ecfdf5;
            color: #047857;
            border: 1px solid #a7f3d0;
            border-radius: 8px;
            padding: 9px 11px;
            font-weight: 700;
            font-size: 14px;
            margin-bottom: 12px;
        }
        .source-warn {
            background: #fffbeb;
            color: #92400e;
            border: 1px solid #fde68a;
            border-radius: 8px;
            padding: 9px 11px;
            font-weight: 700;
            font-size: 14px;
            margin-bottom: 12px;
        }
        .alert-red {
            background: #fff1f2;
            color: #9f1239;
            border: 1px solid #fecdd3;
            border-left: 5px solid #ef4444;
            border-radius: 8px;
            padding: 10px 12px;
            margin-bottom: 10px;
            font-weight: 700;
        }
        .alert-orange {
            background: #fffbeb;
            color: #92400e;
            border: 1px solid #fde68a;
            border-left: 5px solid #f59e0b;
            border-radius: 8px;
            padding: 10px 12px;
            margin-bottom: 10px;
            font-weight: 700;
        }
        div[data-testid="stMetric"] {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 14px 12px;
            box-shadow: 0 8px 22px rgba(15, 23, 42, 0.05);
        }
        div[data-testid="stMetricLabel"] {
            color: #334155;
            font-size: 14px;
            font-weight: 500;
        }
        div[data-testid="stMetricValue"] {
            color: #0f172a;
            font-size: 30px;
            font-weight: 800;
        }
        .stButton > button {
            border-radius: 8px;
            border: 1px solid #cbd5e1;
            background: #ffffff;
            color: #0f172a;
            font-weight: 700;
            min-height: 40px;
        }
        .stButton > button:hover {
            color: #0284c7;
            border-color: #0284c7;
        }
        .sidebar-stat {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 12px 13px;
            margin-bottom: 10px;
            box-shadow: 0 6px 16px rgba(15, 23, 42, .05);
        }
        .sidebar-stat-label {
            color: #334155;
            font-size: 14px;
            font-weight: 500;
            margin-bottom: 3px;
        }
        .sidebar-stat-value {
            color: #0f172a;
            font-size: 24px;
            font-weight: 800;
            line-height: 1.15;
        }
        .stApp {
            background: #0d1a1a;
            color: #eef7f4;
        }
        @keyframes fadeUp {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        @keyframes softPulse {
            0%, 100% { box-shadow: 0 0 0 rgba(94, 234, 192, 0); }
            50% { box-shadow: 0 0 24px rgba(94, 234, 192, .16); }
        }
        @keyframes progressGlow {
            0% { background-position: 0% 50%; }
            100% { background-position: 100% 50%; }
        }
        .block-container {
            padding: 14px 18px 24px 18px;
            max-width: 100%;
        }
        .app-shell {
            background: #0d1a1a;
            border: 0;
            border-radius: 0;
            padding: 0;
            box-shadow: none;
            min-height: 100vh;
        }
        .control-panel {
            background: #12292a;
            border: 1px solid #1f4444;
            border-radius: 0;
            padding: 22px 18px;
            box-shadow: none;
            min-height: 100vh;
            position: sticky;
            top: 0;
        }
        .dashboard-surface {
            padding: 24px 32px 48px 8px;
        }
        .sidebar-brand {
            border-bottom: 1px solid #1f4444;
            padding-bottom: 18px;
            margin-bottom: 18px;
            animation: fadeUp .35s ease-out both;
        }
        .logo-card {
            width: 152px;
            background: #ffffff;
            border-radius: 12px;
            padding: 12px 14px;
            margin-bottom: 16px;
            border: 1px solid rgba(94, 234, 192, .22);
        }
        .logo-card img {
            display: block;
            width: 100%;
            height: auto;
        }
        .sidebar-kicker {
            color: #5eeac0;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: .12em;
            text-transform: uppercase;
            margin-bottom: 8px;
        }
        .sidebar-title {
            color: #eef7f4;
            font-size: 22px;
            font-weight: 800;
            line-height: 1.15;
        }
        .sidebar-subtitle {
            color: #7fa39c;
            font-size: 13px;
            margin-top: 6px;
        }
        .nav-button-strip {
            background: transparent;
            border: 0;
            border-radius: 0;
            padding: 0;
            margin: 0 0 20px 0;
        }
        .nav-button-strip + div {
            gap: 0 !important;
        }
        button[kind="primary"] {
            background: #5eeac0 !important;
            color: #0d1a1a !important;
            border: 1px solid #5eeac0 !important;
            box-shadow: 0 0 18px rgba(94, 234, 192, .18) !important;
            animation: softPulse 2.4s ease-in-out infinite;
        }
        button[kind="secondary"] {
            background: #0f2222 !important;
            color: #7fa39c !important;
            border: 1px solid #1f4444 !important;
        }
        button[kind="primary"],
        button[kind="secondary"],
        .stButton > button {
            border-radius: 8px !important;
            min-height: 42px;
            font-size: 13px;
            font-weight: 750;
        }
        button[kind="secondary"]:hover,
        button[kind="primary"]:hover,
        .stButton > button:hover {
            color: #eef7f4 !important;
            border-color: #5eeac0 !important;
        }
        .top-nav {
            display: none;
        }
        .page-header {
            position: relative;
            overflow: hidden;
            background: linear-gradient(135deg, rgba(18, 41, 42, .98), rgba(15, 34, 34, .96));
            border: 1px solid #1f4444;
            border-radius: 10px;
            padding: 22px 24px;
            margin: 0 0 18px 0;
            animation: fadeUp .35s ease-out both;
        }
        h1 {
            color: #eef7f4 !important;
            font-size: 30px !important;
            font-weight: 800 !important;
            margin-bottom: 6px !important;
        }
        .page-subtitle {
            color: #7fa39c;
            font-size: 13px;
            letter-spacing: .03em;
        }
        .month-pill {
            color: #5eeac0;
            background: #0f2222;
            border: 1px solid #1f4444;
            border-radius: 8px;
            font-size: 13px;
        }
        .control-title,
        .section-title {
            color: #5eeac0;
            font-size: 12px;
            font-weight: 800;
            letter-spacing: .08em;
            text-transform: uppercase;
        }
        .control-subtitle,
        .mini-note {
            color: #7fa39c;
            font-size: 12px;
        }
        .upload-hero {
            background: #12292a;
            border: 1px dashed #5eeac0;
            border-radius: 10px;
            padding: 18px;
            margin-bottom: 18px;
            box-shadow: 0 0 24px rgba(94, 234, 192, .06) inset;
            animation: fadeUp .32s ease-out both;
        }
        .upload-hero-title {
            color: #eef7f4;
            font-size: 17px;
            font-weight: 800;
            margin-bottom: 6px;
        }
        .upload-hero-text {
            color: #7fa39c;
            font-size: 13px;
            line-height: 1.5;
        }
        .chart-card,
        .kpi-card,
        div[data-testid="stMetric"],
        .sidebar-stat {
            background: #12292a;
            border: 1px solid #1f4444;
            border-radius: 10px;
            box-shadow: none;
            animation: fadeUp .28s ease-out both;
        }
        .generation-strip {
            height: 4px;
            border-radius: 999px;
            background: linear-gradient(90deg, #5eeac0, #7c9cff, #ff8f66, #5eeac0);
            background-size: 240% 100%;
            animation: progressGlow 1.2s linear infinite;
            margin: 8px 0 12px;
        }
        .kpi-card {
            min-height: 112px;
            padding: 16px 18px;
        }
        .kpi-value,
        div[data-testid="stMetricValue"],
        .sidebar-stat-value {
            color: #eef7f4;
            font-family: "Inter", "Segoe UI", Roboto, Arial, sans-serif;
            font-size: 28px;
            font-weight: 800;
        }
        .kpi-label,
        div[data-testid="stMetricLabel"],
        .sidebar-stat-label {
            color: #7fa39c;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: .06em;
            text-transform: uppercase;
        }
        .source-ok {
            background: rgba(94, 234, 192, .08);
            color: #5eeac0;
            border: 1px solid rgba(94, 234, 192, .32);
        }
        .source-warn,
        .alert-orange {
            background: rgba(255, 143, 102, .08);
            color: #ff8f66;
            border: 1px solid rgba(255, 143, 102, .32);
            border-left: 4px solid #ff8f66;
        }
        .alert-red {
            background: rgba(239, 68, 68, .08);
            color: #fecaca;
            border: 1px solid rgba(239, 68, 68, .34);
            border-left: 4px solid #ef4444;
        }
        div[data-testid="stFileUploader"] {
            background: #0f2222;
            border: 1px dashed #1f4444;
            border-radius: 10px;
            padding: 10px;
        }
        div[data-testid="stFileUploader"] section {
            background: transparent;
            border: 0;
        }
        label,
        .stMarkdown,
        p,
        span,
        div {
            color: inherit;
        }
        .stSelectbox label,
        .stMultiSelect label,
        .stDateInput label,
        .stRadio label,
        .stTextInput label {
            color: #7fa39c !important;
            font-size: 12px !important;
            font-weight: 700 !important;
        }
        .stDataFrame {
            border: 1px solid #1f4444;
            border-radius: 10px;
            overflow: hidden;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def fmt(value, suffix: str = "") -> str:
    if value is None or pd.isna(value):
        return "Donnee indisponible"
    if isinstance(value, float):
        return f"{value:.2f}{suffix}"
    return f"{value}{suffix}"


def compact(value) -> str:
    if value is None or pd.isna(value):
        return "Donnee indisponible"
    if isinstance(value, float):
        return f"{value:.1f}"
    return str(value)


def load_sidebar_dataset() -> tuple[pd.DataFrame | None, str | None]:
    chart_card_title("Import ASKit")
    st.markdown(
        """
        <div class="upload-hero">
            <div class="upload-hero-title">Zone drag and drop</div>
            <div class="upload-hero-text">
                Deposez les fichiers ASKit ensemble. L'application detecte automatiquement:
                demandes, enquete satisfaction et referentiel employes.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    def detect_type_from_name(filename: str) -> str | None:
        name = filename.lower()
        if any(token in name for token in ["employ", "employe", "employes", "employés", "employee"]):
            return "employes"
        if any(token in name for token in ["enquete", "enquête", "satisfaction", "sst krm"]):
            return "satisfaction"
        if any(token in name for token in ["report request", "request enregistre", "request enregistré", "demand"]):
            return "demandes"
        return None

    st.markdown(
        """
        **Fichier obligatoire**
        Extrait des demandes ASKit avec au minimum:
        `N° ticket`, `Enregistré le`, `Date de résolution`, `Sujet`, `Meta Statut`, `Bénéficiaire : Localisation`.
        """
    )
    uploaded_files = st.file_uploader(
        "Deposer les fichiers ASKit",
        type=["csv", "gz", "xlsx", "xls"],
        accept_multiple_files=True,
        key="askit_multi_upload",
    )

    with st.expander("Chemins locaux"):
        tickets_path = st.text_input("Chemin tickets", value="", key="tickets_sidebar_path")
        satisfaction_path = st.text_input("Chemin satisfaction", value="", key="satisfaction_sidebar_path")
        employees_path = st.text_input("Chemin employes", value="", key="employees_sidebar_path")

    has_manual = bool(uploaded_files) or tickets_path.strip()
    generate_clicked = st.button("Generer le dashboard", type="primary", use_container_width=True)
    input_signature = (
        UPLOAD_FLOW_VERSION,
        tuple(file.name for file in uploaded_files) if uploaded_files else (),
        tickets_path.strip(),
        satisfaction_path.strip(),
        employees_path.strip(),
    )

    if not has_manual:
        validation_card(
            "Fichier 1 - Extrait des demandes",
            "Date de creation, Date de cloture, Site",
            None,
            "date creation, date cloture, site",
        )
        validation_card(
            "Fichier 2 - Enquete satisfaction",
            "Notes par criteres, Commentaire",
            None,
            "notes de satisfaction",
        )
        validation_card(
            "Fichier 3 - Extrait employes",
            "Matricule, Nom et prenom",
            None,
            "matricule, nom et prenom",
        )
        st.info("Dashboard vide: importez au minimum le fichier demandes ASKit.")
        st.session_state.pop("dashboard_dataset", None)
        st.session_state.pop("dashboard_source_label", None)
        st.session_state.pop("dashboard_input_signature", None)
        return None, None

    previous_signature = st.session_state.get("dashboard_input_signature")
    if previous_signature != input_signature and not generate_clicked:
        st.session_state.pop("dashboard_dataset", None)
        st.session_state.pop("dashboard_source_label", None)
        st.session_state.pop("dashboard_input_signature", None)
        st.info("Nouveau fichier detecte. Cliquez sur Generer le dashboard pour recalculer les KPI.")
        return None, None

    if not generate_clicked and "dashboard_dataset" not in st.session_state:
        st.info("Fichier detecte. Cliquez sur Generer le dashboard pour lancer l'ETL et les KPI.")
        return None, None

    if not generate_clicked and "dashboard_dataset" in st.session_state:
        return st.session_state["dashboard_dataset"], st.session_state["dashboard_source_label"]

    tickets_raw = None
    satisfaction_raw = pd.DataFrame()
    employees_raw = pd.DataFrame()
    source_label = None

    for uploaded_file in uploaded_files or []:
        raw = load_tabular(uploaded_file, required=False)
        detected = detect_source_type(raw)["detected"] or detect_type_from_name(uploaded_file.name)
        if detected == "demandes" and tickets_raw is None:
            tickets_raw = raw
            source_label = f"Import: {uploaded_file.name}"
        elif detected == "satisfaction" and satisfaction_raw.empty:
            satisfaction_raw = raw
        elif detected == "employes" and employees_raw.empty:
            employees_raw = raw
        elif detected:
            st.warning(f"Fichier ignore car type deja fourni ({detected}): {uploaded_file.name}")
        else:
            st.error(
                f"Fichier non reconnu: {uploaded_file.name}. "
                "Renommez-le avec demandes, enquete/satisfaction ou employes si les colonnes ne permettent pas la detection."
            )

    if tickets_path.strip():
        path = Path(tickets_path.strip().strip('"').strip("'"))
        tickets_raw = load_tabular(path)
        source_label = f"Chemin: {path.name}"

    if satisfaction_path.strip():
        satisfaction_raw = load_tabular(Path(satisfaction_path.strip().strip('"').strip("'")), required=False)

    if employees_path.strip():
        employees_raw = load_tabular(Path(employees_path.strip().strip('"').strip("'")), required=False)

    if tickets_raw is None:
        st.error("Aucun fichier demandes ASKit detecte. Deposez le fichier 'Report request enregistres' dans la zone.")
        st.session_state.pop("dashboard_dataset", None)
        st.session_state.pop("dashboard_source_label", None)
        st.session_state.pop("dashboard_input_signature", None)
        return None, None

    tickets_validation = validate_tickets_source(tickets_raw)
    satisfaction_validation = validate_satisfaction_source(satisfaction_raw) if not satisfaction_raw.empty else None
    employees_validation = validate_employees_source(employees_raw) if not employees_raw.empty else None
    tickets_type_ok = source_type_card("Fichier demandes detecte", "demandes", tickets_raw)
    validation_card(
        "Fichier 1 - Extrait des demandes",
        "Date de creation, Date de cloture, Site",
        tickets_validation,
        "date creation, date cloture, site",
    )
    validation_card(
        "Fichier 2 - Enquete satisfaction",
        "Notes par criteres, Commentaire",
        satisfaction_validation,
        "notes de satisfaction",
    )
    validation_card(
        "Fichier 3 - Extrait employes",
        "Matricule, Nom et prenom",
        employees_validation,
        "matricule, nom et prenom",
    )
    if satisfaction_validation is not None and not satisfaction_validation["ok"]:
        st.warning("Le fichier enquete est ignore: colonnes satisfaction non detectees.")
        satisfaction_raw = pd.DataFrame()
    if employees_validation is not None and not employees_validation["ok"]:
        st.warning("Le fichier employes est ignore: Matricule/Login et Nom non detectes.")
        employees_raw = pd.DataFrame()
    if not tickets_validation["ok"]:
        st.session_state.pop("dashboard_dataset", None)
        st.session_state.pop("dashboard_source_label", None)
        st.session_state.pop("dashboard_input_signature", None)
        return None, None
    if not tickets_type_ok:
        st.session_state.pop("dashboard_dataset", None)
        st.session_state.pop("dashboard_source_label", None)
        st.session_state.pop("dashboard_input_signature", None)
        return None, None

    st.markdown('<div class="generation-strip"></div>', unsafe_allow_html=True)
    with st.spinner("Generation du dashboard en cours..."):
        dataset = build_dataset(tickets_raw, satisfaction_raw, employees_raw)
    responses = dataset.attrs.get("satisfaction_responses")
    if responses is not None and not responses.empty:
        st.success(f"Enquete satisfaction chargee: {len(responses)} reponses.")
    else:
        st.warning("Aucune reponse satisfaction chargee.")
    st.success(f"Source chargee: {source_label}")
    final_label = f"{source_label} + fichiers optionnels importes"
    st.session_state["dashboard_dataset"] = dataset
    st.session_state["dashboard_source_label"] = final_label
    st.session_state["dashboard_input_signature"] = input_signature
    return dataset, final_label


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    chart_card_title("Periode d'analyse")
    source_attrs = df.attrs.copy()
    min_date = df["date_ouverture"].min().date()
    max_date = df["date_ouverture"].max().date()
    selected_dates = st.date_input("Periode", value=(min_date, max_date), min_value=min_date, max_value=max_date)

    filtered = df.copy()
    filtered.attrs = source_attrs.copy()
    if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
        start, end = pd.to_datetime(selected_dates[0]), pd.to_datetime(selected_dates[1])
        filtered = filtered[
            (filtered["date_ouverture"] >= start)
            & (filtered["date_ouverture"] < end + pd.Timedelta(days=1))
        ]
        filtered.attrs = source_attrs.copy()

    for label, column in [
        ("Annees", "mois_ouverture"),
        ("Sites / localisations", "site"),
        ("Managers", "manager"),
        ("Groupes traitants", "groupe_traitant"),
        ("Etats tickets", "statut"),
    ]:
        options = sorted(filtered[column].dropna().astype(str).unique())
        if column == "mois_ouverture":
            years = sorted({option[:4] for option in options})
            selected_years = st.multiselect(label, years, default=years)
            filtered = filtered[filtered[column].astype(str).str[:4].isin(selected_years)]
            filtered.attrs = source_attrs.copy()
            continue
        selected = st.multiselect(label, options=options, default=options)
        if selected:
            filtered = filtered[filtered[column].astype(str).isin(selected)]
            filtered.attrs = source_attrs.copy()

    filtered.attrs = source_attrs.copy()
    return filtered


def sidebar_stat(label: str, value: str) -> None:
    st.markdown(
        f"""
        <div class="sidebar-stat">
            <div class="sidebar-stat-label">{label}</div>
            <div class="sidebar-stat-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_sidebar_summary(df: pd.DataFrame, mois: str) -> None:
    result = kpi.calculate_month_kpi(df, mois)
    chart_card_title("Synthese du mois")
    sidebar_stat("Demandes ouvertes", fmt(result.total_ouverts))
    sidebar_stat("Tickets fermes", fmt(result.total_fermes))
    sidebar_stat("Ouverts et fermes", fmt(result.ouverts_et_fermes_meme_mois))
    sidebar_stat("Delai moyen", fmt(result.delai_moyen_heures, " h"))
    sidebar_stat("Satisfaction", fmt(result.satisfaction_moyenne, " / 5"))
    sidebar_stat("Participation enquete", fmt(result.satisfaction.taux_participation, " %"))


def _static_top_nav_unused() -> None:
    st.markdown(
        """
        <div class="top-nav">
            <div class="brand"><div class="brand-mark">K</div><span>Sagemcom RSI</span></div>
            <div class="nav-links">
                <div class="nav-link active">Dashboard</div>
                <div class="nav-link">Analytics</div>
                <div class="nav-link">Satisfaction</div>
                <div class="nav-link">Rapports</div>
                <div class="nav-link">API</div>
            </div>
            <div class="nav-tools">⚙ ↻</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def top_nav() -> None:
    st.markdown(
        """
        <div class="top-nav">
            <div class="brand"><div class="brand-mark">R</div><span>Sagemcom RSI</span></div>
            <div class="nav-tools">KPI ASKit | Support IT</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


NAV_ITEMS = (
    ("Dashboard", "dashboard"),
    ("Analytics", "analytics"),
    ("Satisfaction", "satisfaction"),
    ("Rapports", "reports"),
    ("API", "api"),
)


PAGE_TITLES = {
    "dashboard": ("Vue globale", "Suivi mensuel des tickets IT ASKit"),
    "analytics": ("Analytics", "Comparaison des KPI entre deux mois"),
    "satisfaction": ("Satisfaction", "Analyse des reponses enquete ASKit"),
    "reports": ("Rapports", "Generation des exports PDF et Excel"),
    "api": ("API", "Endpoints REST disponibles pour integrer les KPI"),
}


def sidebar_brand() -> None:
    logo_uri = image_data_uri(LOGO_PATH)
    logo_html = f'<div class="logo-card"><img src="{logo_uri}" alt="Sagemcom"></div>' if logo_uri else ""
    st.markdown(
        f"""
        <div class="sidebar-brand">
            {logo_html}
            <div class="sidebar-kicker">Service RSI - Sagemcom</div>
            <div class="sidebar-title">Salle de controle support IT</div>
            <div class="sidebar-subtitle">KPI automatises depuis les exports ASKit reels</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_nav_buttons() -> str:
    if "active_page" not in st.session_state:
        st.session_state["active_page"] = "dashboard"

    st.markdown('<div class="nav-button-strip">', unsafe_allow_html=True)
    for label, page_key in NAV_ITEMS:
        active = st.session_state["active_page"] == page_key
        if st.button(
            label,
            key=f"nav_{page_key}",
            type="primary" if active else "secondary",
            use_container_width=True,
        ):
            st.session_state["active_page"] = page_key
    st.markdown("</div>", unsafe_allow_html=True)
    return st.session_state["active_page"]


def page_header(page_key: str, mois: str) -> None:
    title, subtitle = PAGE_TITLES.get(page_key, PAGE_TITLES["dashboard"])
    st.markdown(
        f"""
        <div class="page-header">
            <div>
                <h1>{title}</h1>
                <div class="page-subtitle">{subtitle}</div>
            </div>
            <div class="month-pill">Mois pilote: {mois}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_empty_state(error: Exception | None = None) -> None:
    st.markdown(
        """
        <div class="page-header">
            <div>
                <h1>Dashboard en attente</h1>
                <div class="page-subtitle">
                    Importez le fichier demandes ASKit dans la barre laterale, puis cliquez sur Generer le dashboard.
                    Aucune statistique n'est affichee avant cette action.
                </div>
            </div>
            <div class="month-pill">Aucun input actif</div>
        </div>
        <div class="upload-hero">
            <div class="upload-hero-title">Processus attendu</div>
            <div class="upload-hero-text">
                1. Importer Demandes ASKit. 2. Ajouter Enquete et Employes si disponibles.
                3. Cliquer sur Generer le dashboard. 4. Les KPI, alertes et exports deviennent disponibles.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if error is not None:
        st.error(str(error))


def validation_card(title: str, examples: str, result: dict[str, object] | None, required: str) -> None:
    if result is None:
        st.markdown(
            f"""
            <div class="source-warn">
                {title}: en attente. Champs attendus: {required}. Exemples: {examples}.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    if result["ok"]:
        found = result.get("found", {})
        st.markdown(
            f"""
            <div class="source-ok">
                {title}: valide. Colonnes detectees: {", ".join(found.values())}.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    missing = ", ".join(str(item) for item in result.get("missing", []))
    st.markdown(
        f"""
        <div class="alert-red">
            {title}: colonnes manquantes ({missing}). Champs attendus: {required}.
        </div>
        """,
        unsafe_allow_html=True,
    )


def source_type_card(slot_label: str, expected_type: str, raw: pd.DataFrame | None) -> bool:
    if raw is None or raw.empty:
        return False

    detected = detect_source_type(raw)["detected"]
    if detected == expected_type:
        st.markdown(
            f"""
            <div class="source-ok">
                {slot_label}: type detecte correct ({detected}).
            </div>
            """,
            unsafe_allow_html=True,
        )
        return True

    st.markdown(
        f"""
        <div class="alert-red">
            {slot_label}: mauvais emplacement. Type detecte: {detected or "inconnu"}.
            Type attendu: {expected_type}.
        </div>
        """,
        unsafe_allow_html=True,
    )
    return False


def kpi_card(label: str, value: str, icon: str, color: str) -> None:
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-head">
                <div class="kpi-value">{value}</div>
                <div class="kpi-icon" style="background:{color}">{icon}</div>
            </div>
            <div class="kpi-label">{label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def chart_card_title(title: str, note: str = "") -> None:
    note_html = f'<div class="mini-note">{note}</div>' if note else ""
    st.markdown(f'<div class="section-title">{title}</div>{note_html}', unsafe_allow_html=True)


def apply_plotly_theme(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=10, b=8),
        font=dict(family="Inter, Segoe UI, Roboto, Arial, sans-serif", size=13, color="#eef7f4"),
        legend=dict(font=dict(size=12, color="#7fa39c"), title_font=dict(size=12, color="#7fa39c")),
        legend_title_text="",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(
            bgcolor="#0f2222",
            bordercolor="#1f4444",
            font=dict(family="Inter, Segoe UI, Roboto, Arial, sans-serif", size=12, color="#ffffff"),
        ),
    )
    fig.update_xaxes(
        title_font=dict(size=12, color="#7fa39c"),
        tickfont=dict(size=12, color="#7fa39c"),
        gridcolor="#1f4444",
        zerolinecolor="#1f4444",
    )
    fig.update_yaxes(
        title_font=dict(size=12, color="#7fa39c"),
        tickfont=dict(size=12, color="#7fa39c"),
        gridcolor="#1f4444",
        zerolinecolor="#1f4444",
    )
    return fig


def _side_menu_unused() -> None:
    st.markdown(
        """
        <div class="side-menu">
            <div class="side-menu-item active"><span class="side-menu-icon">●</span>Analytics</div>
            <div class="side-menu-item"><span class="side-menu-icon">◇</span>Sources ASKit</div>
            <div class="side-menu-item"><span class="side-menu-icon">□</span>KPI Mensuels</div>
            <div class="side-menu-item"><span class="side-menu-icon">◌</span>Satisfaction</div>
            <div class="side-menu-item"><span class="side-menu-icon">▣</span>Rapports</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_alerts(df: pd.DataFrame, mois: str) -> None:
    config = load_config()
    summary = kpi.monthly_summary(df)
    alerts = anomalies.detect_anomalies(
        summary,
        mois,
        config.thresholds.anomaly_std_multiplier,
        config.thresholds.anomaly_window_months,
    )
    for alert in alerts:
        css_class = "alert-red" if alert["severity"] == "red" else "alert-orange"
        metric = "Delai moyen" if alert["metric"] == "delai_moyen_jours" else "Satisfaction"
        st.markdown(
            f"""
            <div class="{css_class}">
                {metric} atypique sur {mois}: valeur {compact(alert["value"])},
                reference historique {compact(alert["baseline_mean"])}
            </div>
            """,
            unsafe_allow_html=True,
        )


def show_smart_insights(df: pd.DataFrame, mois: str) -> None:
    for insight in insights.generate_month_insights(df, mois):
        css_class = "alert-red" if insight["level"] == "red" else "source-ok"
        st.markdown(
            f"""
            <div class="{css_class}">
                {insight["title"]}: {insight["message"]}
            </div>
            """,
            unsafe_allow_html=True,
        )


def status_donut(df: pd.DataFrame, mois: str) -> go.Figure:
    data = kpi.filter_opened_month(df, mois)
    status = data.groupby("statut", as_index=False).size().rename(columns={"size": "tickets"})
    fig = px.pie(
        status,
        names="statut",
        values="tickets",
        hole=0.62,
        color_discrete_sequence=PALETTE,
    )
    fig.update_traces(textinfo="percent", textfont_size=13)
    fig.update_layout(showlegend=True)
    return apply_plotly_theme(fig, 260)


def satisfaction_donut(df: pd.DataFrame, mois: str) -> go.Figure:
    responses = df.attrs.get("satisfaction_responses")
    if responses is None or responses.empty:
        counts = pd.DataFrame({"note": ["Donnee indisponible"], "tickets": [1]})
    else:
        if "mois_enquete" in responses.columns and responses["mois_enquete"].notna().any():
            scoped = responses[responses["mois_enquete"].eq(mois)]
            if scoped.empty:
                scoped = responses
        else:
            scoped = responses
        bins = scoped["satisfaction_traitement"].dropna().round().astype(int).astype(str) + "/5"
        if bins.empty:
            bins = pd.Series(["Donnee indisponible"])
        counts = bins.value_counts().reset_index()
    counts.columns = ["note", "tickets"]
    fig = px.pie(counts, names="note", values="tickets", hole=0.62, color_discrete_sequence=PALETTE)
    fig.update_traces(textinfo="percent", textfont_size=13)
    fig.update_layout(showlegend=True)
    return apply_plotly_theme(fig, 260)


def monthly_line(df: pd.DataFrame) -> go.Figure:
    monthly = kpi.monthly_summary(df)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=monthly["mois"],
            y=monthly["total_ouverts"],
            mode="lines+markers+text",
            text=monthly["total_ouverts"],
            textposition="top center",
            name="Ouverts",
            line=dict(color=COLORS["blue"], width=3, shape="spline"),
            marker=dict(size=7),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=monthly["mois"],
            y=monthly["total_fermes"],
            mode="lines+markers",
            name="Fermes",
            line=dict(color=COLORS["green"], width=3, shape="spline"),
            marker=dict(size=7),
        )
    )
    fig.update_layout(
        legend_title_text="",
    )
    fig.update_xaxes(showgrid=False)
    return apply_plotly_theme(fig, 260)


def top_horizontal_bar(df: pd.DataFrame, mois: str, column: str, label: str) -> go.Figure:
    data = kpi.distribution(df, mois, column, top=5)
    fig = px.bar(
        data.sort_values("nombre_tickets"),
        x="nombre_tickets",
        y=column,
        orientation="h",
        text="nombre_tickets",
        color_discrete_sequence=[COLORS["blue"]],
        labels={"nombre_tickets": "Tickets", column: label},
    )
    fig.update_layout(showlegend=False)
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(title=None)
    return apply_plotly_theme(fig, 255)


def subjects_by_month(df: pd.DataFrame) -> go.Figure:
    top_subjects = (
        df.groupby("categorie", as_index=False)
        .size()
        .rename(columns={"size": "tickets"})
        .sort_values("tickets", ascending=False)
        .head(5)["categorie"]
    )
    data = df[df["categorie"].isin(top_subjects)]
    monthly_subjects = (
        data.groupby(["mois_ouverture", "categorie"], as_index=False)
        .size()
        .rename(columns={"size": "tickets"})
        .sort_values("mois_ouverture")
    )
    fig = px.bar(
        monthly_subjects,
        x="mois_ouverture",
        y="tickets",
        color="categorie",
        color_discrete_sequence=PALETTE,
        labels={"mois_ouverture": "Mois", "tickets": "Demandes ouvertes", "categorie": "Sujet"},
    )
    fig.update_layout(
        legend_title_text="",
    )
    fig.update_xaxes(showgrid=False)
    return apply_plotly_theme(fig, 260)


def selected_month_subjects(df: pd.DataFrame, mois: str) -> go.Figure:
    data = kpi.subjects_opened_month(df, mois, top=10)
    fig = px.bar(
        data,
        x="categorie",
        y="nombre_tickets",
        color="categorie",
        text="nombre_tickets",
        color_discrete_sequence=PALETTE,
        labels={"categorie": "Sujet", "nombre_tickets": "Demandes ouvertes"},
    )
    fig.update_layout(
        showlegend=False,
    )
    fig.update_xaxes(tickangle=30)
    return apply_plotly_theme(fig, 260)


def last_tickets_table(df: pd.DataFrame, mois: str) -> pd.DataFrame:
    data = kpi.filter_opened_month(df, mois).sort_values("date_ouverture", ascending=False).head(6)
    columns = ["ticket_id", "date_ouverture", "beneficiaire", "categorie", "statut", "site"]
    table = data[columns].copy()
    table["date_ouverture"] = table["date_ouverture"].dt.strftime("%d/%m/%Y")
    return table.rename(
        columns={
            "ticket_id": "N ticket",
            "date_ouverture": "Date",
            "beneficiaire": "Beneficiaire",
            "categorie": "Sujet",
            "statut": "Etat",
            "site": "Site",
        }
    )


def show_dashboard(df: pd.DataFrame, mois: str, source_label: str) -> None:
    result = kpi.calculate_month_kpi(df, mois)
    source_class = "source-ok" if "Import" in source_label or "Chemin" in source_label else "source-warn"
    st.markdown(
        f"""
        <div class="upload-hero">
            <div class="upload-hero-title">Input ASKit actif</div>
            <div class="upload-hero-text">
                La zone drag and drop est disponible dans la barre laterale. Source actuellement utilisee:
                <strong>{source_label}</strong>.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="{source_class}">Source active: {source_label}. Tous les KPI et graphes sont calcules depuis ces donnees.</div>',
        unsafe_allow_html=True,
    )
    show_alerts(df, mois)
    show_smart_insights(df, mois)

    cards = st.columns(5)
    with cards[0]:
        kpi_card("Tickets ouverts", str(result.total_ouverts), "O", COLORS["blue"])
    with cards[1]:
        kpi_card("Tickets fermes", str(result.total_fermes), "F", COLORS["purple"])
    with cards[2]:
        kpi_card("Ouverts et fermes", fmt(result.ouverts_et_fermes_meme_mois), "M", COLORS["pink"])
    with cards[3]:
        kpi_card("Delai moyen", fmt(result.delai_moyen_heures, " h"), "D", COLORS["yellow"])
    with cards[4]:
        kpi_card("Satisfaction", fmt(result.satisfaction_moyenne, " / 5"), "S", COLORS["orange"])

    row1_left, row1_mid, row1_right = st.columns([1.05, 1.05, 2.15])
    with row1_left:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        chart_card_title("Tickets par statut")
        st.plotly_chart(status_donut(df, mois), use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with row1_mid:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        chart_card_title("Satisfaction")
        st.plotly_chart(satisfaction_donut(df, mois), use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with row1_right:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        chart_card_title("Tendance mensuelle", "Ouverts vs fermes")
        st.plotly_chart(monthly_line(df), use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    row2_left, row2_right = st.columns([1.2, 2.0])
    with row2_left:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        chart_card_title("Top 5 sites")
        st.plotly_chart(top_horizontal_bar(df, mois, "site", "Site"), use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with row2_right:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        chart_card_title("Derniers tickets ouverts")
        st.dataframe(last_tickets_table(df, mois), use_container_width=True, hide_index=True, height=255)
        st.markdown("</div>", unsafe_allow_html=True)

    row3_left, row3_right = st.columns([1.2, 2.0])
    with row3_left:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        chart_card_title("Top 5 sujets du mois", "Tickets ouverts du mois groupes par Sujet")
        st.plotly_chart(top_horizontal_bar(df, mois, "categorie", "Sujet"), use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    chart_card_title(
        "Satisfaction detaillee",
        "Moyennes issues du fichier enquete; fallback global si la date enquete est inexploitable",
    )
    sat = result.satisfaction
    cols = st.columns(4)
    cols[0].metric("Traitement", fmt(sat.satisfaction_globale, " / 5"))
    cols[1].metric("Communication", fmt(sat.communication, " / 5"))
    cols[2].metric("Temps percu", fmt(sat.temps_percu, " / 5"))
    cols[3].metric("Participation", fmt(sat.taux_participation, " %"))
    if sat.rubrique_moins_satisfaisante:
        st.caption(f"Rubrique la moins satisfaisante: {sat.rubrique_moins_satisfaisante}")
    if sat.fallback_global:
        st.warning("Satisfaction affichee en moyenne globale: aucune reponse exploitable pour le mois selectionne.")
    st.markdown("</div>", unsafe_allow_html=True)
    with row3_right:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        chart_card_title("Sujets ouverts du mois", "Tri du plus frequent au moins frequent")
        st.plotly_chart(selected_month_subjects(df, mois), use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)


def show_comparison(df: pd.DataFrame, months: list[str], default_month: str) -> None:
    col_a, col_b = st.columns(2)
    month_a = col_a.selectbox("Mois A", options=months, index=max(0, len(months) - 2), key="compare_a")
    month_b = col_b.selectbox("Mois B", options=months, index=months.index(default_month), key="compare_b")

    left = kpi.calculate_month_kpi(df, month_a).as_dict()
    right = kpi.calculate_month_kpi(df, month_b).as_dict()
    rows = []
    for metric in ["total_ouverts", "total_fermes", "ouverts_et_fermes_meme_mois", "delai_moyen_heures", "satisfaction_moyenne"]:
        old = left[metric]
        new = right[metric]
        if old in [None, 0] or pd.isna(old) or new is None or pd.isna(new):
            delta = None
        else:
            delta = (new - old) / old * 100
        rows.append(
            {
                "Indicateur": metric,
                month_a: compact(old),
                month_b: compact(new),
                "Variation": "Donnee indisponible" if delta is None else f"{delta:+.1f}%",
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def show_exports(df: pd.DataFrame, mois: str) -> None:
    config = load_config()
    exports_dir = resolve_path(config.data.exports_dir) or Path("data/exports")
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    chart_card_title("Rapports mensuels", "Exports bases sur les donnees filtrees et le mois selectionne")
    col1, col2 = st.columns(2)
    if col1.button("Exporter le rapport PDF", use_container_width=True):
        path = export_month_pdf(df, mois, exports_dir, config.company_name)
        st.success(f"PDF genere: {path}")
    if col2.button("Exporter le rapport Excel", use_container_width=True):
        path = export_month_excel(df, mois, exports_dir)
        st.success(f"Excel genere: {path}")
    st.markdown("</div>", unsafe_allow_html=True)


def show_satisfaction_audit(df: pd.DataFrame, mois: str, sat: kpi.SatisfactionResult) -> None:
    responses = df.attrs.get("satisfaction_responses")
    opened_count = len(kpi.filter_opened_month(df, mois))
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    chart_card_title("Audit du calcul satisfaction", "Preuve de calcul depuis les colonnes reelles du fichier enquete")

    if responses is None or responses.empty:
        st.warning("Aucun fichier enquete satisfaction n'est charge: aucune note n'est inventee.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    if "mois_enquete" in responses.columns and responses["mois_enquete"].notna().any():
        scoped = responses[responses["mois_enquete"].eq(mois)].copy()
        scope_label = f"reponses du mois {mois}"
        if scoped.empty:
            scoped = responses.copy()
            scope_label = "fallback moyenne globale: aucune reponse datee pour le mois"
    else:
        scoped = responses.copy()
        scope_label = "fallback moyenne globale: date enquete absente ou inexploitable"

    required = ["satisfaction_traitement", "communication_operateurs", "satisfaction_temps"]
    valid_responses = scoped[required].apply(pd.to_numeric, errors="coerce").dropna(how="all")
    sources = df.attrs.get("column_sources", {}).get("satisfaction", {})
    rows = [
        {
            "KPI": "Satisfaction traitement",
            "Colonne source": sources.get("satisfaction_traitement", "satisfaction_traitement"),
            "Formule": "mean(colonne)",
            "Valeur": fmt(sat.satisfaction_globale, " / 5"),
        },
        {
            "KPI": "Communication",
            "Colonne source": sources.get("communication_operateurs", "communication_operateurs"),
            "Formule": "mean(colonne)",
            "Valeur": fmt(sat.communication, " / 5"),
        },
        {
            "KPI": "Temps de traitement",
            "Colonne source": sources.get("satisfaction_temps", "satisfaction_temps"),
            "Formule": "mean(colonne)",
            "Valeur": fmt(sat.temps_percu, " / 5"),
        },
        {
            "KPI": "Taux participation",
            "Colonne source": "N reponses enquete / tickets ouverts",
            "Formule": f"{len(valid_responses)} / {opened_count} * 100",
            "Valeur": fmt(sat.taux_participation, " %"),
        },
    ]
    st.caption(f"Perimetre utilise: {scope_label}. Reponses exploitees: {len(valid_responses)}.")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    if sat.rubrique_moins_satisfaisante:
        st.caption(f"Point le plus bas calcule avec idxmin sur les 3 moyennes: {sat.rubrique_moins_satisfaisante}.")
    st.markdown("</div>", unsafe_allow_html=True)


def show_satisfaction_page(df: pd.DataFrame, mois: str) -> None:
    result = kpi.calculate_month_kpi(df, mois)
    sat = result.satisfaction

    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    chart_card_title("Satisfaction enquete", "Calcul depuis le fichier enquete ASKit importe")
    cols = st.columns(4)
    cols[0].metric("Satisfaction traitement", fmt(sat.satisfaction_globale, " / 5"))
    cols[1].metric("Communication", fmt(sat.communication, " / 5"))
    cols[2].metric("Temps de traitement", fmt(sat.temps_percu, " / 5"))
    cols[3].metric("Participation", fmt(sat.taux_participation, " %"))
    if sat.rubrique_moins_satisfaisante:
        st.caption(f"Rubrique la moins satisfaisante: {sat.rubrique_moins_satisfaisante}")
    if sat.fallback_global:
        st.warning("Moyenne globale utilisee: aucune date enquete exploitable pour le mois selectionne.")
    st.markdown("</div>", unsafe_allow_html=True)

    show_satisfaction_audit(df, mois, sat)

    left, right = st.columns([1.05, 1.55])
    with left:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        chart_card_title("Repartition des notes")
        st.plotly_chart(satisfaction_donut(df, mois), use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with right:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        chart_card_title("Trace des reponses")
        responses = df.attrs.get("satisfaction_responses")
        if responses is None or responses.empty:
            st.info("Donnee indisponible: aucun fichier enquete charge.")
        else:
            display = responses.copy()
            if "mois_enquete" in display.columns and display["mois_enquete"].notna().any():
                scoped = display[display["mois_enquete"].eq(mois)]
                if not scoped.empty:
                    display = scoped
            wanted = [
                "ticket_id",
                "mois_enquete",
                "satisfaction_traitement",
                "communication_operateurs",
                "satisfaction_temps",
            ]
            available = [column for column in wanted if column in display.columns]
            st.dataframe(display[available].head(20), use_container_width=True, hide_index=True, height=300)
        st.markdown("</div>", unsafe_allow_html=True)


def show_api_panel(mois: str) -> None:
    endpoints = pd.DataFrame(
        [
            {"Endpoint": f"GET /kpi/{mois}", "Role": "Indicateurs mensuels principaux"},
            {"Endpoint": f"GET /kpi/{mois}/par-site", "Role": "Nombre de tickets ouverts par site"},
            {"Endpoint": f"GET /satisfaction/{mois}", "Role": "Satisfaction depuis l'enquete ASKit"},
            {"Endpoint": f"GET /export/{mois}", "Role": "Generation PDF et Excel du mois"},
            {"Endpoint": "GET /docs", "Role": "Documentation Swagger FastAPI"},
        ]
    )
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    chart_card_title("API REST", "Demarrer l'API avec: uvicorn api.main:app --reload")
    st.dataframe(endpoints, use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)


def _legacy_main_unused() -> None:
    st.set_page_config(page_title="KPI RSI Sagemcom", page_icon=":bar_chart:", layout="wide")
    inject_css()
    st.markdown('<div class="app-shell">', unsafe_allow_html=True)
    top_nav()
    st.markdown('<div class="control-panel">', unsafe_allow_html=True)

    try:
        df, source_label = load_sidebar_dataset()
    except SchemaError as exc:
        st.error(
            "Le fichier importé n'est pas reconnu comme un extrait des demandes ASKit. "
            "Importe le rapport ASKit des demandes, pas un fichier exemple de tâches. "
            "Colonnes attendues: N° ticket, Bénéficiaire, Enregistré le, Date de résolution, "
            "Sujet, Meta Statut, Bénéficiaire : Localisation."
        )
        st.caption(str(exc))
        st.stop()
    except Exception as exc:
        st.error(str(exc))
        st.stop()

    if df.empty:
        st.warning("Aucune donnee chargee.")
        st.stop()

    filtered = apply_filters(df)
    months = kpi.available_months(filtered)
    if not months:
        st.warning("Aucun mois disponible apres filtrage.")
        st.stop()

    mois = st.selectbox("Mois de pilotage", options=months, index=len(months) - 1)
    show_sidebar_summary(filtered, mois)
    st.markdown("</div>", unsafe_allow_html=True)

    active_page = render_nav_buttons()
    page_header(active_page, mois)
    if active_page == "dashboard":
        show_dashboard(filtered, mois, source_label)
    elif active_page == "analytics":
        show_comparison(filtered, months, mois)
    elif active_page == "satisfaction":
        show_satisfaction_page(filtered, mois)
    elif active_page == "reports":
        show_exports(filtered, mois)
    elif active_page == "api":
        show_api_panel(mois)
    st.markdown("</div>", unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(page_title="KPI RSI Sagemcom", page_icon=":bar_chart:", layout="wide")
    inject_css()

    control_col, dashboard_col = st.columns([0.82, 2.9], gap="large")

    with control_col:
        sidebar_brand()
        active_page = render_nav_buttons()
        df = None
        source_label = None
        load_error = None
        try:
            df, source_label = load_sidebar_dataset()
        except SchemaError as exc:
            st.error(
                "Le fichier importe n'est pas reconnu comme un extrait des demandes ASKit. "
                "Importe le rapport ASKit des demandes. Colonnes attendues: N ticket, "
                "Beneficiaire, Enregistre le, Date de resolution, Sujet, Meta Statut, Localisation."
            )
            st.caption(str(exc))
            load_error = exc
        except Exception as exc:
            st.error(str(exc))
            load_error = exc

        if df is None:
            filtered = None
            months = []
            mois = ""
        elif df.empty:
            st.warning("Aucune donnee chargee.")
            filtered = None
            months = []
            mois = ""
        else:
            filtered = apply_filters(df)
            months = kpi.available_months(filtered)

        if df is not None and not months:
            st.warning("Aucun mois disponible apres filtrage.")
            filtered = None
            mois = ""
        elif months:
            mois = st.selectbox("Mois de pilotage", options=months, index=len(months) - 1)
            show_sidebar_summary(filtered, mois)

    with dashboard_col:
        if filtered is None or not mois or source_label is None:
            show_empty_state(load_error)
        elif active_page == "dashboard":
            page_header(active_page, mois)
            show_dashboard(filtered, mois, source_label)
        elif active_page == "analytics":
            page_header(active_page, mois)
            show_comparison(filtered, months, mois)
        elif active_page == "satisfaction":
            page_header(active_page, mois)
            show_satisfaction_page(filtered, mois)
        elif active_page == "reports":
            page_header(active_page, mois)
            show_exports(filtered, mois)
        elif active_page == "api":
            page_header(active_page, mois)
            show_api_panel(mois)


if __name__ == "__main__":
    main()
