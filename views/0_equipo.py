import streamlit as st
import os
from supabase_state import cargar_estado, guardar_estado


def inicializar_equipo():
    # Cargar desde nube solo si no existe en session_state
    if "integrantes" not in st.session_state or not isinstance(st.session_state["integrantes"], list):
        datos_db = cargar_estado("equipo") or {}
        st.session_state["integrantes"] = datos_db.get("integrantes", [])

    if "equipo_edit_idx" not in st.session_state:
        st.session_state["equipo_edit_idx"] = None

    # Keys de formulario (para prefills)
    if "equipo_nombre" not in st.session_state:
        st.session_state["equipo_nombre"] = ""
    if "equipo_tel" not in st.session_state:
        st.session_state["equipo_tel"] = ""
    if "equipo_email" not in st.session_state:
        st.session_state["equipo_email"] = ""


def guardar_datos_nube():
    payload = {"integrantes": st.session_state.get("integrantes", [])}
    guardar_estado("equipo", payload)


inicializar_equipo()

# --- ESTILOS CSS ---
st.markdown(
    """
    <style>
    .ficha-equipo {
        background-color: #FFF1F1;
        border-left: 10px solid #B22222;
        padding: 20px;
        border-radius: 15px;
        margin-bottom: 10px;
        box-shadow: 4px 4px 10px rgba(0,0,0,0.08);
        height: 160px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .nombre-mediano {
        font-size: 24px !important;
        color: #8B0000;
        font-weight: 800;
        line-height: 1.2;
        margin-bottom: 8px;
    }
    .detalle-pequeno {
        font-size: 15px !important;
        color: #555;
        margin-bottom: 4px;
    }

    .titulo-principal {
        font-size: 42px !important;
        font-weight: 800 !important;
        color: #B22222;
        text-align: left;
        margin-bottom: 25px;
    }

    div[data-testid="stForm"] {
        border: 1px solid #eee;
        padding: 20px;
        border-radius: 12px;
        background-color: #fafafa;
        margin-top: 0px;
    }

    [data-testid="stImage"] img {
        pointer-events: none;
        user-select: none;
        border-radius: 15px;
    }
    [data-testid="StyledFullScreenButton"] { display: none !important; }

    div.stButton > button[data-testid^="stBaseButton"] {
        border-radius: 10px !important;
    }

    /* BOTÓN PRINCIPAL (type="primary") EN VERDE TECNIC — selector robusto */
    div.stButton > button[kind="primary"],
    button[kind="primary"],
    div.stButton > button[data-testid*="primary"],
    button[data-testid*="primary"] {
        background-color: #8B0000 !important;
        color: white !important;
        border: 1px solid #B22222 !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
    }
    div.stButton > button[kind="primary"]:hover,
    button[kind="primary"]:hover,
    div.stButton > button[data-testid*="primary"]:hover,
    button[data-testid*="primary"]:hover {
        background-color: #B22222 !important;
        border-color: #FF4D4D !important;
    }
    div.stButton > button[kind="primary"]:active,
    button[kind="primary"]:active,
    div.stButton > button[data-testid*="primary"]:active,
    button[data-testid*="primary"]:active {
        background-color: #5C0000 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# SECCIÓN SUPERIOR
# ---------------------------------------------------------
st.markdown('<div class="titulo-principal">Gestión de Equipo</div>', unsafe_allow_html=True)

col_titulo, col_btn = st.columns([4, 1])
with col_titulo:
    st.subheader("Miembros Registrados")
with col_btn:
    if st.session_state.get("equipo_edit_idx") is not None:
        if st.button("✖️ Cancelar", help="Cancela la edición actual"):
            st.session_state["equipo_edit_idx"] = None
            st.session_state["equipo_nombre"] = ""
            st.session_state["equipo_tel"] = ""
            st.session_state["equipo_email"] = ""
            st.rerun()

integrantes_raw = st.session_state.get("integrantes", [])

integrantes_indexados = []
for i, p in enumerate(integrantes_raw):
    if isinstance(p, dict) and p:
        integrantes_indexados.append((i, p))

if integrantes_indexados:
    cols = st.columns(3)
    for n, (real_idx, persona) in enumerate(integrantes_indexados):
        with cols[n % 3]:
            nombre_raw = persona.get("Nombre Completo") or "SIN NOMBRE"
            nombre = str(nombre_raw).upper()
            tel = persona.get("Teléfono") or "N/A"
            email = persona.get("Correo Electrónico") or "N/A"

            st.markdown(
                f"""
                <div class="ficha-equipo">
                    <div class="nombre-mediano">👤 {nombre}</div>
                    <div class="detalle-pequeno">📞 {tel}</div>
                    <div class="detalle-pequeno">✉️ {email}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            b1, b2 = st.columns(2)
            with b1:
                if st.button("✏️ Editar", key=f"edit_{real_idx}", use_container_width=True):
                    st.session_state["equipo_edit_idx"] = real_idx
                    st.session_state["equipo_nombre"] = persona.get("Nombre Completo", "") or ""
                    st.session_state["equipo_tel"] = persona.get("Teléfono", "") or ""
                    st.session_state["equipo_email"] = persona.get("Correo Electrónico", "") or ""
                    st.rerun()

            with b2:
                if st.button("🗑️ Eliminar", key=f"del_{real_idx}", use_container_width=True):
                    try:
                        st.session_state["integrantes"].pop(real_idx)
                    except Exception:
                        st.session_state["integrantes"] = [
                            p for j, p in enumerate(st.session_state.get("integrantes", [])) if j != real_idx
                        ]

                    if st.session_state.get("equipo_edit_idx") == real_idx:
                        st.session_state["equipo_edit_idx"] = None
                        st.session_state["equipo_nombre"] = ""
                        st.session_state["equipo_tel"] = ""
                        st.session_state["equipo_email"] = ""

                    try:
                        guardar_datos_nube()
                    except Exception as e:
                        st.error("Error al guardar en nube tras eliminar.")
                        st.code(str(e))

                    st.rerun()
else:
    st.info("No hay equipo registrado aún.")

st.divider()

# ---------------------------------------------------------
# SECCIÓN INFERIOR: IMAGEN vs FORMULARIO
# ---------------------------------------------------------
col_izq_vacia, col_img, col_form, col_der_vacia = st.columns([0.6, 1.3, 2.2, 0.6], gap="medium")

with col_img:
    st.write("")
    st.write("")
    if os.path.exists("unnamed.jpg"):
        st.image("unnamed.jpg", use_container_width=True)
    else:
        st.info("Logo TECNIC")

with col_form:
    st.markdown("##### Registrar Nuevo Integrante")

    with st.form("form_registro", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            nuevo_nombre = st.text_input("Nombre *", key="equipo_nombre")
            nuevo_tel = st.text_input("Teléfono", key="equipo_tel")
        with c2:
            nuevo_email = st.text_input("Email", key="equipo_email")
            st.write("")

        submitted = st.form_submit_button("💾 GUARDAR", type="primary", use_container_width=True)

        if submitted:
            if nuevo_nombre:
                nuevo_integrante = {
                    "Nombre Completo": nuevo_nombre,
                    "Teléfono": nuevo_tel,
                    "Correo Electrónico": nuevo_email,
                }

                if "integrantes" not in st.session_state or not isinstance(st.session_state["integrantes"], list):
                    st.session_state["integrantes"] = []

                edit_idx = st.session_state.get("equipo_edit_idx")
                if (
                    edit_idx is not None
                    and isinstance(edit_idx, int)
                    and 0 <= edit_idx < len(st.session_state["integrantes"])
                ):
                    st.session_state["integrantes"][edit_idx] = nuevo_integrante
                    st.toast(f"{nuevo_nombre} actualizado correctamente")
                else:
                    st.session_state["integrantes"].append(nuevo_integrante)
                    st.toast(f"{nuevo_nombre} agregado correctamente")

                st.session_state["equipo_edit_idx"] = None

                try:
                    guardar_datos_nube()
                except Exception as e:
                    st.error("Error al guardar en nube.")
                    st.code(str(e))

                st.rerun()
            else:
                st.error("Nombre obligatorio.")
