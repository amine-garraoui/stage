"""Streamlit session state manager."""

from __future__ import annotations
from typing import Optional
import streamlit as st

_TOKEN = "_rsi_token"
_USER_ID = "_rsi_uid"
_USERNAME = "_rsi_uname"
_ROLE = "_rsi_role"
_FULLNAME = "_rsi_name"
_MUST_CHANGE = "_rsi_pwchange"


def is_authenticated() -> bool:
    return bool(st.session_state.get(_TOKEN))


def get_session_token() -> Optional[str]:
    return st.session_state.get(_TOKEN)


def get_current_user_id() -> Optional[int]:
    return st.session_state.get(_USER_ID)


def get_current_username() -> Optional[str]:
    return st.session_state.get(_USERNAME)


def get_current_role() -> Optional[str]:
    return st.session_state.get(_ROLE)


def get_current_full_name() -> Optional[str]:
    return st.session_state.get(_FULLNAME)


def must_change_password() -> bool:
    return bool(st.session_state.get(_MUST_CHANGE, False))


def set_session(token, user_id, username, role, full_name, must_change_pwd=False):
    st.session_state[_TOKEN] = token
    st.session_state[_USER_ID] = user_id
    st.session_state[_USERNAME] = username
    st.session_state[_ROLE] = role
    st.session_state[_FULLNAME] = full_name
    st.session_state[_MUST_CHANGE] = must_change_pwd


def clear_session():
    for k in (_TOKEN, _USER_ID, _USERNAME, _ROLE, _FULLNAME, _MUST_CHANGE):
        st.session_state.pop(k, None)


def require_auth():
    if not is_authenticated():
        st.switch_page("app/pages/login.py")


def require_role(required_role: str):
    require_auth()
    if get_current_role() != required_role and get_current_role() != "ADMIN":
        st.error("⛔ Accès refusé. Droits insuffisants.")
        st.stop()
