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
            options=[f"Grupo {i:02d}" for i in range(1, 6)]
            + [f"WGrupo {i:02d}" for i in range(1, 9)],
            index=0,
        )

        password = st.text_input("Contraseña", type="password")

        def grupo_to_emails(grupo_label: str) -> list[str]:
            partes = grupo_label.strip().lower().split()
            if len(partes) != 2:
                return []

            numero = int(partes[1])

            if partes[0] == "grupo":
                base = f"grupo{numero:02d}"
            elif partes[0] == "wgrupo":
                base = f"wgrupo{numero:02d}"
            else:
                base = f"bgrupo{numero:02d}"

            return [
                f"{base}@constructor.local",
                f"{base}@tecnic.local",
            ]
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
            emails = grupo_to_emails(grupo)

            try:
                auth_resp = None
                email_ok = None

                for email in emails:
                    try:
                        intento = supabase.auth.sign_in_with_password({"email": email, "password": password})
                        if intento and intento.session and intento.user:
                            auth_resp = intento
                            email_ok = email
                            break
                    except Exception:
                        continue

                if not auth_resp or not auth_resp.session or not auth_resp.user:
                    st.error("Credenciales inválidas o error de autenticación.")
                    clear_auth()
                    st.stop()

                st.session_state["auth_ok"] = True
                st.session_state["auth_email"] = email_ok
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

    # CSS: botones sidebar negros
    st.sidebar.markdown(
        """
        <style>
        section[data-testid="stSidebar"] div.stButton > button {
            background-color: #000000 !important;
            color: white !important;
            border: 1px solid #222222 !important;
            border-radius: 10px !important;
            font-weight: 700 !important;
            padding: 0.65rem 1rem !important;
            box-shadow: 0 0 12px rgba(0, 0, 0, 0.25) !important;
        }
        section[data-testid="stSidebar"] div.stButton > button:hover {
            background-color: #1a1a1a !important;
            border-color: #444444 !important;
            box-shadow: 0 0 16px rgba(0, 0, 0, 0.35) !important;
        }
        section[data-testid="stSidebar"] div.stButton > button:active {
            background-color: #000000 !important;
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
        st.Page("views/2_ver_contrato.py", title="2. Ver contrato", icon="📘"),
        st.Page("views/3_contrato_interventoria.py", title="3. Contrato de interventoría", icon="📑"),
        st.Page("views/4_ver_contrato_interventoria.py", title="4. Ver contrato interventoría", icon="📘"),
        st.Page("views/1_alcance.py", title="5. Alcance", icon="🎯"),
        st.Page("views/2_cronograma.py", title="⭐ 6. CRONOGRAMA", icon="📅"),
        st.Page("views/3_gantt.py", title="7. Diagrama de Gantt", icon="📊"),
        st.Page("views/4_vista_completa_cronograma.py", title="8. Vista completa cronograma", icon="🖼️"),
        st.Page("views/5_presupuesto_obra.py", title="🟡 9. PRESUPUESTO DE OBRA", icon="💰"),
        st.Page("views/6_APU.py", title="APU", icon="🧮"),
        st.Page("views/8_crear_apus_obra.py", title="10. CREAR APUS DE OBRA", icon="🧱"),
        st.Page("views/9_aiu.py", title="11. AIU", icon="📊"),
        st.Page("views/10_costos_indirectos.py", title="12 COSTOS INDIRECTOS", icon="📋"),
        st.Page("views/11_factor_multiplicador.py", title="13 FACTOR MULTIPLICADOR", icon="🧮"),
        st.Page("views/12_estudio_mercado.py", title="14. Estudio de mercado", icon="🛒"),
        st.Page("views/13_flujo_fondos.py", title="15. FLUJO DE FONDOS", icon="📈"),
        st.Page("views/informes.py", title="16. Informes", icon="📄"),
        st.Page("views/18_informe_anexos.py", title="17. INFORME ANEXOS", icon="🗂️"),
        st.Page("views/14_acta_inicio.py", title="18. Acta de inicio obra", icon="📋"),
        st.Page("views/15_reunion_tecnica.py", title="19. Reunión técnica inicial", icon="📝"),
        st.Page("views/16_plan_inversion_anticipo.py", title="20. Anticipo", icon="💳"),
        st.Page("views/17_bitacora_obra.py", title="21. Bitácora de obra", icon="📓"),
        st.Page("views/19_acta_reunion.py", title="22. Acta de reunión", icon="📑"),
        st.Page("views/20_comite_obra.py", title="23. Comité de obra", icon="🧾"),
    ]

    pg = st.navigation(pages)
    pg.run()
