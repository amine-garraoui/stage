from pathlib import Path
import base64
import html
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_echarts import st_echarts, JsCode

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

OFFICIAL_SITE_POLES = [
    ("Megrine / AVS", "Tunisie/Megrine", "AVS"),
    ("Megrine / BBS", "Tunisie/Megrine", "BBS"),
    ("Megrine / E&T", "Tunisie/Megrine", "E&T"),
    ("Megrine / supports", "Tunisie/Megrine", "supports"),
    ("kram / E&T", "Tunisie/Kram", "E&T"),
    ("kram / supports", "Tunisie/Kram", "supports"),
    ("kram / BBS", "Tunisie/Kram", "BBS"),
    ("Sousse / E&T", "Tunisie/Sousse", "E&T"),
    ("Sousse / supports", "Tunisie/Sousse", "supports"),
]

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
        @import url('https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,300..900;1,14..32,300..900&display=swap');

        /* ── Reset & hide Streamlit chrome ──────────────────────── */
        #MainMenu, footer, header,
        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        [data-testid="stStatusWidget"],
        [data-testid="StyledFullScreenButton"] { display: none !important; }

        /* ── Typography base ─────────────────────────────────────── */
        html, body, [class*="css"], .stApp, .stMarkdown,
        .stText, label, p, span, div {
            font-family: "Inter", "Segoe UI", Roboto, Arial, sans-serif;
            letter-spacing: 0;
        }

        /* ── App background (deep navy like Flux) ────────────────── */
        .stApp { background: #0f0f14 !important; color: #e2e8f0; }

        /* ── Block container ─────────────────────────────────────── */
        .block-container {
            padding: 0 !important;
            max-width: 100% !important;
        }

        /* ── Native Streamlit Sidebar ────────────────────────────── */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #14141c 0%, #101017 100%) !important;
            border-right: 1px solid rgba(124, 58, 237, 0.16) !important;
            min-width: 82px !important;
            width: 82px !important;
            max-width: 82px !important;
        }
        [data-testid="stSidebar"][aria-expanded="true"] {
            width: 82px !important;
        }
        [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
            width: 82px !important;
        }
        [data-testid="stSidebar"] > div:first-child {
            padding: 0 !important;
        }
        [data-testid="collapsedControl"] { display: flex !important; }

        /* ── Sidebar scrollbar ───────────────────────────────────── */
        [data-testid="stSidebar"]::-webkit-scrollbar { width: 4px; }
        [data-testid="stSidebar"]::-webkit-scrollbar-track { background: transparent; }
        [data-testid="stSidebar"]::-webkit-scrollbar-thumb { background: #2d2d44; border-radius: 2px; }

        /* ── Flux sidebar brand block ────────────────────────────── */
        .flux-sidebar-brand {
            padding: 16px 14px 12px 14px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            margin-bottom: 4px;
        }
        .flux-brand-logo {
            display: flex;
            align-items: center;
            gap: 9px;
        }
        .flux-brand-icon {
            width: 30px; height: 30px;
            border-radius: 9px;
            background: linear-gradient(135deg, #7c3aed, #4f46e5);
            display: flex; align-items: center; justify-content: center;
            font-size: 15px; color: #fff; font-weight: 800;
            flex-shrink: 0;
            box-shadow: 0 4px 12px -4px rgba(124,58,237,.6);
        }
        .flux-brand-name {
            color: #f1f5f9;
            font-size: 14px; font-weight: 700; line-height: 1.05;
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
            display: none;
        }
        .flux-brand-sub {
            color: #5b6675;
            font-size: 10px; font-weight: 500;
            margin-top: 2px; padding-left: 39px;
            text-transform: uppercase; letter-spacing: 0.05em;
        }

        /* ── Sidebar nav label ───────────────────────────────────── */
        .flux-nav-label {
            padding: 8px 16px 2px 16px;
            color: #3f4756;
            font-size: 9px; font-weight: 700;
            text-transform: uppercase; letter-spacing: 0.12em;
            display: none;
        }

        /* ── Sidebar nav buttons ─────────────────────────────────── */
        [data-testid="stSidebar"] .stButton > button {
            width: 100% !important;
            text-align: center !important;
            justify-content: center !important;
            border-radius: 9px !important;
            border: none !important;
            background: transparent !important;
            color: #8b97a8 !important;
            font-size: 20px !important;
            font-weight: 500 !important;
            padding: 8px 4px !important;
            min-height: 42px !important;
            transition: all .15s ease !important;
            box-shadow: none !important;
            margin: 2px 8px !important;
            width: calc(100% - 16px) !important;
        }
        [data-testid="stSidebar"] .stButton > button:hover {
            background: rgba(124, 58, 237, 0.1) !important;
            color: #d7c9ff !important;
            transform: translateY(-2px) !important;
        }
        [data-testid="stSidebar"] button[kind="primary"] {
            background: rgba(109, 40, 217, 0.22) !important;
            color: #d7c9ff !important;
            border-left: 3px solid #7c3aed !important;
            font-weight: 650 !important;
            padding-left: 4px !important;
            animation: none !important;
            box-shadow: none !important;
        }

        /* ── Sidebar user card (compact) ─────────────────────────── */
        .flux-user-card {
            padding: 8px 6px;
            border-radius: 10px;
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.05);
            display: flex; align-items: center; gap: 8px;
            justify-content: center;
        }
        .flux-user-avatar {
            width: 28px; height: 28px; border-radius: 50%;
            background: linear-gradient(135deg, #7c3aed, #ec4899);
            display: flex; align-items: center; justify-content: center;
            color: #fff; font-size: 12px; font-weight: 700;
            flex-shrink: 0;
        }
        .flux-user-name, .flux-user-role { display: none; }

        /* ── Main content area ───────────────────────────────────── */
        .flux-main {
            padding: 0 28px 40px 28px;
            min-height: 100vh;
        }

        /* ── Top bar ─────────────────────────────────────────────── */
        .flux-topbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 16px 0 20px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            margin-bottom: 20px;
            gap: 16px;
        }
        .flux-topbar-title {
            color: #f8fafc;
            font-size: 22px; font-weight: 700;
        }
        .flux-topbar-right {
            display: flex; align-items: center; gap: 10px;
        }
        .flux-badge {
            background: rgba(124, 58, 237, 0.15);
            border: 1px solid rgba(124, 58, 237, 0.35);
            color: #a78bfa;
            font-size: 11px; font-weight: 600;
            padding: 4px 10px; border-radius: 20px;
        }
        .flux-badge-green {
            background: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.3);
            color: #34d399;
            font-size: 11px; font-weight: 600;
            padding: 4px 10px; border-radius: 20px;
        }

        /* ── Hero gradient banner (Flux style) ───────────────────── */
        .flux-hero {
            border-radius: 14px;
            background: linear-gradient(120deg, #1e1b4b 0%, #312e81 30%, #4338ca 60%, #3b82f6 100%);
            padding: 24px 28px;
            margin-bottom: 20px;
            position: relative;
            overflow: hidden;
        }
        .flux-hero::before {
            content: "";
            position: absolute;
            top: -40px; right: -40px;
            width: 200px; height: 200px;
            border-radius: 50%;
            background: rgba(139, 92, 246, 0.25);
            filter: blur(40px);
        }
        .flux-hero-eyebrow {
            color: rgba(255,255,255,0.7);
            font-size: 11px; font-weight: 600;
            text-transform: uppercase; letter-spacing: 0.1em;
            margin-bottom: 6px;
        }
        .flux-hero-title {
            color: #ffffff;
            font-size: 26px; font-weight: 800; line-height: 1.15;
            margin-bottom: 4px;
        }
        .flux-hero-sub {
            color: rgba(255,255,255,0.65);
            font-size: 13px; font-weight: 400;
        }
        .flux-hero-pill {
            display: inline-block;
            background: rgba(255,255,255,0.15);
            backdrop-filter: blur(6px);
            border: 1px solid rgba(255,255,255,0.2);
            color: #fff;
            border-radius: 20px;
            font-size: 12px; font-weight: 600;
            padding: 4px 12px;
            margin-top: 10px;
        }

        /* ── KPI Cards (Flux style) ──────────────────────────────── */
        .flux-kpi-card {
            background: #1a1a2e;
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 12px;
            padding: 20px 18px;
            position: relative;
            overflow: hidden;
            transition: transform .18s ease, box-shadow .18s ease;
        }
        .flux-kpi-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 12px 32px rgba(0,0,0,0.35);
        }
        .flux-kpi-top {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 10px;
        }
        .flux-kpi-label {
            color: #64748b;
            font-size: 12px; font-weight: 600;
            text-transform: uppercase; letter-spacing: 0.07em;
        }
        .flux-kpi-icon {
            width: 36px; height: 36px;
            border-radius: 10px;
            display: flex; align-items: center; justify-content: center;
            font-size: 16px;
        }
        .flux-kpi-value {
            color: #f1f5f9;
            font-size: 28px; font-weight: 800;
            line-height: 1.1; margin-bottom: 8px;
        }
        .flux-kpi-trend {
            display: flex; align-items: center; gap: 5px;
            font-size: 12px; font-weight: 600;
        }
        .flux-kpi-trend-up { color: #34d399; }
        .flux-kpi-trend-neutral { color: #64748b; }

        /* ── Chart cards ─────────────────────────────────────────── */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: #16161f !important;
            border: 1px solid rgba(255,255,255,0.07) !important;
            border-radius: 12px !important;
            box-shadow: none !important;
        }
        .chart-card {
            background: #16161f;
            border: 1px solid rgba(255,255,255,0.07);
            border-radius: 12px;
            padding: 18px;
        }
        .section-title {
            color: #f1f5f9;
            font-size: 14px; font-weight: 600;
            margin-bottom: 2px;
        }
        .mini-note {
            color: #475569;
            font-size: 12px; font-weight: 400;
            margin-bottom: 10px;
        }

        /* ── Page header ─────────────────────────────────────────── */
        .page-header {
            background: linear-gradient(120deg, #1e1b4b 0%, #312e81 30%, #4338ca 60%, #3b82f6 100%);
            border-radius: 14px;
            padding: 20px 24px;
            margin-bottom: 18px;
            position: relative; overflow: hidden;
        }
        .page-header::before {
            content: "";
            position: absolute; top: -30px; right: -30px;
            width: 160px; height: 160px; border-radius: 50%;
            background: rgba(139,92,246,0.2); filter: blur(30px);
        }
        .page-header h1 {
            color: #ffffff !important;
            font-size: 22px !important; font-weight: 800 !important;
            margin: 0 0 4px 0 !important;
        }
        .page-subtitle { color: rgba(255,255,255,0.65); font-size: 13px; }
        .month-pill {
            display: inline-block;
            background: rgba(255,255,255,0.15);
            border: 1px solid rgba(255,255,255,0.2);
            color: #fff;
            border-radius: 20px; padding: 4px 14px;
            font-size: 12px; font-weight: 600;
            margin-top: 8px;
        }

        /* ── Metric widget override ───────────────────────────────── */
        div[data-testid="stMetric"] {
            background: #1a1a2e !important;
            border: 1px solid rgba(255,255,255,0.07) !important;
            border-radius: 10px !important;
            padding: 14px !important;
        }
        div[data-testid="stMetricLabel"] { color: #64748b !important; font-size: 12px !important; font-weight: 600 !important; text-transform: uppercase !important; }
        div[data-testid="stMetricValue"] { color: #f1f5f9 !important; font-size: 26px !important; font-weight: 800 !important; }
        div[data-testid="stMetricDelta"] { font-size: 12px !important; }

        /* ── Heading overrides ───────────────────────────────────── */
        h1 { color: #f1f5f9 !important; font-size: 22px !important; font-weight: 800 !important; }
        h2, h3, h4 { color: #e2e8f0 !important; }

        /* ── Inputs & selects ────────────────────────────────────── */
        .stSelectbox label, .stMultiSelect label,
        .stDateInput label, .stRadio label, .stTextInput label {
            color: #64748b !important; font-size: 11px !important;
            font-weight: 600 !important; text-transform: uppercase !important;
            letter-spacing: 0.06em !important;
        }
        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        div[data-baseweb="textarea"] > div {
            background: #1a1a2e !important;
            border-color: rgba(255,255,255,0.1) !important;
            color: #e2e8f0 !important;
        }
        .stTextInput input {
            background: #1a1a2e !important;
            border-color: rgba(255,255,255,0.1) !important;
            color: #e2e8f0 !important; border-radius: 8px !important;
        }

        /* ── Buttons (main content area) ─────────────────────────── */
        .stButton > button {
            background: rgba(124,58,237,0.15) !important;
            color: #c4b5fd !important;
            border: 1px solid rgba(124,58,237,0.35) !important;
            border-radius: 8px !important; font-weight: 600 !important;
            min-height: 40px !important; transition: all .15s ease !important;
        }
        .stButton > button:hover {
            background: rgba(124,58,237,0.3) !important;
            color: #e9d5ff !important;
        }
        button[kind="primary"] {
            background: linear-gradient(135deg, #7c3aed, #4f46e5) !important;
            color: #fff !important;
            border: none !important;
            box-shadow: 0 4px 14px rgba(124,58,237,0.35) !important;
            animation: none !important;
        }
        button[kind="secondary"] {
            background: #1a1a2e !important;
            color: #94a3b8 !important;
            border: 1px solid rgba(255,255,255,0.08) !important;
        }

        /* ── File uploader ───────────────────────────────────────── */
        div[data-testid="stFileUploader"] {
            background: #1a1a2e;
            border: 1px dashed rgba(124,58,237,0.4);
            border-radius: 10px; padding: 10px;
        }
        div[data-testid="stFileUploader"] section { background: transparent; border: 0; }

        /* ── DataFrame ───────────────────────────────────────────── */
        .stDataFrame { border: 1px solid rgba(255,255,255,0.07); border-radius: 10px; overflow: hidden; }
        .official-tdb-table {
            width: min(640px, 100%);
            border-collapse: collapse;
            margin: 12px 0 18px 0;
            background: #ffffff;
            color: #000000;
            font-family: Calibri, Arial, sans-serif;
            font-size: 16px;
        }
        .official-tdb-table th,
        .official-tdb-table td {
            border: 1px solid #000000;
            padding: 2px 10px;
            height: 19px;
            line-height: 18px;
        }
        .official-tdb-table thead th {
            text-align: center;
            font-weight: 700;
        }
        .official-tdb-table tbody th {
            width: 64%;
            text-align: center;
            font-weight: 700;
        }
        .official-tdb-table tbody td {
            width: 36%;
            text-align: center;
            font-weight: 400;
        }

        /* ── Expander ────────────────────────────────────────────── */
        [data-testid="stExpander"] {
            background: #16161f;
            border: 1px solid rgba(255,255,255,0.07) !important;
            border-radius: 12px !important;
        }

        /* ── Status / alert badges ───────────────────────────────── */
        .source-ok { background: rgba(16,185,129,.1); color: #34d399; border: 1px solid rgba(16,185,129,.3); border-radius: 8px; padding: 8px 12px; font-size: 13px; font-weight: 600; margin-bottom: 10px; }
        .source-warn { background: rgba(245,158,11,.08); color: #fbbf24; border: 1px solid rgba(245,158,11,.28); border-radius: 8px; padding: 8px 12px; font-size: 13px; font-weight: 600; margin-bottom: 10px; }
        .alert-red { background: rgba(239,68,68,.08); color: #fca5a5; border: 1px solid rgba(239,68,68,.28); border-left: 3px solid #ef4444; border-radius: 8px; padding: 10px 12px; margin-bottom: 8px; font-weight: 600; }
        .alert-orange { background: rgba(245,158,11,.08); color: #fbbf24; border: 1px solid rgba(245,158,11,.28); border-left: 3px solid #f59e0b; border-radius: 8px; padding: 10px 12px; margin-bottom: 8px; font-weight: 600; }
        .upload-hero { position: relative; overflow: hidden; background: linear-gradient(135deg, #182b35 0%, #142028 100%); border: 1px dashed rgba(94,234,192,.45); border-radius: 16px; padding: 22px; margin-bottom: 16px; }
        .upload-hero::after { content:""; position:absolute; top:-60%; left:-30%; width:60%; height:220%; background:linear-gradient(90deg, transparent, rgba(94,234,192,.10), transparent); transform:rotate(18deg); animation: heroSheen 4.5s ease-in-out infinite; }
        .upload-hero-title { position: relative; color: #eef7f4; font-size: 18px; font-weight: 750; margin-bottom: 6px; }
        .upload-hero-text { position: relative; color: #9fc0b9; font-size: 13px; line-height: 1.6; }

        /* ── Premium animated welcome ────────────────────────────── */
        .welcome-shell { position: relative; max-width: 1040px; margin: 30px auto 0 auto; padding: 0 24px 48px 24px; }
        .welcome-shell::before { content:""; position:absolute; top:-120px; left:50%; transform:translateX(-50%); width:640px; height:640px; background:radial-gradient(circle, rgba(94,234,192,.16) 0%, rgba(124,156,255,.10) 38%, transparent 68%); filter:blur(14px); z-index:0; animation: haloPulse 7s ease-in-out infinite; pointer-events:none; }
        .welcome-inner { position: relative; z-index: 1; }
        .welcome-badge { display:inline-flex; align-items:center; gap:8px; padding:7px 14px; border-radius:999px; background:rgba(94,234,192,.08); border:1px solid rgba(94,234,192,.28); color:#5eeac0; font-size:11px; font-weight:750; letter-spacing:.14em; text-transform:uppercase; margin-bottom:20px; opacity:0; animation: riseIn .7s ease-out .05s forwards; }
        .welcome-badge .dot { width:7px; height:7px; border-radius:50%; background:#5eeac0; box-shadow:0 0 0 0 rgba(94,234,192,.6); animation: livePulse 1.8s ease-out infinite; }
        .welcome-title { font-size: clamp(34px, 5.2vw, 62px); line-height: 1.03; font-weight: 850; letter-spacing:-.02em; margin: 0 0 18px 0; opacity:0; animation: riseIn .8s ease-out .16s forwards; }
        .welcome-title .grad { background:linear-gradient(100deg,#5eeac0,#7c9cff,#38bdf8,#5eeac0); background-size:300% 100%; -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent; animation: gradShift 6s ease infinite; }
        .welcome-copy { color: #a7c6bf; font-size: 16px; line-height: 1.7; max-width: 620px; margin-bottom: 30px; opacity:0; animation: riseIn .8s ease-out .28s forwards; }
        .welcome-steps { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin: 20px 0 26px 0; }
        .welcome-step { position:relative; overflow:hidden; background: linear-gradient(160deg,#16272e,#122028); border: 1px solid #234b47; border-radius: 16px; padding: 20px 18px; opacity:0; transform:translateY(14px); transition: transform .25s ease, border-color .25s ease, box-shadow .25s ease; }
        .welcome-step:nth-child(1){ animation: riseIn .7s ease-out .40s forwards; }
        .welcome-step:nth-child(2){ animation: riseIn .7s ease-out .52s forwards; }
        .welcome-step:nth-child(3){ animation: riseIn .7s ease-out .64s forwards; }
        .welcome-step:hover { transform: translateY(-6px); border-color: rgba(94,234,192,.5); box-shadow: 0 18px 40px -18px rgba(94,234,192,.4); }
        .welcome-step::before { content:""; position:absolute; inset:0; background:radial-gradient(120px 80px at var(--mx,80%) 0%, rgba(94,234,192,.12), transparent 70%); opacity:0; transition:opacity .3s ease; }
        .welcome-step:hover::before { opacity:1; }
        .welcome-step-number { display:inline-block; font-size: 22px; font-weight: 850; background:linear-gradient(120deg,#5eeac0,#7c9cff); -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent; margin-bottom: 10px; }
        .welcome-step-title { color: #eef7f4; font-size: 15px; font-weight: 750; margin-bottom: 6px; }
        .welcome-step-text { color: #8fb2ab; font-size: 12.5px; line-height: 1.55; }
        .welcome-trust { display:flex; flex-wrap:wrap; gap:22px; margin-top:8px; opacity:0; animation: riseIn .8s ease-out .78s forwards; }
        .welcome-trust-item { display:flex; flex-direction:column; gap:2px; }
        .welcome-trust-num { color:#eef7f4; font-size:24px; font-weight:850; }
        .welcome-trust-num .grad { background:linear-gradient(120deg,#5eeac0,#7c9cff); -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent; }
        .welcome-trust-label { color:#7fa39c; font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:.08em; }

        @keyframes riseIn { from { opacity:0; transform:translateY(16px); } to { opacity:1; transform:translateY(0); } }
        @keyframes gradShift { 0%,100% { background-position:0% 50%; } 50% { background-position:100% 50%; } }
        @keyframes haloPulse { 0%,100% { transform:translateX(-50%) scale(1); opacity:.85; } 50% { transform:translateX(-50%) scale(1.12); opacity:1; } }
        @keyframes livePulse { 0% { box-shadow:0 0 0 0 rgba(94,234,192,.55); } 70% { box-shadow:0 0 0 10px rgba(94,234,192,0); } 100% { box-shadow:0 0 0 0 rgba(94,234,192,0); } }
        @keyframes heroSheen { 0% { left:-40%; } 55%,100% { left:130%; } }
        @media (max-width: 720px) { .welcome-shell { margin-top: 18px; padding: 0 14px 32px 14px; } .welcome-steps { grid-template-columns: 1fr; } }
        @media (prefers-reduced-motion: reduce) { .welcome-shell::before, .upload-hero::after, .welcome-badge .dot, .welcome-title .grad { animation: none !important; } }

        /* ── Animations ──────────────────────────────────────────── */
        @keyframes fadeUp {
            from { opacity: 0; transform: translateY(8px); }
            to   { opacity: 1; transform: translateY(0); }
        }
        .flux-kpi-card, div[data-testid="stVerticalBlockBorderWrapper"] {
            animation: fadeUp .25s ease-out both;
        }

        /* ── Sidebar stats (legacy compat) ───────────────────────── */
        .sidebar-stat { background: #1a1a2e; border: 1px solid rgba(255,255,255,.07); border-radius: 10px; padding: 12px 14px; margin-bottom: 8px; }
        .sidebar-stat-label { color: #64748b; font-size: 11px; font-weight: 600; text-transform: uppercase; }
        .sidebar-stat-value { color: #f1f5f9; font-size: 22px; font-weight: 800; }
        .sidebar-kicker { color: #7c3aed; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .1em; }
        .control-title, .section-title { color: #7c3aed !important; font-size: 11px !important; font-weight: 700 !important; text-transform: uppercase !important; letter-spacing: .08em !important; }
        .control-subtitle, .mini-note { color: #475569 !important; font-size: 12px !important; }
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
    chart_card_title("Import")
    st.markdown(
        """
        <div class="upload-hero">
            <div class="upload-hero-title">Fichiers ASKit</div>
            <div class="upload-hero-text">
                CSV, GZ, XLS ou XLSX · demandes obligatoire
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    def validate_uploaded_file(uploaded_file) -> bool:
        """Validate uploaded file for security and compatibility."""
        # SECURITY: Check file size (50 MB limit)
        MAX_SIZE = 50 * 1024 * 1024
        if uploaded_file.size > MAX_SIZE:
            st.error(f"File {uploaded_file.name} too large: {uploaded_file.size / 1024 / 1024:.1f} MB (max 50 MB)")
            return False
        
        # SECURITY: Validate file extension
        allowed_extensions = {".csv", ".gz", ".xlsx", ".xls"}
        file_ext = Path(uploaded_file.name).suffix.lower()
        if file_ext not in allowed_extensions and not uploaded_file.name.endswith(".csv.gz"):
            st.error(f"Unsupported file type: {file_ext}. Allowed: CSV, GZ, XLSX, XLS")
            return False
        
        # SECURITY: Check for suspicious filenames
        if ".." in uploaded_file.name or "/" in uploaded_file.name:
            st.error(f"Invalid filename: {uploaded_file.name}")
            return False
        
        return True

    def detect_type_from_name(filename: str) -> str | None:
        name = filename.lower()
        if any(token in name for token in ["employ", "employe", "employes", "employés", "employee"]):
            return "employes"
        if any(token in name for token in ["enquete", "enquête", "satisfaction", "sst krm"]):
            return "satisfaction"
        if any(token in name for token in ["report request", "request enregistre", "request enregistré", "demand"]):
            return "demandes"
        return None

    uploaded_files = st.file_uploader(
        "Déposer les fichiers",
        type=["csv", "gz", "xlsx", "xls"],
        accept_multiple_files=True,
        key="askit_multi_upload",
    )

    with st.popover("📁 Chemins locaux (optionnel)"):
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
        st.info("Demandes ASKit requises")
        st.session_state.pop("dashboard_dataset", None)
        st.session_state.pop("dashboard_source_label", None)
        st.session_state.pop("dashboard_input_signature", None)
        return None, None

    previous_signature = st.session_state.get("dashboard_input_signature")
    if previous_signature != input_signature and not generate_clicked:
        st.session_state.pop("dashboard_dataset", None)
        st.session_state.pop("dashboard_source_label", None)
        st.session_state.pop("dashboard_input_signature", None)
        st.info("Nouveaux fichiers · cliquez sur Générer")
        return None, None

    if not generate_clicked and "dashboard_dataset" not in st.session_state:
        st.info("Fichier prêt · cliquez sur Générer")
        return None, None

    if not generate_clicked and "dashboard_dataset" in st.session_state:
        return st.session_state["dashboard_dataset"], st.session_state["dashboard_source_label"]

    tickets_raw = None
    satisfaction_raw = pd.DataFrame()
    employees_raw = pd.DataFrame()
    source_label = None

    for uploaded_file in uploaded_files or []:
        # SECURITY: Validate uploaded file before processing
        if not validate_uploaded_file(uploaded_file):
            continue
        
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
            # Fichier du même type déjà chargé — prendre les données quand même (surcharge)
            st.info(f"Fichier accepté · {uploaded_file.name}")
        else:
            # Type non reconnu — essayer de détecter manuellement par colonnes
            st.warning(
                f"Type non reconnu · {uploaded_file.name}"
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
        st.error("Fichier demandes ASKit introuvable")
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
        "N° ticket, date de creation",
        tickets_validation,
        "ticket et date de creation",
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
        st.info("Enquête ignorée · colonnes absentes")
        satisfaction_raw = pd.DataFrame()
    if employees_validation is not None and not employees_validation["ok"]:
        st.info("Employés ignoré · identifiant absent")
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
        st.success(f"Satisfaction · {len(responses)} réponses")
    else:
        st.warning("Satisfaction indisponible")
    st.success(f"Source · {source_label}")
    final_label = source_label
    st.session_state["dashboard_dataset"] = dataset
    st.session_state["dashboard_source_label"] = final_label
    st.session_state["dashboard_input_signature"] = input_signature
    return dataset, final_label


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    chart_card_title("Periode d'analyse")
    source_attrs = df.attrs.copy()
    min_date = df["date_ouverture"].min().date()
    max_date = df["date_ouverture"].max().date()

    col_f1, col_f2 = st.columns(2)

    with col_f1:
        selected_dates = st.date_input("Periode", value=(min_date, max_date), min_value=min_date, max_value=max_date)

    with col_f2:
        search_term = st.text_input("🔍 Recherche par mot-clé", value="", placeholder="Chercher ticket, demandeur, sujet...")

    filtered = df.copy()
    filtered.attrs = source_attrs.copy()
    if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
        start, end = pd.to_datetime(selected_dates[0]), pd.to_datetime(selected_dates[1])
        filtered = filtered[
            (filtered["date_ouverture"] >= start)
            & (filtered["date_ouverture"] < end + pd.Timedelta(days=1))
        ]
        filtered.attrs = source_attrs.copy()

    if search_term.strip():
        term = search_term.strip().lower()
        search_cols = [c for c in ["ticket_id", "beneficiaire", "sujet", "site", "groupe_traitant", "statut"] if c in filtered.columns]
        mask = pd.Series(False, index=filtered.index)
        for col in search_cols:
            mask |= filtered[col].astype(str).str.lower().str.contains(term, na=False)
        filtered = filtered[mask]
        filtered.attrs = source_attrs.copy()

    filter_configs = [
        ("Annees", "mois_ouverture"),
        ("Sites / localisations", "site"),
        ("Managers", "manager"),
        ("Groupes traitants", "groupe_traitant"),
        ("Etats tickets", "statut"),
    ]

    for idx, (label, column) in enumerate(filter_configs):
        target_col = col_f1 if idx % 2 == 0 else col_f2
        with target_col:
            options = sorted(filtered[column].dropna().astype(str).unique())
            if column == "mois_ouverture":
                years = sorted({option[:4] for option in options})
                selected_years = st.multiselect(label, years, default=[])
                if selected_years:
                    filtered = filtered[filtered[column].astype(str).str[:4].isin(selected_years)]
                    filtered.attrs = source_attrs.copy()
                continue
            selected = st.multiselect(label, options=options, default=[])
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
    ("Import", "import"),
    ("Dashboard", "dashboard"),
    ("Analytics", "analytics"),
    ("Satisfaction", "satisfaction"),
    ("Rapports", "reports"),
    ("API", "api"),
)


PAGE_TITLES = {
    "import": ("Import", "Sources ASKit"),
    "dashboard": ("Vue globale", "KPI et alertes"),
    "analytics": ("Analytics", "Comparaison mensuelle"),
    "satisfaction": ("Satisfaction", "Réponses ASKit"),
    "reports": ("Rapports", "PDF et Excel"),
    "api": ("API", "Endpoints REST"),
}


def sidebar_brand() -> None:
    """Flux-style sidebar brand block with logo and user card."""
    logo_uri = image_data_uri(LOGO_PATH)
    logo_img = f'<img src="{logo_uri}" alt="Sagemcom" style="height:20px;vertical-align:middle;margin-right:6px">' if logo_uri else ""
    st.markdown(
        f"""
        <div class="flux-sidebar-brand">
            <div class="flux-brand-logo">
                <div class="flux-brand-icon">S</div>
                <div class="flux-brand-name">Sagemcom RSI</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_nav_buttons() -> str:
    """Flux-style sidebar nav items rendered as stacked buttons."""
    if "active_page" not in st.session_state:
        st.session_state["active_page"] = "dashboard"

    NAV_ICONS = {
        "import": "📥",
        "dashboard": "📊",
        "analytics": "📈",
        "satisfaction": "⭐",
        "reports": "📄",
        "api": "🔌",
    }
    st.markdown('<div class="flux-nav-label">Menu</div>', unsafe_allow_html=True)
    for label, page_key in NAV_ITEMS:
        active = st.session_state["active_page"] == page_key
        icon = NAV_ICONS.get(page_key, "•")
        if st.button(
            icon,
            key=f"nav_{page_key}",
            type="primary" if active else "secondary",
            use_container_width=True,
            help=label,
        ):
            st.session_state["active_page"] = page_key
    return st.session_state["active_page"]





def page_header(page_key: str, mois: str) -> None:
    title, subtitle = PAGE_TITLES.get(page_key, PAGE_TITLES["dashboard"])
    st.markdown(
        f"""
        <div class="page-header">
            <div class="flux-hero-eyebrow">RSI Sagemcom — Support IT</div>
            <h1 style="color:#fff !important; font-size:24px !important; font-weight:800 !important; margin:4px 0 !important;">{title}</h1>
            <div class="page-subtitle">{subtitle}</div>
            <span class="month-pill">📅 {mois}</span>
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
                    Ouvrez Import pour charger vos sources.
                </div>
            </div>
            <div class="month-pill">Aucun input actif</div>
        </div>
        <div class="upload-hero">
            <div class="upload-hero-title">Aucune donnée</div>
            <div class="upload-hero-text">
                Demandes ASKit requises · satisfaction et employés optionnels
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


def kpi_card(label: str, value: str, icon: str, color: str, trend: str = "") -> None:
    trend_html = f'<div class="flux-kpi-trend flux-kpi-trend-up">↑ {trend}</div>' if trend else '<div class="flux-kpi-trend flux-kpi-trend-neutral">vs mois precedent</div>'
    st.markdown(
        f"""
        <div class="flux-kpi-card">
            <div class="flux-kpi-top">
                <div class="flux-kpi-label">{label}</div>
                <div class="flux-kpi-icon" style="background:{color}22; color:{color}; font-size:18px;">{icon}</div>
            </div>
            <div class="flux-kpi-value">{value}</div>
            {trend_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def chart_card_title(title: str, note: str = "") -> None:
    note_html = f'<div class="mini-note">{note}</div>' if note and len(note) < 52 else ""
    st.markdown(f'<div class="section-title">{title}</div>{note_html}', unsafe_allow_html=True)


def apply_plotly_theme(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=10, b=8),
        font=dict(family="Inter, Segoe UI, Roboto, Arial, sans-serif", size=13, color="#e2e8f0"),
        legend=dict(font=dict(size=12, color="#64748b"), title_font=dict(size=12, color="#64748b")),
        legend_title_text="",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(
            bgcolor="#1a1a2e",
            bordercolor="rgba(124,58,237,0.3)",
            font=dict(family="Inter, Segoe UI, Roboto, Arial, sans-serif", size=12, color="#e2e8f0"),
        ),
    )
    fig.update_xaxes(
        title_font=dict(size=12, color="#475569"),
        tickfont=dict(size=12, color="#475569"),
        gridcolor="rgba(255,255,255,0.05)",
        zerolinecolor="rgba(255,255,255,0.05)",
    )
    fig.update_yaxes(
        title_font=dict(size=12, color="#475569"),
        tickfont=dict(size=12, color="#475569"),
        gridcolor="rgba(255,255,255,0.05)",
        zerolinecolor="rgba(255,255,255,0.05)",
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


def top_horizontal_bar(
    df: pd.DataFrame,
    mois: str,
    column: str,
    label: str,
    top: int | None = None,
    height: int = 280,
) -> go.Figure:
    """Barre horizontale par dimension. Si top=None affiche tout."""
    data = kpi.distribution(df, mois, column, top=top)
    if data.empty:
        fig = go.Figure()
        fig.add_annotation(text="Donnée indisponible", showarrow=False, font=dict(color="#475569"))
        return apply_plotly_theme(fig, height)
    sorted_data = data.sort_values("nombre_tickets")
    dynamic_height = max(height, 28 * len(sorted_data) + 60)
    fig = px.bar(
        sorted_data,
        x="nombre_tickets",
        y=column,
        orientation="h",
        text="nombre_tickets",
        color_discrete_sequence=[COLORS["blue"]],
        labels={"nombre_tickets": "Tickets", column: label},
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(showlegend=False)
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(title=None)
    return apply_plotly_theme(fig, dynamic_height)



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
    # Jamais de colonne nominative (beneficiaire) — ID technique uniquement
    columns = ["ticket_id", "date_ouverture", "categorie", "statut", "site"]
    available = [c for c in columns if c in data.columns]
    table = data[available].copy()
    if "date_ouverture" in table.columns:
        table["date_ouverture"] = table["date_ouverture"].dt.strftime("%d/%m/%Y")
    return table.rename(
        columns={
            "ticket_id": "N ticket",
            "date_ouverture": "Date",
            "categorie": "Sujet",
            "statut": "Etat",
            "site": "Site",
        }
    )


def site_pole_heatmap(df: pd.DataFrame, mois: str) -> go.Figure:
    """Graphique croisé Site x Pôle (bar groupé)."""
    data = kpi.tickets_by_site_pole(df, mois)
    if data.empty:
        fig = go.Figure()
        fig.add_annotation(text="Donnée indisponible", showarrow=False, font=dict(color="#475569"))
        return apply_plotly_theme(fig, 280)
    fig = px.bar(
        data,
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


def top_horizontal_bar(
    df: pd.DataFrame,
    mois: str,
    column: str,
    label: str,
    top: int | None = None,
    height: int = 280,
) -> go.Figure:
    """Barre horizontale par dimension. Si top=None affiche tout."""
    data = kpi.distribution(df, mois, column, top=top)
    if data.empty:
        fig = go.Figure()
        fig.add_annotation(text="Donnée indisponible", showarrow=False, font=dict(color="#475569"))
        return apply_plotly_theme(fig, height)
    sorted_data = data.sort_values("nombre_tickets")
    dynamic_height = max(height, 28 * len(sorted_data) + 60)
    fig = px.bar(
        sorted_data,
        x="nombre_tickets",
        y=column,
        orientation="h",
        text="nombre_tickets",
        color_discrete_sequence=[COLORS["blue"]],
        labels={"nombre_tickets": "Tickets", column: label},
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(showlegend=False)
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(title=None)
    return apply_plotly_theme(fig, dynamic_height)



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
    # Jamais de colonne nominative (beneficiaire) — ID technique uniquement
    columns = ["ticket_id", "date_ouverture", "categorie", "statut", "site"]
    available = [c for c in columns if c in data.columns]
    table = data[available].copy()
    if "date_ouverture" in table.columns:
        table["date_ouverture"] = table["date_ouverture"].dt.strftime("%d/%m/%Y")
    return table.rename(
        columns={
            "ticket_id": "N ticket",
            "date_ouverture": "Date",
            "categorie": "Sujet",
            "statut": "Etat",
            "site": "Site",
        }
    )


def site_pole_heatmap(df: pd.DataFrame, mois: str) -> go.Figure:
    """Graphique croisé Site x Pôle (bar groupé)."""
    data = kpi.tickets_by_site_pole(df, mois)
    if data.empty:
        fig = go.Figure()
        fig.add_annotation(text="Donnée indisponible", showarrow=False, font=dict(color="#475569"))
        return apply_plotly_theme(fig, 280)
    fig = px.bar(
        data,
        x="site",
        y="nombre_tickets",
        color="pole",
        barmode="group",
        text="nombre_tickets",
        color_discrete_sequence=PALETTE,
        labels={"site": "Site", "nombre_tickets": "Tickets ouverts", "pole": "Pôle"},
    )
    fig.update_traces(textposition="outside", textfont_size=11)
    fig.update_layout(legend_title_text="Pôle")
    fig.update_xaxes(showgrid=False)
    return apply_plotly_theme(fig, 280)


def rubrique_bar(detail: "kpi.RubriqueDetail | None", label: str) -> go.Figure:
    """Mini-bar horizontale montrant la distribution par niveau pour une rubrique."""
    categories = [
        "Très insatisfait", "Plutôt insatisfait",
        "Insatisfait", "Satisfait", "Très satisfait",
    ]
    colors_map = {
        "Très insatisfait": "#ef4444",
        "Plutôt insatisfait": "#f97316",
        "Insatisfait": "#eab308",
        "Satisfait": "#22c55e",
        "Très satisfait": "#10b981",
    }
    if detail is None:
        counts = [0] * 5
    else:
        counts = [
            detail.tres_insatisfait,
            detail.plutot_insatisfait,
            detail.insatisfait,
            detail.satisfait,
            detail.tres_satisfait,
        ]
    fig = go.Figure()
    for cat, cnt, color in zip(categories, counts, colors_map.values()):
        fig.add_trace(go.Bar(
            name=cat,
            x=[cnt],
            y=[label],
            orientation="h",
            marker_color=color,
            text=[cnt] if cnt > 0 else [""],
            textposition="inside",
            insidetextanchor="middle",
        ))
    fig.update_layout(
        barmode="stack",
        showlegend=False,
        margin=dict(l=0, r=0, t=4, b=4),
    )
    return apply_plotly_theme(fig, 56)


def _month_excel_label(mois: str) -> str:
    month_names = {
        "01": "janv", "02": "févr", "03": "mars", "04": "avr",
        "05": "mai", "06": "juin", "07": "juil", "08": "août",
        "09": "sept", "10": "oct", "11": "nov", "12": "déc",
    }
    try:
        year, month = mois.split("-")
        return f"{month_names.get(month, month)}-{year[-2:]}"
    except ValueError:
        return mois


def official_site_pole_table_html(df: pd.DataFrame, mois: str) -> str:
    data = kpi.tickets_by_site_pole(df, mois)
    rows = []
    for label, site, pole in OFFICIAL_SITE_POLES:
        if data.empty:
            value = 0
        else:
            matched = data[
                data["site"].astype(str).str.casefold().eq(site.casefold())
                & data["pole"].astype(str).str.casefold().eq(pole.casefold())
            ]
            value = int(matched["nombre_tickets"].sum()) if not matched.empty else 0
        rows.append((label, value))

    body = "".join(
        f"<tr><th style='border:1px solid #000;padding:2px 10px;text-align:center;font-weight:700;background:#fff;color:#000;'>{html.escape(label)}</th><td style='border:1px solid #000;padding:2px 10px;text-align:center;background:#fff;color:#000;'>{value}</td></tr>"
        for label, value in rows
    )
    return f"""
    <table class="official-tdb-table" style="width:100%;border-collapse:collapse;margin:6px 0 14px 0;background:#fff;color:#000;font-family:Calibri,Arial,sans-serif;font-size:15px;">
        <thead><tr><th style="border:1px solid #000;padding:4px 10px;background:#fff;color:#000;"></th><th style="border:1px solid #000;padding:4px 10px;text-align:center;font-weight:700;background:#fff;color:#000;">{html.escape(_month_excel_label(mois))}</th></tr></thead>
        <tbody>{body}</tbody>
    </table>
    """


def echarts_kpi_bar(total_ouverts: int, ouverts_fermes: int, total_fermes: int, height: str = "280px") -> None:
    """ECharts 3-bar KPI chart matching TDB 'demandes de services'."""
    options = {
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "shadow"},
            "backgroundColor": "rgba(22, 22, 31, 0.95)",
            "borderColor": "rgba(124, 58, 237, 0.3)",
            "textStyle": {"color": "#e2e8f0"}
        },
        "grid": {"top": "15%", "bottom": "18%", "left": "4%", "right": "4%", "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": ["Demandes ouvertes\nsur le mois", "Demandes ouvertes et\ntraitées sur le mois", "Demandes globales\ntraitées sur le mois"],
            "axisLabel": {"interval": 0, "color": "#94a3b8", "fontSize": 10},
            "axisLine": {"lineStyle": {"color": "rgba(255,255,255,0.1)"}}
        },
        "yAxis": {
            "type": "value",
            "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.06)"}},
            "axisLabel": {"color": "#94a3b8"}
        },
        "series": [
            {
                "type": "bar",
                "barWidth": "42%",
                "data": [
                    {"value": total_ouverts, "itemStyle": {"color": "#4472C4", "borderRadius": [5, 5, 0, 0]}},
                    {"value": ouverts_fermes, "itemStyle": {"color": "#ED7D31", "borderRadius": [5, 5, 0, 0]}},
                    {"value": total_fermes, "itemStyle": {"color": "#A5A5A5", "borderRadius": [5, 5, 0, 0]}},
                ],
                "label": {
                    "show": True,
                    "position": "top",
                    "color": "#f8fafc",
                    "fontWeight": "bold",
                    "fontSize": 13
                }
            }
        ]
    }
    st_echarts(options=options, height=height, theme="dark")


def echarts_site_pie(df_site: pd.DataFrame, height: str = "280px") -> None:
    """ECharts doughnut chart for site distribution."""
    if df_site.empty:
        st.info("Donnée indisponible")
        return
    data = [{"name": row["site"].replace("Tunisie/", ""), "value": int(row["nombre_tickets"])} for _, row in df_site.iterrows()]
    options = {
        "title": {
            "text": "demandes de services par site",
            "left": "center",
            "top": "0%",
            "textStyle": {"color": "#e2e8f0", "fontSize": 13, "fontWeight": "bold"}
        },
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
        "legend": {
            "bottom": "0%",
            "textStyle": {"color": "#94a3b8", "fontSize": 11}
        },
        "color": ["#4472C4", "#ED7D31", "#A5A5A5", "#FFC000", "#5B9BD5"],
        "series": [
            {
                "name": "Site",
                "type": "pie",
                "radius": ["38%", "68%"],
                "center": ["50%", "48%"],
                "avoidLabelOverlap": True,
                "itemStyle": {"borderRadius": 5, "borderColor": "#16161f", "borderWidth": 2},
                "label": {"show": True, "formatter": "{b}\n{d}%", "color": "#e2e8f0", "fontSize": 10},
                "emphasis": {
                    "label": {"show": True, "fontSize": 12, "fontWeight": "bold"},
                    "itemStyle": {"shadowBlur": 10, "shadowOffsetX": 0, "shadowColor": "rgba(0, 0, 0, 0.5)"}
                },
                "data": data
            }
        ]
    }
    st_echarts(options=options, height=height, theme="dark")


def echarts_pole_pie(site_data: pd.DataFrame, title: str, height: str = "240px") -> None:
    """ECharts mini-pie chart for per-site pôle distribution."""
    if site_data.empty:
        return
    data = [{"name": row["pole"], "value": int(row["nombre_tickets"])} for _, row in site_data.iterrows()]
    options = {
        "title": {
            "text": title,
            "left": "center",
            "top": "2%",
            "textStyle": {"color": "#e2e8f0", "fontSize": 11, "fontWeight": "bold"}
        },
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
        "legend": {
            "bottom": "0%",
            "textStyle": {"color": "#94a3b8", "fontSize": 9},
            "itemWidth": 10,
            "itemHeight": 8
        },
        "color": ["#4472C4", "#ED7D31", "#A5A5A5", "#FFC000", "#5B9BD5", "#70AD47"],
        "series": [
            {
                "type": "pie",
                "radius": ["32%", "62%"],
                "center": ["50%", "45%"],
                "itemStyle": {"borderRadius": 4, "borderColor": "#16161f", "borderWidth": 1},
                "label": {"show": True, "formatter": "{c}", "fontSize": 9, "color": "#cbd5e1"},
                "data": data
            }
        ]
    }
    st_echarts(options=options, height=height, theme="dark")


def echarts_subjects_bar(df_sujets: pd.DataFrame, mois: str, height: str = "380px") -> None:
    """ECharts vertical bar chart with dynamic dataZoom slider."""
    if df_sujets.empty:
        st.info("Donnée indisponible")
        return
    sorted_df = df_sujets.sort_values("nombre_tickets", ascending=False)
    categories = sorted_df["categorie"].tolist()
    values = sorted_df["nombre_tickets"].tolist()
    end_pct = min(100, max(25, int(12 / max(len(categories), 1) * 100)))
    options = {
        "title": {
            "text": f"type des demandes ouvertes dans le mois de {mois}",
            "left": "center",
            "top": "1%",
            "textStyle": {"color": "#e2e8f0", "fontSize": 12}
        },
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "toolbox": {
            "feature": {"dataView": {"readOnly": True}, "saveAsImage": {}},
            "iconStyle": {"borderColor": "#94a3b8"}
        },
        "dataZoom": [
            {"type": "inside", "start": 0, "end": 100},
            {"type": "slider", "start": 0, "end": end_pct, "height": 18, "bottom": "0%", "borderColor": "rgba(255,255,255,0.1)", "fillerColor": "rgba(68,114,196,0.25)"}
        ],
        "grid": {"left": "3%", "right": "3%", "bottom": "18%", "top": "14%", "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": categories,
            "axisLabel": {"interval": 0, "rotate": 45, "color": "#94a3b8", "fontSize": 9}
        },
        "yAxis": {
            "type": "value",
            "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.06)"}},
            "axisLabel": {"color": "#94a3b8"}
        },
        "series": [
            {
                "type": "bar",
                "data": values,
                "itemStyle": {"color": "#4472C4", "borderRadius": [4, 4, 0, 0]},
                "label": {"show": True, "position": "top", "color": "#cbd5e1", "fontSize": 9}
            }
        ]
    }
    st_echarts(options=options, height=height, theme="dark")


def echarts_satisfaction_grouped_bar(tdb_df: pd.DataFrame, mois: str, height: str = "360px") -> None:
    """ECharts grouped bar chart matching official satisfaction report."""
    rubriques = ["Satisfaction de traitement", "Communication des opérateurs", "Satisfaction du temps de traitement"]
    categories = ["très insatisfait", "Plutôt insatisfait", "insatisfait", "Satisfait", "très satisfait"]
    colors = ["#C00000", "#ED7D31", "#FFC000", "#92D050", "#00B050"]
    series = []
    for cat, col in zip(categories, colors):
        vals = [int(tdb_df.loc[r, cat]) if r in tdb_df.index and cat in tdb_df.columns else 0 for r in rubriques]
        series.append({
            "name": cat,
            "type": "bar",
            "data": vals,
            "itemStyle": {"color": col, "borderRadius": [3, 3, 0, 0]},
            "label": {"show": True, "position": "top", "color": "#e2e8f0", "fontSize": 8}
        })
    options = {
        "title": {
            "text": f"satisfaction de traitement — {mois}",
            "left": "center",
            "top": "2%",
            "textStyle": {"color": "#e2e8f0", "fontSize": 12}
        },
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "legend": {"bottom": "0%", "data": categories, "textStyle": {"color": "#94a3b8", "fontSize": 9}},
        "grid": {"left": "3%", "right": "3%", "bottom": "16%", "top": "15%", "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": ["Satisfaction\ntraitement", "Communication\nopérateurs", "Temps de\ntraitement"],
            "axisLabel": {"color": "#cbd5e1", "fontSize": 10}
        },
        "yAxis": {
            "type": "value",
            "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.06)"}},
            "axisLabel": {"color": "#94a3b8"}
        },
        "series": series
    }
    st_echarts(options=options, height=height, theme="dark")


def echarts_satisfaction_donut(sat_pct: float, height: str = "280px") -> None:
    """ECharts satisfaction ring chart."""
    insat = max(0.0, 100.0 - sat_pct)
    options = {
        "title": {
            "text": f"{sat_pct:.2f}%",
            "subtext": "Satisfaction",
            "left": "center",
            "top": "36%",
            "textStyle": {"color": "#00B050", "fontSize": 22, "fontWeight": "bold"},
            "subtextStyle": {"color": "#94a3b8", "fontSize": 11}
        },
        "tooltip": {"trigger": "item", "formatter": "{b}: {c}%"},
        "legend": {"bottom": "0%", "textStyle": {"color": "#94a3b8", "fontSize": 10}},
        "series": [
            {
                "type": "pie",
                "radius": ["55%", "75%"],
                "center": ["50%", "48%"],
                "avoidLabelOverlap": False,
                "label": {"show": False},
                "data": [
                    {"value": round(sat_pct, 2), "name": "Satisfait / Très satisfait", "itemStyle": {"color": "#00B050", "borderRadius": 6}},
                    {"value": round(insat, 2), "name": "Insatisfait / Autres", "itemStyle": {"color": "#C00000", "borderRadius": 6}},
                ]
            }
        ]
    }
    st_echarts(options=options, height=height, theme="dark")


def echarts_rubriques_stacked(sat: kpi.SatisfactionResult, height: str = "280px") -> None:
    """ECharts horizontal stacked bar chart for satisfaction rubriques."""
    rubriques = ["Satisfaction traitement", "Communication opérateurs", "Temps traitement"]
    details = [sat.detail_traitement, sat.detail_communication, sat.detail_temps]
    categories = ["très insatisfait", "Plutôt insatisfait", "insatisfait", "Satisfait", "très satisfait"]
    colors = ["#C00000", "#ED7D31", "#FFC000", "#92D050", "#00B050"]
    attrs = ["tres_insatisfait", "plutot_insatisfait", "insatisfait", "satisfait", "tres_satisfait"]
    series = []
    for cat, col, attr in zip(categories, colors, attrs):
        vals = [getattr(d, attr, 0) if d else 0 for d in details]
        series.append({
            "name": cat,
            "type": "bar",
            "stack": "total",
            "itemStyle": {"color": col},
            "label": {"show": True, "fontSize": 9},
            "emphasis": {"focus": "series"},
            "data": vals
        })
    options = {
        "title": {"text": "Répartition par rubrique", "left": "center", "top": "2%", "textStyle": {"color": "#e2e8f0", "fontSize": 11}},
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "legend": {"bottom": "0%", "data": categories, "textStyle": {"color": "#94a3b8", "fontSize": 9}},
        "grid": {"left": "3%", "right": "4%", "bottom": "15%", "top": "15%", "containLabel": True},
        "xAxis": {"type": "value", "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.06)"}}, "axisLabel": {"color": "#94a3b8"}},
        "yAxis": {"type": "category", "data": rubriques, "axisLabel": {"color": "#cbd5e1", "fontSize": 10}},
        "series": series
    }
    st_echarts(options=options, height=height, theme="dark")


def show_dashboard(df: pd.DataFrame, mois: str, source_label: str) -> None:
    result = kpi.calculate_month_kpi(df, mois)
    sat = result.satisfaction
    source_class = "source-ok" if "Import" in source_label or "Chemin" in source_label or "officielles" in source_label else "source-warn"

    st.markdown(
        f'<div class="{source_class}">Source : {source_label}</div>',
        unsafe_allow_html=True,
    )
    show_alerts(df, mois)
    show_smart_insights(df, mois)

    # ══════════════════════════════════════════════════════════════════
    # ROW 1 — KPI Metrics Cards (Style ECharts Showcase)
    # ══════════════════════════════════════════════════════════════════
    kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
    with kpi_col1:
        st.metric(
            "Demandes ouvertes",
            f"{result.total_ouverts:,}",
        )
    with kpi_col2:
        val_fermes = f"{result.total_fermes:,}" if result.total_fermes is not None else "N/A"
        st.metric(
            "Globales traitées",
            val_fermes,
        )
    with kpi_col3:
        st.metric(
            "Délai moyen",
            _format_delay(result.delai_moyen_minutes),
        )
    with kpi_col4:
        sat_str = f"{sat.satisfaction_globale:.1f} %" if sat.satisfaction_globale is not None else "N/A"
        st.metric(
            "Satisfaction globale",
            sat_str,
        )

    # ══════════════════════════════════════════════════════════════════
    # SECTION 1 — Demandes de services (Tableau + ECharts 3D Bar)
    # ══════════════════════════════════════════════════════════════════
    st.subheader(":material/trending_up: Demandes de services")
    st.caption(f"Mois : {mois}")
    with st.container(border=True):
        kpi_data = {
            "Indicateur": [
                "Nbr des demandes ouvertes sur le mois",
                "Nbr des demandes ouvertes et traitées sur le mois",
                "Nbr des demandes globales Traitées sur le mois",
                "Délai moyen de traitement des tickets",
            ],
            "Valeur": [
                str(result.total_ouverts),
                str(result.ouverts_et_fermes_meme_mois) if result.ouverts_et_fermes_meme_mois is not None else "N/A",
                str(result.total_fermes) if result.total_fermes is not None else "N/A",
                _format_delay(result.delai_moyen_minutes),
            ],
        }
        s1_left, s1_right = st.columns([1.1, 1.5])
        with s1_left:
            st.dataframe(
                pd.DataFrame(kpi_data),
                use_container_width=True,
                hide_index=True,
            )
        with s1_right:
            echarts_kpi_bar(
                result.total_ouverts,
                result.ouverts_et_fermes_meme_mois or 0,
                result.total_fermes or 0,
                height="280px"
            )

    # ══════════════════════════════════════════════════════════════════
    # SECTION 2 — Répartition Site & Pôle (Tableau officiel + ECharts)
    # ══════════════════════════════════════════════════════════════════
    st.subheader(":material/pie_chart: Répartition par site et pôle")
    st.caption("Ouvertures par site")
    with st.container(border=True):
        df_site = kpi.tickets_by_site(df, mois)
        df_sp = kpi.tickets_by_site_pole(df, mois)

        s2_tbl, s2_pie = st.columns([1.1, 1.5])
        with s2_tbl:
            if not df_site.empty:
                st.dataframe(
                    df_site.rename(columns={"site": "Site", "nombre_tickets": "Tickets ouverts"}),
                    use_container_width=True,
                    hide_index=True,
                )
            st.markdown(official_site_pole_table_html(df, mois), unsafe_allow_html=True)

        with s2_pie:
            echarts_site_pie(df_site, height="300px")

        if not df_sp.empty:
            sites = df_site["site"].tolist() if not df_site.empty else df_sp["site"].unique().tolist()
            cols_poles = st.columns(min(len(sites), 3))
            for i, site_name in enumerate(sites[:3]):
                site_data = df_sp[df_sp["site"].eq(site_name)]
                if site_data.empty:
                    continue
                with cols_poles[i]:
                    short_name = site_name.replace("Tunisie/", "")
                    echarts_pole_pie(site_data, f"{short_name} répartition par pole", height="240px")

    # ══════════════════════════════════════════════════════════════════
    # SECTION 3 — Types de demandes ouvertes (Tableau + ECharts Zoom)
    # ══════════════════════════════════════════════════════════════════
    st.subheader(":material/category: Types des demandes ouvertes")
    st.caption(f"Sujets · {mois}")
    with st.container(border=True):
        df_sujets = kpi.subjects_opened_month(df, mois)
        s3a, s3b = st.columns([1, 1.8])
        with s3a:
            if not df_sujets.empty:
                st.dataframe(
                    df_sujets.rename(columns={"categorie": "Sujet", "nombre_tickets": "Tickets"}),
                    use_container_width=True,
                    hide_index=True,
                    height=min(480, 28 * len(df_sujets) + 40),
                )
        with s3b:
            echarts_subjects_bar(df_sujets, mois, height="450px")

    # ══════════════════════════════════════════════════════════════════
    # SECTION 4 — Satisfaction (Tableau 3x5 + ECharts Grouped Bar + Donut)
    # ══════════════════════════════════════════════════════════════════
    st.subheader(":material/sentiment_satisfied: Enquête de satisfaction ASKit")
    st.caption("Notes 1–5 · taux ≥ 4")
    with st.container(border=True):
        if sat.fallback_global:
            st.warning("Mode fallback : aucune date d'enquête pour le mois — données globales utilisées.")

        def _d(detail):
            if detail is None:
                return {"très insatisfait": 0, "Plutôt insatisfait": 0, "insatisfait": 0, "Satisfait": 0, "très satisfait": 0}
            return {
                "très insatisfait": detail.tres_insatisfait,
                "Plutôt insatisfait": detail.plutot_insatisfait,
                "insatisfait": detail.insatisfait,
                "Satisfait": detail.satisfait,
                "très satisfait": detail.tres_satisfait,
            }

        tdb_rows = [
            {"Rubrique": "Satisfaction de traitement",           **_d(sat.detail_traitement)},
            {"Rubrique": "Communication des opérateurs",          **_d(sat.detail_communication)},
            {"Rubrique": "Satisfaction du temps de traitement",   **_d(sat.detail_temps)},
        ]
        tdb_df = pd.DataFrame(tdb_rows).set_index("Rubrique")
        total_all = tdb_df.values.sum()
        if total_all > 0:
            taux_row = {col: f"{tdb_df[col].sum() / total_all * 100:.2f}%" for col in tdb_df.columns}
        else:
            taux_row = {col: "N/A" for col in tdb_df.columns}
        taux_df = pd.DataFrame([taux_row], index=["taux de satisfaction"])

        s4_left, s4_right = st.columns([1.1, 1.5])
        with s4_left:
            st.dataframe(tdb_df, use_container_width=True)
            st.dataframe(taux_df, use_container_width=True)
        with s4_right:
            echarts_satisfaction_grouped_bar(tdb_df, mois, height="340px")

        st.markdown("---")
        ms1, ms2, ms3 = st.columns(3)
        ms1.metric(
            "Demandes globales traitées",
            str(result.total_fermes) if result.total_fermes is not None else "N/A",
        )
        ms2.metric("Participants à l'enquête", str(sat.nombre_reponses))
        ms3.metric(
            "Taux de participation",
            f"{sat.taux_participation:.2f} %" if sat.taux_participation is not None else "N/A",
        )

        st.markdown("---")
        sd1, sd2 = st.columns([1, 1.5])
        with sd1:
            sat_pct = sat.satisfaction_globale if sat.satisfaction_globale is not None else 0.0
            echarts_satisfaction_donut(sat_pct, height="280px")
        with sd2:
            echarts_rubriques_stacked(sat, height="280px")

        st.markdown("---")
        chart_card_title("Les rubriques les moins satisfaisantes")
        if sat.rubrique_moins_satisfaisante:
            st.markdown(
                f'<div style="background:#FFC7CE;color:#9C0006;padding:12px 16px;border-radius:8px;'
                f'font-weight:700;font-size:14px;margin-bottom:8px">'
                f'⚠️ Rubrique la moins satisfaisante : {sat.rubrique_moins_satisfaisante}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.success("Toutes les rubriques sont à 100% de satisfaction.")

        insatisf_data = []
        for label, detail in [
            ("Satisfaction de traitement", sat.detail_traitement),
            ("Communication de l'opérateur", sat.detail_communication),
            ("temps de résolution", sat.detail_temps),
        ]:
            if detail:
                insatisf_data.append({
                    "Rubrique": label,
                    "très insatisfait": detail.tres_insatisfait,
                    "plutôt insatisfait": detail.plutot_insatisfait,
                    "insatisfait": detail.insatisfait,
                })
            else:
                insatisf_data.append({
                    "Rubrique": label,
                    "très insatisfait": 0,
                    "plutôt insatisfait": 0,
                    "insatisfait": 0,
                })
        if insatisf_data:
            st.dataframe(
                pd.DataFrame(insatisf_data).set_index("Rubrique"),
                use_container_width=True,
            )



def _format_delay(minutes: float | None) -> str:
    """Formate le délai en 'Xj Yh Zmin' comme dans le TDB officiel."""
    if minutes is None:
        return "N/A"
    h = int(minutes // 60)
    m = int(minutes % 60)
    j = h // 24
    hh = h % 24
    if j > 0:
        return f"{j}j {hh:02d}h{m:02d}min"
    return f"{h:02d}h{m:02d}min"


def show_comparison(df: pd.DataFrame, months: list[str], default_month: str) -> None:
    col_a, col_b = st.columns(2)
    month_a = col_a.selectbox("Mois A", options=months, index=max(0, len(months) - 2), key="compare_a")
    month_b = col_b.selectbox("Mois B", options=months, index=months.index(default_month), key="compare_b")

    left  = kpi.calculate_month_kpi(df, month_a).as_dict()
    right = kpi.calculate_month_kpi(df, month_b).as_dict()

    METRICS = [
        ("total_ouverts",              "Demandes ouvertes",          ""),
        ("total_fermes",               "Global traitées",            ""),
        ("ouverts_et_fermes_meme_mois","Ouvertes ET fermées même mois",""),
        ("delai_moyen_heures",         "Délai moyen",                " h"),
        ("satisfaction_moyenne",       "Satisfaction globale",       " %"),
        ("taux_participation",         "Taux de participation",      " %"),
    ]

    rows = []
    for key, label, suffix in METRICS:
        old = left.get(key)
        new = right.get(key)
        try:
            old_f = float(old) if old is not None else None
            new_f = float(new) if new is not None else None
        except (TypeError, ValueError):
            old_f = new_f = None

        if old_f in (None, 0) or new_f is None:
            delta_str = "—"
        else:
            delta = (new_f - old_f) / old_f * 100
            delta_str = f"{delta:+.1f}%"

        def _disp(v, s):
            if v is None:
                return "Donnée indisponible"
            try:
                if pd.isna(v):
                    return "Donnée indisponible"
            except TypeError:
                pass
            if isinstance(v, float):
                return f"{v:.2f}{s}"
            return f"{v}{s}"

        rows.append({
            "Indicateur": label,
            month_a: _disp(old, suffix),
            month_b: _disp(new, suffix),
            "Variation": delta_str,
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)



def show_exports(df: pd.DataFrame, mois: str) -> None:
    config = load_config()
    exports_dir = resolve_path(config.data.exports_dir) or Path("data/exports")
    with st.container(border=True):
        chart_card_title("Rapports mensuels", "Exports filtrés")
        col1, col2 = st.columns(2)
        if col1.button("Exporter le rapport PDF", use_container_width=True):
            path = export_month_pdf(df, mois, exports_dir, config.company_name)
            st.success(f"PDF genere: {path}")
        if col2.button("Exporter le rapport Excel", use_container_width=True):
            path = export_month_excel(df, mois, exports_dir)
            st.success(f"Excel genere: {path}")


def show_satisfaction_audit(df: pd.DataFrame, mois: str, sat: kpi.SatisfactionResult) -> None:
    """Tableau de preuve de calcul — formules traçables, aucune valeur inventée."""
    responses = df.attrs.get("satisfaction_responses")
    global_traites = kpi.calculate_month_kpi(df, mois).total_fermes or len(kpi.filter_opened_month(df, mois))

    with st.container(border=True):
        chart_card_title(
            "Audit du calcul satisfaction",
            "Preuve de calcul depuis les colonnes réelles du fichier enquête",
        )

        if responses is None or responses.empty:
            st.warning("Aucun fichier enquête satisfaction chargé : aucune note n'est inventée.")
            return

        if "mois_enquete" in responses.columns and responses["mois_enquete"].notna().any():
            scoped = responses[responses["mois_enquete"].eq(mois)].copy()
            scope_label = f"réponses du mois {mois}"
            if scoped.empty:
                scoped = responses.copy()
                scope_label = "fallback global : aucune réponse datée pour le mois"
        else:
            scoped = responses.copy()
            scope_label = "fallback global : date enquête absente ou inexploitable"

        required = ["satisfaction_traitement", "communication_operateurs", "satisfaction_temps"]
        valid_responses = scoped[required].apply(pd.to_numeric, errors="coerce").dropna(how="all")
        nb = len(valid_responses)
        sources = df.attrs.get("column_sources", {}).get("satisfaction", {})

        # Calcul du taux combiné pour la preuve
        toutes_notes = pd.concat([
            valid_responses["satisfaction_traitement"].dropna(),
            valid_responses["communication_operateurs"].dropna(),
            valid_responses["satisfaction_temps"].dropna(),
        ])
        n_total = len(toutes_notes)
        n_positifs = int((toutes_notes.round().isin([4, 5])).sum())

        rows = [
            {
                "KPI": "Satisfaction globale",
                "Colonne source": "3 rubriques combinées",
                "Formule": f"(note≥4) combinées : {n_positifs} / {n_total}",
                "Valeur": f"{sat.satisfaction_globale:.2f} %" if sat.satisfaction_globale is not None else "N/A",
            },
            {
                "KPI": "Satisfaction traitement",
                "Colonne source": sources.get("satisfaction_traitement", "satisfaction_traitement"),
                "Formule": f"(note≥4) : {sat.detail_traitement.satisfait + sat.detail_traitement.tres_satisfait if sat.detail_traitement else 0} / {nb}",
                "Valeur": f"{sat.detail_traitement.taux_satisfaction:.2f} %" if sat.detail_traitement and sat.detail_traitement.taux_satisfaction is not None else "N/A",
            },
            {
                "KPI": "Communication",
                "Colonne source": sources.get("communication_operateurs", "communication_operateurs"),
                "Formule": f"(note≥4) : {sat.detail_communication.satisfait + sat.detail_communication.tres_satisfait if sat.detail_communication else 0} / {nb}",
                "Valeur": f"{sat.detail_communication.taux_satisfaction:.2f} %" if sat.detail_communication and sat.detail_communication.taux_satisfaction is not None else "N/A",
            },
            {
                "KPI": "Temps de traitement",
                "Colonne source": sources.get("satisfaction_temps", "satisfaction_temps"),
                "Formule": f"(note≥4) : {sat.detail_temps.satisfait + sat.detail_temps.tres_satisfait if sat.detail_temps else 0} / {nb}",
                "Valeur": f"{sat.detail_temps.taux_satisfaction:.2f} %" if sat.detail_temps and sat.detail_temps.taux_satisfaction is not None else "N/A",
            },
            {
                "KPI": "Taux de participation",
                "Colonne source": "N réponses / global traitées",
                "Formule": f"{nb} / {global_traites} * 100",
                "Valeur": f"{sat.taux_participation:.2f} %" if sat.taux_participation is not None else "N/A",
            },
        ]
        st.caption(f"Périmètre : {scope_label}. Réponses exploitées : {nb}.")
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        if sat.rubrique_moins_satisfaisante:
            st.caption(f"Rubrique la moins satisfaisante (taux individuel min) : {sat.rubrique_moins_satisfaisante}.")


def show_satisfaction_page(df: pd.DataFrame, mois: str) -> None:
    result = kpi.calculate_month_kpi(df, mois)
    sat = result.satisfaction

    # ── KPI summary ──────────────────────────────────────
    with st.container(border=True):
        chart_card_title(
            "Satisfaction enquête ASKit",
            "Taux = (notes 4+5) / total réponses × 100  —  Source : fichier enquête importé",
        )
        if sat.fallback_global:
            st.warning("Mode fallback : aucune date enquête exploitable pour le mois sélectionné.")

        km1, km2, km3, km4 = st.columns(4)
        km1.metric(
            "Satisfaction globale",
            f"{sat.satisfaction_globale:.2f} %" if sat.satisfaction_globale is not None else "N/A",
            help="(satisfait + très satisfait) / total réponses combinées",
        )
        km2.metric(
            "Taux de participation",
            f"{sat.taux_participation:.2f} %" if sat.taux_participation is not None else "N/A",
            help="nb répondants / global traitées × 100",
        )
        km3.metric("Répondants", str(sat.nombre_reponses))
        km4.metric(
            "Global traitées",
            str(result.total_fermes) if result.total_fermes is not None else "N/A",
            help="Tickets fermés dans le mois (dénominateur de la participation)",
        )

        if sat.rubrique_moins_satisfaisante:
            st.markdown(
                f'<div class="alert-orange">⚠️ Rubrique la moins satisfaisante : '
                f'<strong>{sat.rubrique_moins_satisfaisante}</strong></div>',
                unsafe_allow_html=True,
            )

    # ── Détail par rubrique (barres empilées) ────────────────
    with st.container(border=True):
        chart_card_title(
            "Distribution par niveau — 3 rubriques",
            "🟥 Très insatisfait  🟧 Plutôt insatisfait  🟨 Insatisfait  🟩 Satisfait  🟩→ Très satisfait",
        )
        for rubrique_label, detail, taux_attr in [
            ("Satisfaction de traitement", sat.detail_traitement, sat.detail_traitement.taux_satisfaction if sat.detail_traitement else None),
            ("Communication des opérateurs", sat.detail_communication, sat.detail_communication.taux_satisfaction if sat.detail_communication else None),
            ("Satisfaction du temps de traitement", sat.detail_temps, sat.detail_temps.taux_satisfaction if sat.detail_temps else None),
        ]:
            taux_str = f"{taux_attr:.1f} %" if taux_attr is not None else "N/A"
            col_lbl, col_bar = st.columns([1, 3])
            col_lbl.markdown(
                f'<div style="color:#e2e8f0;font-size:13px;font-weight:600;padding-top:16px">{rubrique_label}</div>'
                f'<div style="color:#34d399;font-size:20px;font-weight:800">{taux_str}</div>',
                unsafe_allow_html=True,
            )
            col_bar.plotly_chart(
                rubrique_bar(detail, rubrique_label),
                use_container_width=True,
            )

        # Légende
        st.markdown(
            "<div style='display:flex;gap:16px;margin-top:4px;font-size:11px;color:#64748b'>"
            "<span>🟥 Très insatisfait</span>"
            "<span>🟧 Plutôt insatisfait</span>"
            "<span>🟨 Insatisfait</span>"
            "<span style='color:#22c55e'>⬤ Satisfait</span>"
            "<span style='color:#10b981'>⬤ Très satisfait</span>"
            "</div>",
            unsafe_allow_html=True,
        )

    # ── Audit de calcul + Graphique notes ──────────────────
    show_satisfaction_audit(df, mois, sat)

    with st.container(border=True):
        chart_card_title("Répartition des notes (traitement)")
        st.plotly_chart(satisfaction_donut(df, mois), use_container_width=True)


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
    with st.container(border=True):
        chart_card_title("API REST", "Demarrer l'API avec: uvicorn api.main:app --reload")
        st.dataframe(endpoints, use_container_width=True, hide_index=True)



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
    st.set_page_config(
        page_title="RSI Sagemcom — Support IT",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_css()

    df = None
    source_label = None
    load_error = None

    if "dashboard_dataset" in st.session_state:
        df = st.session_state["dashboard_dataset"]
        source_label = st.session_state.get("dashboard_source_label")

    # ── SIDEBAR: navigation only ────────────────────────────────────
    with st.sidebar:
        sidebar_brand()
        active_page = render_nav_buttons()

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        st.markdown(
            """
            <div class="flux-user-card">
                <div class="flux-user-avatar">R</div>
                <div>
                    <div class="flux-user-name">RSI Sagemcom</div>
                    <div class="flux-user-role">Admin</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # No dataset yet → force the dedicated Import page
    if df is None or df.empty:
        active_page = "import"

    # ── MAIN CONTENT AREA ───────────────────────────────────────────
    st.markdown('<div style="padding: 20px 28px 40px 28px;">', unsafe_allow_html=True)

    loaded_months = kpi.available_months(df) if (df is not None and not df.empty) else []

    PAGE_LABELS = {
        "import": "Import des données",
        "dashboard": "Vue globale",
        "analytics": "Analytics",
        "satisfaction": "Satisfaction",
        "reports": "Rapports & Exports",
        "api": "API REST",
    }
    current_label = PAGE_LABELS.get(active_page, "Dashboard")
    st.markdown(
        f"""
        <div class="flux-topbar">
            <div class="flux-topbar-title">{current_label}</div>
            <div class="flux-topbar-right">
                <span class="flux-badge-green">● En ligne</span>
                <span class="flux-badge">Engine v3.0</span>
                {'<span class="flux-badge-green">✓ ' + str(len(loaded_months)) + ' mois chargés</span>' if loaded_months else ''}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── IMPORT PAGE: dedicated drag & drop screen, separate from dashboard ──
    if active_page == "import":
        st.markdown('<div class="welcome-shell"><div class="welcome-inner">', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="welcome-badge"><span class="dot"></span> RSI Sagemcom · Pilotage Support IT</div>
            <h1 class="welcome-title">Vos données.<br><span class="grad">Vos décisions.</span></h1>
            <p class="welcome-copy">
                Importez ASKit. Générez vos KPI. Pilotez.
            </p>
            <div class="welcome-steps">
                <div class="welcome-step"><div class="welcome-step-number">01</div><div class="welcome-step-title">Déposer</div><div class="welcome-step-text">CSV · GZ · XLS · XLSX</div></div>
                <div class="welcome-step"><div class="welcome-step-number">02</div><div class="welcome-step-title">Générer</div><div class="welcome-step-text">Détection et calcul automatique</div></div>
                <div class="welcome-step"><div class="welcome-step-number">03</div><div class="welcome-step-title">Piloter</div><div class="welcome-step-text">KPI · alertes · rapports</div></div>
            </div>
            <div class="welcome-trust">
                <div class="welcome-trust-item"><span class="welcome-trust-num"><span class="grad">3</span></span><span class="welcome-trust-label">Sources unifiées</span></div>
                <div class="welcome-trust-item"><span class="welcome-trust-num"><span class="grad">&lt;5s</span></span><span class="welcome-trust-label">Génération KPI</span></div>
                <div class="welcome-trust-item"><span class="welcome-trust-num"><span class="grad">100%</span></span><span class="welcome-trust-label">Local & sécurisé</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        try:
            df, source_label = load_sidebar_dataset()
        except SchemaError as exc:
            st.error("Le fichier des demandes ASKit n'a pas été reconnu.")
            st.caption(str(exc))
            load_error = exc
        except Exception as exc:
            st.error(str(exc))
            load_error = exc

        if df is not None and not df.empty:
            st.success("Données prêtes")
            if st.button("Ouvrir le dashboard", type="primary", use_container_width=True):
                st.session_state["active_page"] = "dashboard"
                st.rerun()
        st.markdown('</div></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # ── DATA PAGES: advanced period filter on top of the global view ──
    filtered = None
    months = []
    mois = ""

    with st.container(border=True):
        chart_card_title("Période d'analyse", "Filtres actifs")
        filtered = apply_filters(df)

        if filtered is not None and not filtered.empty:
            months = kpi.available_months(filtered)

        if not months:
            st.warning("Aucun mois pour ces filtres")
        else:
            mois = st.selectbox("📅 Mois de pilotage", options=months, index=len(months) - 1)

    if not months or not mois:
        st.markdown('</div>', unsafe_allow_html=True)
        return

    if source_label is None:
        source_label = st.session_state.get("dashboard_source_label", "Source ASKit")

    if active_page == "dashboard":
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

    st.markdown('</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
