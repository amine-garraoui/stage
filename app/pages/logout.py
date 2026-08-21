"""Logout page."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import streamlit as st
from app.session_state import clear_session, get_session_token, is_authenticated
from src.auth.auth_service import AuthService
from src.database.connection import get_db


def render() -> None:
    token = get_session_token()
    if token:
        try:
            with get_db() as conn:
                AuthService(conn).logout(token)
        except Exception:
            pass
    clear_session()
    st.success("Deconnexion reussie.")
    st.info("Vous pouvez fermer cette page ou vous reconnecter via le menu.")
