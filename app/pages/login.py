"""Login page."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st
from app.session_state import clear_session, is_authenticated, set_session
from src.auth.auth_service import AccountLockedError, AuthService, AuthenticationError
from src.database.connection import get_db, init_db


def render() -> None:
    init_db()

    if is_authenticated():
        st.rerun()
        return

    st.markdown("""
    <div style='text-align:center;padding:2rem 0 1rem 0'>
    <h1 style='color:#003366;font-size:2rem'>RSI Sagemcom</h1>
    <h2 style='color:#0066CC;font-size:1.2rem'>Plateforme KPI IT Support</h2>
    <p style='color:#888;font-size:.9rem'>Acces securise - Usage interne uniquement</p>
    </div>""", unsafe_allow_html=True)

    with st.form("login_form"):
        username = st.text_input("Nom d'utilisateur", placeholder="admin")
        password = st.text_input("Mot de passe", type="password")
        submitted = st.form_submit_button("Se connecter", use_container_width=True, type="primary")

    if submitted:
        if not username or not password:
            st.error("Veuillez saisir vos identifiants.")
        else:
            try:
                with get_db() as conn:
                    svc = AuthService(conn)
                    user, token = svc.login(username=username, password=password)
                set_session(token=token, user_id=user["id"], username=user["username"],
                            role=user["role"], full_name=user["full_name"],
                            must_change_pwd=bool(user["must_change_password"]))
                if user["must_change_password"]:
                    st.warning("Vous devez changer votre mot de passe avant de continuer.")
                st.rerun()
            except AccountLockedError as e:
                st.error(f"Compte verrouille: {e}")
            except AuthenticationError:
                st.error("Identifiants incorrects.")
            except Exception as e:
                st.error(f"Erreur : {e}")

    st.markdown("<div style='text-align:center;margin-top:2rem;color:#aaa;font-size:.75rem'>"
                "RSI Sagemcom IT Support - Application locale confidentielle</div>",
                unsafe_allow_html=True)
