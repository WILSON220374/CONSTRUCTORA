import json
import streamlit as st
from supabase import create_client

st.header("Hoja 1 — Supabase (CRUD)")

if not st.session_state.get("auth_ok"):
    st.warning("Primero inicia sesión en Login.")
    st.stop()

url = st.secrets.get("SUPABASE_URL")
key = st.secrets.get("SUPABASE_ANON_KEY")

token = st.session_state.get("access_token")
group_id = st.session_state.get("group_id")

if not token:
    st.error("No hay access_token en sesión. Vuelve a Login.")
    st.stop()

if not group_id:
    st.error("No hay group_id en sesión. Verifica que group_users tenga el usuario asignado.")
    st.stop()

supabase = create_client(url, key)
supabase.postgrest.auth(token)

st.write("group_id activo:", group_id)

# El usuario define solo el sufijo; el prefijo lo pone el sistema
session_suffix = st.text_input("session_key (sufijo)", value="tecnic")
session_key = f"{group_id}__{session_suffix}"
st.code(f"session_key real: {session_key}")

payload_text = st.text_area(
    "payload (JSON)",
    value=json.dumps({"hola": "mundo", "version": 1}, ensure_ascii=False, indent=2),
    height=160,
)

col1, col2 = st.columns(2)

with col1:
    if st.button("Upsert"):
        try:
            payload = json.loads(payload_text)
        except Exception as e:
            st.error("El JSON no es válido.")
            st.code(str(e))
            st.stop()

        try:
            data = {"group_id": group_id, "session_key": session_key, "payload": payload}
            resp = supabase.table("app_state").upsert(data, on_conflict="session_key").execute()
            st.success("Upsert OK.")
            st.write(resp.data)
        except Exception as e:
            st.error("Upsert falló.")
            st.code(str(e))

with col2:
    if st.button("Select"):
        try:
            resp = (
                supabase.table("app_state")
                .select("id, created_at, updated_at, group_id, session_key, payload")
                .eq("group_id", group_id)
                .eq("session_key", session_key)
                .limit(1)
                .execute()
            )
            if resp.data:
                st.success("Select OK.")
                st.json(resp.data[0])
            else:
                st.warning("No hay registro para ese session_key en tu grupo.")
        except Exception as e:
            st.error("Select falló.")
            st.code(str(e))
