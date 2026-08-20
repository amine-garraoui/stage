"""Administration - Page 9 (ADMIN only)."""
import sys, os, json, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import pandas as pd
import streamlit as st
from app.session_state import get_current_role, get_current_full_name, get_current_user_id, require_auth, require_role
from app.components.sidebar import render_sidebar
from src.auth.user_service import UserService, DuplicateUsernameError
from src.database.connection import get_db
from src.engine.importer import AskitImporter, DuplicateImportError, ImportError as AskImportError
from src.engine.kpi_engine import KpiEngine
from src.anomaly.anomaly_detector import AnomalyDetector
from src.forecasting.forecasting_service import ForecastingService
from src.insights.insights_engine import InsightsEngine


def render() -> None:
    require_auth()
    require_role("ADMIN")
    role = get_current_role()
    full_name = get_current_full_name()
    uid = get_current_user_id()
    render_sidebar(role, full_name)
    st.title("Administration")

    tabs = st.tabs(["Import", "Recalcul KPI", "Utilisateurs", "Audit", "Suppression"])

    # Import
    with tabs[0]:
        st.subheader("Importer un fichier ASKit")
        uploaded = st.file_uploader("Fichier ASKit (.xlsx, .xls, .csv)", type=["xlsx", "xls", "csv"])
        if uploaded:
            st.info(f"**{uploaded.name}** - {uploaded.size / 1024:.1f} KB")
            if st.button("Lancer l'import", type="primary"):
                suffix = Path(uploaded.name).suffix
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(uploaded.getbuffer())
                    tmp_path = Path(tmp.name)
                try:
                    with get_db() as conn:
                        result = AskitImporter(conn, uid).run(tmp_path, uploaded.name)
                    st.success(f"Import #{result['id']}: **{result['rows_imported']}** lignes, {result['rows_rejected']} rejetees.")
                    with get_db() as conn:
                        KpiEngine(conn).recalculate_all()
                    st.info("KPIs recalcules automatiquement.")
                    st.balloons()
                except DuplicateImportError as e:
                    st.warning(f"Doublon detecte: {e}")
                except AskImportError as e:
                    st.error(f"Erreur import: {e}")
                except Exception as e:
                    st.error(f"Erreur inattendue: {e}")
                finally:
                    try:
                        os.unlink(tmp_path)
                    except Exception:
                        pass

        st.divider()
        st.subheader("Historique des Imports")
        with get_db() as conn:
            rows = [dict(r) for r in conn.execute(
                "SELECT id, original_filename, status, rows_imported, rows_rejected, created_at FROM data_imports ORDER BY created_at DESC LIMIT 20"
            ).fetchall()]
        if rows:
            st.dataframe(pd.DataFrame(rows).rename(columns={
                "id": "ID", "original_filename": "Fichier", "status": "Statut",
                "rows_imported": "Importees", "rows_rejected": "Rejetees", "created_at": "Date"
            }), use_container_width=True, hide_index=True)

    # Recalcul
    with tabs[1]:
        st.subheader("Recalcul Complet des Indicateurs")
        if st.button("Tout recalculer", type="primary"):
            bar = st.progress(0, "Demarrage...")
            with get_db() as conn:
                bar.progress(10, "Calcul KPIs...")
                engine = KpiEngine(conn)
                n = engine.recalculate_all()
                bar.progress(40, "Previsions...")
                kpi_df = engine.get_monthly_dataframe()
                ForecastingService(conn).run_all(kpi_df)
                bar.progress(70, "Anomalies...")
                AnomalyDetector(conn).detect_all(kpi_df)
                bar.progress(85, "Syntheses executives...")
                ins = InsightsEngine(conn)
                for _, row in kpi_df.iterrows():
                    try:
                        ins.generate_for_period(int(row["year"]), int(row["month"]))
                    except Exception:
                        pass
            bar.progress(100, "Termine!")
            st.success(f"{n} snapshots KPI generes.")

    # Users
    with tabs[2]:
        st.subheader("Gestion des Utilisateurs")
        with get_db() as conn:
            users = [dict(r) for r in conn.execute(
                "SELECT id, username, full_name, role, is_active, last_login FROM users ORDER BY username"
            ).fetchall()]
        if users:
            df = pd.DataFrame(users)
            df["is_active"] = df["is_active"].map({1: "Actif", 0: "Inactif"})
            df["last_login"] = df["last_login"].fillna("Jamais")
            st.dataframe(df.rename(columns={"id": "ID", "username": "Utilisateur", "full_name": "Nom",
                                             "role": "Role", "is_active": "Actif", "last_login": "Derniere connexion"}),
                         use_container_width=True, hide_index=True)

        with st.expander("Creer un utilisateur"):
            with st.form("create_user"):
                nu = st.text_input("Nom d'utilisateur")
                nf = st.text_input("Nom complet")
                ne = st.text_input("Email (optionnel)")
                nr = st.selectbox("Role", ["USER", "ADMIN"])
                np = st.text_input("Mot de passe initial", type="password")
                if st.form_submit_button("Creer", type="primary"):
                    try:
                        with get_db() as conn:
                            UserService(conn, uid, role).create_user(nu, nf, np, nr, ne or None)
                        st.success(f"Utilisateur '{nu}' cree.")
                        st.rerun()
                    except DuplicateUsernameError as e:
                        st.error(f"Erreur: {e}")
                    except ValueError as e:
                        st.error(f"Erreur: {e}")

    # Audit
    with tabs[3]:
        st.subheader("Journal d'Audit")
        with get_db() as conn:
            logs = [dict(r) for r in conn.execute(
                "SELECT created_at, username, action, resource, success, details FROM audit_logs ORDER BY created_at DESC LIMIT 200"
            ).fetchall()]
        if logs:
            df = pd.DataFrame(logs)
            df["success"] = df["success"].map({1: "OK", 0: "ECHEC"})
            df["details"] = df["details"].fillna("").str[:80]
            st.dataframe(df.rename(columns={"created_at": "Date", "username": "Utilisateur",
                                             "action": "Action", "resource": "Ressource",
                                             "success": "Succes", "details": "Details"}),
                         use_container_width=True, hide_index=True)
        else:
            st.info("Journal vide.")

    # Delete
    with tabs[4]:
        st.subheader("Suppression des Donnees")
        st.error("Action irreversible. Toutes les donnees importees seront supprimees.")
        with get_db() as conn:
            n_imp = conn.execute("SELECT COUNT(*) FROM data_imports").fetchone()[0]
            n_kpi = conn.execute("SELECT COUNT(*) FROM kpi_snapshots").fetchone()[0]
        st.metric("Imports", n_imp)
        st.metric("Snapshots KPI", n_kpi)
        confirm = st.checkbox("Je confirme la suppression")
        if confirm and st.button("SUPPRIMER TOUTES LES DONNEES", type="primary"):
            with get_db() as conn:
                for tbl in ["tickets", "forecast_results", "anomaly_records",
                            "executive_insights", "kpi_snapshots", "data_imports"]:
                    conn.execute(f"DELETE FROM {tbl}")
                conn.execute("INSERT INTO audit_logs (user_id, action, details, success) VALUES (?,?,?,1)",
                             (uid, "DATA_DELETED", "All data deleted by admin"))
            st.success("Donnees supprimees.")
            st.rerun()
