import streamlit as st

DEFAULTS = {
    # Auth / grupo
    "auth_ok": False,
    "auth_email": None,
    "auth_user_id": None,
    "access_token": None,
    "refresh_token": None,
    "group_id": None,

    # Proyecto
    "project_code": "tecnic",
}

def init_session_state():
    """Inicializa claves estándar del proyecto si no existen."""
    for k, v in DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v

def clear_auth():
    """Limpia solo lo relacionado con autenticación/grupo."""
    st.session_state["auth_ok"] = DEFAULTS["auth_ok"]
    st.session_state["auth_email"] = DEFAULTS["auth_email"]
    st.session_state["auth_user_id"] = DEFAULTS["auth_user_id"]
    st.session_state["access_token"] = DEFAULTS["access_token"]
    st.session_state["refresh_token"] = DEFAULTS["refresh_token"]
    st.session_state["group_id"] = DEFAULTS["group_id"]

def build_session_key(suffix: str) -> str:
    """
    Construye un session_key único por grupo.
    Formato: {group_id}__{project_code}__{suffix}
    """
    group_id = st.session_state.get("group_id") or "no_group"
    project_code = st.session_state.get("project_code") or "project"
    suffix = (suffix or "default").strip()
    return f"{group_id}__{project_code}__{suffix}"
