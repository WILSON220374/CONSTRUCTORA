import json
import time
import base64
import streamlit as st
from supabase import create_client
from session_state import init_session_state, build_session_key

# PostgREST APIError (donde viene PGRST303)
try:
    from postgrest.exceptions import APIError
except Exception:
    APIError = Exception


def _make_client():
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError("Faltan secrets SUPABASE_URL y/o SUPABASE_ANON_KEY.")
    return create_client(url, key)


def _apply_access_token(supabase, access_token: str):
    # Importante: esto es lo que hace que RLS vea 'authenticated'
    supabase.postgrest.auth(access_token)
    return supabase


def _token_expirado_o_por_vencer(access_token: str, margen_segundos: int = 120) -> bool:
    try:
        partes = access_token.split(".")
        if len(partes) != 3:
            return False

        payload_b64 = partes[1]
        padding = "=" * (-len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode(payload_b64 + padding).decode("utf-8")
        payload = json.loads(payload_json)

        exp = payload.get("exp")
        if not exp:
            return False

        return time.time() >= (float(exp) - margen_segundos)
    except Exception:
        return False


def _manejar_sesion_expirada():
    st.session_state["auth_ok"] = False
    st.session_state["supabase_session_expired"] = True
    st.warning("Tu sesión expiró. Inicia sesión de nuevo. Los cambios locales no se borran hasta recargar.")
    return None


def _refresh_tokens(supabase):
    """
    Refresca la sesión usando refresh_token en st.session_state.
    Soporta variaciones de supabase-py (refresh_session con/ sin argumento).
    """
    refresh_token = st.session_state.get("refresh_token")
    if not refresh_token:
        return _manejar_sesion_expirada()

    resp = None
    try:
        resp = supabase.auth.refresh_session(refresh_token)
    except Exception:
        pass

    if resp is None:
        try:
            resp = supabase.auth.refresh_session()
        except Exception:
            resp = None

    if resp is None:
        return _manejar_sesion_expirada()

    session = getattr(resp, "session", None)
    if session is None and isinstance(resp, dict):
        session = resp.get("session")

    if session is None:
        return _manejar_sesion_expirada()

    new_access = getattr(session, "access_token", None) or (session.get("access_token") if isinstance(session, dict) else None)
    new_refresh = getattr(session, "refresh_token", None) or (session.get("refresh_token") if isinstance(session, dict) else None)

    if not new_access:
        return _manejar_sesion_expirada()

    st.session_state["access_token"] = new_access
    if new_refresh:
        st.session_state["refresh_token"] = new_refresh

    _apply_access_token(supabase, new_access)
    st.session_state["supabase_session_expired"] = False
    return supabase


def get_supabase_client():
    """
    Cliente autenticado listo para RLS.
    Refresca el token antes de usarlo si ya venció o está por vencer.
    """
    init_session_state()

    access_token = st.session_state.get("access_token")
    if not access_token:
        return None

    supabase = _make_client()

    if _token_expirado_o_por_vencer(access_token):
        supabase = _refresh_tokens(supabase)
        if supabase is None:
            return None
        access_token = st.session_state.get("access_token")

    if not access_token:
        return None

    _apply_access_token(supabase, access_token)
    return supabase

def _execute_with_refresh_retry(execute_callable):
    """
    Ejecuta una operación PostgREST. Si falla por JWT expired (PGRST303),
    refresca y reintenta una sola vez.
    """
    try:
        return execute_callable()
    except Exception as e:
        info = {}
        code = None
        msg = str(e)

        try:
            info = e.args[0] if e.args else {}
        except Exception:
            info = {}

        if isinstance(info, dict):
            code = info.get("code")
            msg = info.get("message", msg)

        es_jwt_expirado = (
            code == "PGRST303"
            or "JWT expired" in str(msg)
            or "PGRST303" in str(msg)
        )

        if not es_jwt_expirado:
            raise

        supabase = _make_client()
        _refresh_tokens(supabase)
        return execute_callable()


def guardar_estado(suffix: str, payload: dict, merge: bool = False):
    """
    Upsert en public.app_state (por grupo + session_key).
    merge se mantiene por compatibilidad (si no lo usas, no afecta).
    """
    init_session_state()
    if not isinstance(payload, dict):
        raise ValueError("payload debe ser dict.")

    group_id = st.session_state.get("group_id")
    if not group_id:
        raise RuntimeError("No hay group_id en session_state.")

    session_key = build_session_key(suffix)

    # Sanitización JSON segura (evita objetos no serializables)
    payload_seguro = json.loads(json.dumps(payload, default=str))

    data = {"group_id": group_id, "session_key": session_key, "payload": payload_seguro}

    def _do():
        supabase = get_supabase_client()
        if supabase is None:
            return None
        return supabase.table("app_state").upsert(data, on_conflict="session_key").execute()

    try:
        return _execute_with_refresh_retry(_do)
    except Exception:
        _manejar_sesion_expirada()
        return None

def cargar_estado(suffix: str):
    init_session_state()

    group_id = st.session_state.get("group_id")
    if not group_id:
        raise RuntimeError("No hay group_id en session_state.")

    session_key = build_session_key(suffix)

    def _do():
        supabase = get_supabase_client()
        if supabase is None:
            return None
        return (
            supabase.table("app_state")
            .select("payload")
            .eq("group_id", group_id)
            .eq("session_key", session_key)
            .limit(1)
            .execute()
        )

    try:
        resp = _execute_with_refresh_retry(_do)
    except Exception:
        _manejar_sesion_expirada()
        return None

    if resp is None:
        return None

    if resp.data:
        return resp.data[0].get("payload")
    return None


def exportar_estado_json(suffix: str):
    payload = cargar_estado(suffix)
    if payload is None:
        return None
    return json.dumps(payload, ensure_ascii=False, indent=2)


def guardar_apus_generados_obra(payload: dict):
    return guardar_estado("apus_generados_obra", payload)


def cargar_apus_generados_obra():
    data = cargar_estado("apus_generados_obra")
    if isinstance(data, dict):
        return data
    return {}
