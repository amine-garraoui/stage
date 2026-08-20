"""Change password page."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import streamlit as st
from app.session_state import get_current_user_id, get_current_role, get_current_full_name, require_auth
from src.auth.user_service import UserService
from src.database.connection import get_db


def render() -> None:
    require_auth()
    uid = get_current_user_id()
    role = get_current_role()
    name = get_current_full_name()
    st.title("Changer le Mot de Passe")
    st.caption(f"Utilisateur : **{name}**")

    with st.form("pwd_form"):
        cur = st.text_input("Mot de passe actuel", type="password")
        new = st.text_input("Nouveau mot de passe", type="password")
        confirm = st.text_input("Confirmer", type="password")
        submitted = st.form_submit_button("Changer", type="primary")

    if submitted:
        if new != confirm:
            st.error("Les mots de passe ne correspondent pas.")
        else:
            try:
                with get_db() as conn:
                    UserService(conn, uid, role).change_password(uid, new, current_password=cur)
                st.success("Mot de passe modifie avec succes.")
            except ValueError as e:
                st.error(f"Erreur : {e}")
