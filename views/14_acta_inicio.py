import json
import re
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

from supabase_state import cargar_estado
from supabase_state import guardar_estado as guardar_estado_bd


def guardar_estado(clave, datos):
    def serializar(obj):
        if isinstance(obj, dict):
            return {k: serializar(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [serializar(x) for x in obj]
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return obj

    guardar_estado_bd(clave, serializar(datos))


def _leer_contrato_obra():
    datos = st.session_state.get("contrato_obra_datos", {})
    if not isinstance(datos, dict) or not datos:
        datos = cargar_estado("contrato_obra") or {}
    return datos if isinstance(datos, dict) else {}


def _parse_fecha(valor):
    if isinstance(valor, date):
        return valor
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, str) and valor.strip():
        try:
            return datetime.fromisoformat(valor.strip()).date()
        except Exception:
            return None
    return None


def _extraer_dias_plazo(valor):
    if isinstance(valor, (int, float)):
        return int(valor)

    txt = str(valor or "").strip()
    if not txt:
        return 0

    match = re.search(r"\d+", txt.replace(".", "").replace(",", ""))
    if not match:
        return 0

    try:
        return int(match.group())
    except Exception:
        return 0


def _inicializar_estado():
    if "acta_inicio_obra_datos" not in st.session_state:
        st.session_state["acta_inicio_obra_datos"] = cargar_estado("acta_inicio_obra") or {}

    datos = st.session_state["acta_inicio_obra_datos"]

    if "fecha_inicio" not in datos:
        datos["fecha_inicio"] = None

    if "requisitos" not in datos or not isinstance(datos["requisitos"], list) or len(datos["requisitos"]) == 0:
        datos["requisitos"] = [
            {
                "REQUISITOS": "Garantías y su aprobación",
                "ESTADO": "N.A.",
            }
        ]

    if "certificaciones" not in datos or not isinstance(datos["certificaciones"], list) or len(datos["certificaciones"]) == 0:
        datos["certificaciones"] = [
            {
                "CERTIFICACION": "Afiliacion a Riesgos Laborales",
                "ESTADO": "N.A.",
                "FECHA DE INICIO DE COBERTURA": None,
            }
        ]

    datos["fecha_inicio"] = _parse_fecha(datos.get("fecha_inicio"))

    for fila in datos["certificaciones"]:
        if isinstance(fila, dict):
            fila["FECHA DE INICIO DE COBERTURA"] = _parse_fecha(fila.get("FECHA DE INICIO DE COBERTURA"))


def _guardar():
    guardar_estado("acta_inicio_obra", st.session_state["acta_inicio_obra_datos"])
    st.success("Acta de inicio guardada correctamente.")


_inicializar_estado()
datos = st.session_state["acta_inicio_obra_datos"]
contrato = _leer_contrato_obra()

plazo_dias = _extraer_dias_plazo(contrato.get("plazo_ejecucion", ""))
fecha_inicio = datos.get("fecha_inicio")
fecha_terminacion = fecha_inicio + timedelta(days=plazo_dias) if isinstance(fecha_inicio, date) else None

st.markdown("""
<style>
.titulo-seccion { font-size: 32px !important; font-weight: 800 !important; color: #7A0019; }
.subtitulo-gris { font-size: 16px !important; color: #666; margin-bottom: 15px; }
div[data-testid="stProgress"] > div > div > div > div { background-color: #C62828 !important; }
section[data-testid="stSidebar"] { background-color: #f4f4f4; }
.stButton > button { width: 100%; border-radius: 6px; height: 3em; font-weight: bold; }
button[kind="primary"] {
    background-color: #7A0019 !important;
    border-color: #7A0019 !important;
    color: white !important;
}
button[kind="primary"]:hover {
    background-color: #5C0013 !important;
    border-color: #5C0013 !important;
    color: white !important;
}
</style>
""", unsafe_allow_html=True)

col_t, col_l = st.columns([4, 1], vertical_alignment="center")
with col_t:
    st.markdown('<div class="titulo-seccion">📋 Acta de inicio de obra</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subtitulo-gris">Diligencie la información base del acta de inicio a partir de los datos del contrato de obra.</div>',
        unsafe_allow_html=True
    )
with col_l:
    try:
        st.image("unnamed.jpg", use_container_width=True)
    except Exception:
        pass

st.divider()

with st.sidebar:
    st.header("🧭 Acciones")
    if st.button("💾 Guardar acta", type="primary", key="guardar_acta_inicio_sidebar"):
        _guardar()
    st.markdown("---")
    st.markdown("**Módulo actual:** Acta de inicio de obra")

st.subheader("1. Datos del contrato de obra")

c1, c2 = st.columns(2)
with c1:
    st.text_input(
        "Número de contrato",
        value=str(contrato.get("numero_contrato", "") or ""),
        disabled=True,
        key="acta_numero_contrato_mostrar",
    )
    st.text_input(
        "Nombre del proyecto",
        value=str(contrato.get("nombre_proyecto", "") or ""),
        disabled=True,
        key="acta_nombre_proyecto_mostrar",
    )
    st.text_input(
        "Contratista",
        value=str(contrato.get("nombre_contratista", "") or ""),
        disabled=True,
        key="acta_nombre_contratista_mostrar",
    )

with c2:
    st.text_input(
        "Objeto del contrato",
        value=str(contrato.get("objeto_general", "") or ""),
        disabled=True,
        key="acta_objeto_general_mostrar",
    )
    st.text_input(
        "Plazo de ejecución (días calendario)",
        value=str(contrato.get("plazo_ejecucion", "") or ""),
        disabled=True,
        key="acta_plazo_ejecucion_mostrar",
    )

st.divider()

st.subheader("2. Fechas del acta")

f1, f2 = st.columns(2)

with f1:
    fecha_inicio_seleccionada = st.date_input(
        "Fecha de inicio",
        value=fecha_inicio or date.today(),
        format="DD/MM/YYYY",
        key="acta_fecha_inicio_input",
    )
    datos["fecha_inicio"] = fecha_inicio_seleccionada

with f2:
    fecha_terminacion = datos["fecha_inicio"] + timedelta(days=plazo_dias) if isinstance(datos["fecha_inicio"], date) else None
    st.date_input(
        "Fecha de terminación",
        value=fecha_terminacion or date.today(),
        format="DD/MM/YYYY",
        disabled=True,
        key="acta_fecha_terminacion_input",
    )

st.caption(f"Plazo aplicado desde la hoja 1: {plazo_dias} días calendario.")

st.divider()

st.markdown("**Marque con una X el requisito que aplique para la legalización y ejecución del contrato:**")

df_requisitos = pd.DataFrame(datos["requisitos"])
df_requisitos_edit = st.data_editor(
    df_requisitos,
    width="stretch",
    hide_index=True,
    num_rows="fixed",
    key="acta_requisitos_editor",
    column_order=["REQUISITOS", "ESTADO"],
    column_config={
        "REQUISITOS": st.column_config.TextColumn("REQUISITOS", disabled=True),
        "ESTADO": st.column_config.SelectboxColumn(
            "MARCAR",
            options=["SI", "NO", "N.A."],
            required=True,
        ),
    },
    disabled=["REQUISITOS"],
)
datos["requisitos"] = df_requisitos_edit.to_dict(orient="records")

st.markdown("")

df_cert = pd.DataFrame(datos["certificaciones"])
df_cert_edit = st.data_editor(
    df_cert,
    width="stretch",
    hide_index=True,
    num_rows="fixed",
    key="acta_certificaciones_editor",
    column_order=["CERTIFICACION", "ESTADO", "FECHA DE INICIO DE COBERTURA"],
    column_config={
        "CERTIFICACION": st.column_config.TextColumn("CERTIFICACION", disabled=True),
        "ESTADO": st.column_config.SelectboxColumn(
            "MARCAR",
            options=["SI", "N.A."],
            required=True,
        ),
        "FECHA DE INICIO DE COBERTURA": st.column_config.DateColumn(
            "FECHA DE INICIO DE COBERTURA",
            format="DD/MM/YYYY",
        ),
    },
    disabled=["CERTIFICACION"],
)

certificaciones = df_cert_edit.to_dict(orient="records")
for fila in certificaciones:
    if isinstance(fila, dict):
        fila["FECHA DE INICIO DE COBERTURA"] = _parse_fecha(fila.get("FECHA DE INICIO DE COBERTURA"))
datos["certificaciones"] = certificaciones

st.divider()

if st.button("💾 Guardar acta de inicio", type="primary", key="guardar_acta_inicio_principal"):
    _guardar()
