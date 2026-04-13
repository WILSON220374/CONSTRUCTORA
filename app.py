import streamlit as st
from supabase import create_client

from session_state import init_session_state, clear_auth
from supabase_state import cargar_estado, guardar_estado

st.set_page_config(
    page_title="CONSTRUCTORA",
    layout="wide",
    page_icon="unnamed.jpg",
)

init_session_state()


# =========================
# LOGIN (embebido)
# =========================
def render_login():
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_ANON_KEY")

    if not url or not key:
        st.error("Faltan secrets en Streamlit Cloud: SUPABASE_URL y/o SUPABASE_ANON_KEY.")
        st.stop()

    supabase = create_client(url, key)

    col_img, col_form = st.columns([1, 1.4], vertical_alignment="top")

    with col_img:
        try:
            st.image("unnamed.jpg", use_container_width=True)
        except Exception:
            st.warning("No se pudo cargar la imagen 'unnamed.jpg'. Verifica que exista en la raíz del repo.")

    with col_form:
        st.subheader("Acceso por grupo")

        grupo = st.selectbox(
            "Grupo",
            options=[f"Grupo {i:02d}" for i in range(1, 11)]
            + [f"WGrupo {i}" for i in range(1, 8)]
            + [f"BGrupo {i}" for i in range(1, 8)],
            index=0,
        )

        password = st.text_input("Contraseña", type="password")

        def grupo_to_email(grupo_label: str) -> str:
            partes = grupo_label.split()

            if partes[0] == "Grupo":
                return f"grupo{int(partes[1]):02d}@tecnic.local"
            if partes[0] == "WGrupo":
                return f"wgrupo{int(partes[1]):02d}@tecnic.local"
            return f"bgrupo{int(partes[1]):02d}@tecnic.local"

        st.divider()

        # Botón INGRESAR (verde oscuro)
        st.markdown(
            """
            <style>
            div.stButton > button {
                background-color: #8B0000 !important;
                color: white !important;
                border: 1px solid #B22222 !important;
                border-radius: 10px !important;
                font-weight: 700 !important;
                padding: 0.65rem 1rem !important;
                box-shadow: 0 0 12px rgba(255, 59, 59, 0.35) !important;
            }
            div.stButton > button:hover {
                background-color: #B22222 !important;
                border-color: #FF4D4D !important;
                box-shadow: 0 0 16px rgba(255, 77, 77, 0.45) !important;
            }
            div.stButton > button:active {
                background-color: #5C0000 !important;
            }
            </style>
            """,
            unsafe_allow_html=True
        )

        if st.button("INGRESAR", use_container_width=True):
            clear_auth()
            email = grupo_to_email(grupo)

            try:
                auth_resp = supabase.auth.sign_in_with_password({"email": email, "password": password})

                if not auth_resp or not auth_resp.session or not auth_resp.user:
                    st.error("Login falló: respuesta incompleta de Supabase.")
                    clear_auth()
                    st.stop()

                st.session_state["auth_ok"] = True
                st.session_state["auth_email"] = email
                st.session_state["auth_user_id"] = str(auth_resp.user.id)
                st.session_state["access_token"] = auth_resp.session.access_token
                st.session_state["refresh_token"] = auth_resp.session.refresh_token

                # RLS
                supabase.postgrest.auth(st.session_state["access_token"])

                resp = (
                    supabase.table("group_users")
                    .select("group_id")
                    .eq("user_id", auth_resp.user.id)
                    .limit(1)
                    .execute()
                )
                st.session_state["group_id"] = resp.data[0]["group_id"] if resp.data else None

                if not st.session_state["group_id"]:
                    st.error("El usuario inició sesión pero no tiene group_id asignado en group_users.")
                    clear_auth()
                    st.stop()

                # Forzar recarga de "todo" al entrar
                st.session_state.pop("todo_loaded", None)

                st.success("Acceso correcto.")
                st.rerun()

            except Exception as e:
                clear_auth()
                st.error("Credenciales inválidas o error de autenticación.")
                st.code(str(e))


# =========================
# SIDEBAR
# =========================
def render_sidebar():
    # CSS: quita líneas y reduce espacios
    st.sidebar.markdown(
        """
        <style>
        section[data-testid="stSidebar"] hr { display: none !important; }
        section[data-testid="stSidebar"] .block-container { padding-top: 0.25rem !important; }
        </style>
        """,
        unsafe_allow_html=True
    )

    # CSS: botones sidebar verdes
    st.sidebar.markdown(
        """
        <style>
        section[data-testid="stSidebar"] div.stButton > button {
            background-color: #0B3D2E !important;
            color: white !important;
            border: 1px solid #145A32 !important;
            border-radius: 10px !important;
            font-weight: 700 !important;
            padding: 0.65rem 1rem !important;
            box-shadow: 0 0 12px rgba(0, 230, 118, 0.25) !important;
        }
        section[data-testid="stSidebar"] div.stButton > button:hover {
            background-color: #145A32 !important;
            border-color: #00FF7F !important;
            box-shadow: 0 0 16px rgba(0, 255, 127, 0.35) !important;
        }
        section[data-testid="stSidebar"] div.stButton > button:active {
            background-color: #06281E !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # ====== Cargar "TODO" (una sola vez por sesión) ======
    if "todo_loaded" not in st.session_state:
        st.session_state["todo_loaded"] = True
        try:
            todo = cargar_estado("todo") or {}
            if "integrantes" not in st.session_state and isinstance(todo.get("integrantes"), list):
                st.session_state["integrantes"] = todo.get("integrantes", [])
            if "alcance_datos" not in st.session_state and isinstance(todo.get("alcance_datos"), dict):
                st.session_state["alcance_datos"] = todo.get("alcance_datos", {})
            if "informes_config" not in st.session_state and isinstance(todo.get("informes_config"), dict):
                st.session_state["informes_config"] = todo.get("informes_config", {})
            if "cronograma_datos" not in st.session_state and isinstance(todo.get("cronograma_datos"), dict):
                st.session_state["cronograma_datos"] = todo.get("cronograma_datos", {})
            if "localizacion_datos" not in st.session_state and isinstance(todo.get("localizacion_datos"), dict):
                st.session_state["localizacion_datos"] = todo.get("localizacion_datos", {})
            if "presupuesto_obra_datos" not in st.session_state and isinstance(todo.get("presupuesto_obra_datos"), dict):
                st.session_state["presupuesto_obra_datos"] = todo.get("presupuesto_obra_datos", {})
        except Exception:
            pass

    # Cargar integrantes si no están en memoria (fallback)
    if "integrantes" not in st.session_state:
        try:
            datos = cargar_estado("equipo") or {}
            st.session_state["integrantes"] = datos.get("integrantes", [])
        except Exception:
            st.session_state["integrantes"] = []

    integrantes = st.session_state.get("integrantes", [])

    st.sidebar.markdown("### 👥 Equipo")
    if integrantes:
        for p in integrantes:
            if isinstance(p, dict):
                nombre_completo = (p.get("Nombre Completo") or p.get("nombre") or "").strip()
                solo_nombre = (nombre_completo.split()[0] if nombre_completo else "SIN NOMBRE").upper()
                st.sidebar.markdown(f"**{solo_nombre}**")
    else:
        st.sidebar.caption("Sin integrantes registrados.")

    if st.sidebar.button("💾 GUARDAR TODO EN NUBE", use_container_width=True):
        try:
            payload_todo = {
                "integrantes": st.session_state.get("integrantes", []),
                "alcance_datos": st.session_state.get("alcance_datos", {}),
                "informes_config": st.session_state.get("informes_config", {}),
                "cronograma_datos": st.session_state.get("cronograma_datos", {}),
                "localizacion_datos": st.session_state.get("localizacion_datos", {}),
                "presupuesto_obra_datos": st.session_state.get("presupuesto_obra_datos", {}),
            }
            guardar_estado("todo", payload_todo)
            st.sidebar.success("Guardado OK.")
        except Exception as e:
            st.sidebar.error("Error guardando.")
            st.sidebar.code(str(e))

    if st.sidebar.button("🚪 CERRAR SESIÓN", use_container_width=True):
        clear_auth()
        for k in [
            "integrantes",
            "equipo_edit_idx",
            "equipo_nombre",
            "equipo_tel",
            "equipo_email",
            "alcance_datos",
            "informes_config",
            "cronograma_datos",
            "localizacion_datos",
            "presupuesto_obra_datos",
            "todo_loaded",
        ]:
            st.session_state.pop(k, None)

        try:
            url = st.secrets.get("SUPABASE_URL")
            key = st.secrets.get("SUPABASE_ANON_KEY")
            if url and key:
                create_client(url, key).auth.sign_out()
        except Exception:
            pass

        st.rerun()


# =========================
# FLUJO PRINCIPAL
# =========================
if not st.session_state.get("auth_ok"):
    render_login()
else:
    render_sidebar()

    pages = [
        st.Page("views/0_equipo.py", title="0. Equipo", icon="👥"),
        st.Page("views/1_contrato_obra.py", title="1. Contrato de obra", icon="📄"),
        st.Page("views/1_alcance.py", title="1. Alcance", icon="🎯"),
        st.Page("views/localizacion.py", title="Localización", icon="📍"),
        st.Page("views/2_cronograma.py", title="⭐ 2. CRONOGRAMA", icon="📅"),
        st.Page("views/3_gantt.py", title="3. Diagrama de Gantt", icon="📊"),
        st.Page("views/4_vista_completa_cronograma.py", title="Vista completa cronograma", icon="🖼️"),
        st.Page("views/5_presupuesto_obra.py", title="🟡 PRESUPUESTO DE OBRA", icon="💰"),
        st.Page("views/6_APU.py", title="APU", icon="🧮"),
        st.Page("views/8_crear_apus_obra.py", title="CREAR APUS DE OBRA", icon="🧱"),
        st.Page("views/9_aiu.py", title="AIU", icon="📊"),
        st.Page("views/10_costos_indirectos.py", title="COSTOS INDIRECTOS", icon="📋"),
        st.Page("views/11_factor_multiplicador.py", title="FACTOR MULTIPLICADOR", icon="🧮"),
        st.Page("views/12_estudio_mercado.py", title="12. Estudio de mercado", icon="🛒"),
        st.Page("views/13_flujo_fondos.py", title="13. FLUJO DE FONDOS", icon="📈"),
        st.Page("views/7_presupuesto_consultoria.py", title="🔵 PRESUPUESTO CONSULTORIA", icon="📘"),
        st.Page("views/14_APUS_CONSULTORIA.py", title="APUS CONSULTORÍA", icon="🧮"),
        st.Page("views/15_estudio_mercado_consultoria.py", title="15. Estudio de mercado consultoría", icon="🛒"),
        st.Page("views/16_flujo_fondos_consultoria.py", title="16. FLUJO DE FONDOS CONSULTORÍA", icon="📈"),
        st.Page("views/17_analisis_financiero.py", title="17. ANÁLISIS FINANCIERO", icon="💹"),
        st.Page("views/informes.py", title="Informes", icon="📄"),
        st.Page("views/18_informe_anexos.py", title="18. INFORME ANEXOS", icon="🗂️"),
    ]

    pg = st.navigation(pages)
    pg.run()
