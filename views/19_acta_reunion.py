from datetime import date, datetime

import pandas as pd
import streamlit as st

from supabase_state import cargar_estado
from supabase_state import guardar_estado as guardar_estado_bd


CLAVE_GUARDADO = "acta_reunion_obra"
MIN_FILAS_COMPROMISOS = 1
MIN_FILAS_PARTICIPANTES = 1


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


def _texto(valor) -> str:
    if valor is None:
        return ""
    return str(valor).strip()


def _primero_no_vacio(*valores):
    for valor in valores:
        txt = _texto(valor)
        if txt:
            return txt
    return ""


def _parse_fecha(valor):
    if isinstance(valor, date):
        return valor
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, str) and valor.strip():
        txt = valor.strip()
        try:
            return datetime.fromisoformat(txt).date()
        except Exception:
            pass
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(txt, fmt).date()
            except Exception:
                continue
    return date.today()


def _leer_estado_directo(clave: str) -> dict:
    datos = cargar_estado(clave) or {}
    return datos if isinstance(datos, dict) else {}


def _leer_acta_inicio() -> dict:
    return _leer_estado_directo("acta_inicio_obra")


def _leer_contrato_obra() -> dict:
    return _leer_estado_directo("contrato_obra")


def _leer_contrato_interventoria() -> dict:
    return _leer_estado_directo("contrato_interventoria")


def _fila_compromiso_vacia():
    return {
        "COMPROMISOS PACTADOS": "",
        "RESPONSABLES": "",
        "FECHA DE CUMPLIMIENTO": date.today(),
    }


def _fila_participante_vacia():
    return {
        "NOMBRE DEL PARTICIPANTE": "",
        "CARGO": "",
        "EMPRESA / ENTIDAD": "",
    }


def _normalizar_compromisos(rows):
    filas = []
    for fila in rows or []:
        base = _fila_compromiso_vacia()
        if isinstance(fila, dict):
            base["COMPROMISOS PACTADOS"] = _texto(fila.get("COMPROMISOS PACTADOS"))
            base["RESPONSABLES"] = _texto(fila.get("RESPONSABLES"))
            base["FECHA DE CUMPLIMIENTO"] = _parse_fecha(fila.get("FECHA DE CUMPLIMIENTO"))
        filas.append(base)

    while len(filas) < MIN_FILAS_COMPROMISOS:
        filas.append(_fila_compromiso_vacia())

    return filas


def _normalizar_participantes(rows):
    filas = []
    for fila in rows or []:
        base = _fila_participante_vacia()
        if isinstance(fila, dict):
            base["NOMBRE DEL PARTICIPANTE"] = _texto(fila.get("NOMBRE DEL PARTICIPANTE"))
            base["CARGO"] = _texto(fila.get("CARGO"))
            base["EMPRESA / ENTIDAD"] = _texto(fila.get("EMPRESA / ENTIDAD"))
        filas.append(base)

    while len(filas) < MIN_FILAS_PARTICIPANTES:
        filas.append(_fila_participante_vacia())

    return filas


def _datos_encabezado(acta_inicio, contrato_obra, contrato_interventoria):
    return {
        "contrato_obra_no": _primero_no_vacio(
            acta_inicio.get("numero_contrato"),
            contrato_obra.get("numero_contrato"),
        ),
        "contratista": _primero_no_vacio(
            acta_inicio.get("nombre_firma_contratista"),
            contrato_obra.get("nombre_contratista"),
        ),
        "objeto_contrato_obra": _primero_no_vacio(
            acta_inicio.get("objeto_contrato"),
            contrato_obra.get("objeto_general"),
            contrato_obra.get("objeto_contrato"),
            contrato_obra.get("objeto"),
        ),
        "interventor": _primero_no_vacio(
            acta_inicio.get("nombre_firma_interventor"),
            contrato_interventoria.get("nombre_contratista"),
            contrato_interventoria.get("nombre_interventor"),
            contrato_obra.get("nombre_interventor"),
            contrato_obra.get("nombre_supervisor"),
        ),
    }


def _acta_vacia(nueva_no: int, acta_inicio, contrato_obra, contrato_interventoria):
    encabezado = _datos_encabezado(acta_inicio, contrato_obra, contrato_interventoria)
    return {
        "acta_no": int(nueva_no),
        "fecha": date.today().isoformat(),
        "contrato_obra_no": encabezado["contrato_obra_no"],
        "contratista": encabezado["contratista"],
        "objeto_contrato_obra": encabezado["objeto_contrato_obra"],
        "interventor": encabezado["interventor"],
        "objetivos_reunion": "",
        "desarrollo_reunion": "",
        "compromisos": _normalizar_compromisos([]),
        "participantes": _normalizar_participantes([]),
    }


def _normalizar_acta(acta, acta_inicio, contrato_obra, contrato_interventoria):
    if not isinstance(acta, dict):
        acta = {}

    encabezado = _datos_encabezado(acta_inicio, contrato_obra, contrato_interventoria)

    return {
        "acta_no": int(acta.get("acta_no") or 1),
        "fecha": _parse_fecha(acta.get("fecha")).isoformat(),
        "contrato_obra_no": _primero_no_vacio(
            acta.get("contrato_obra_no"),
            encabezado["contrato_obra_no"],
        ),
        "contratista": _primero_no_vacio(
            acta.get("contratista"),
            encabezado["contratista"],
        ),
        "objeto_contrato_obra": _primero_no_vacio(
            acta.get("objeto_contrato_obra"),
            encabezado["objeto_contrato_obra"],
        ),
        "interventor": _primero_no_vacio(
            acta.get("interventor"),
            encabezado["interventor"],
        ),
        "objetivos_reunion": _texto(acta.get("objetivos_reunion")),
        "desarrollo_reunion": _texto(acta.get("desarrollo_reunion")),
        "compromisos": _normalizar_compromisos(acta.get("compromisos", [])),
        "participantes": _normalizar_participantes(acta.get("participantes", [])),
    }


def _inicializar_estado(acta_inicio, contrato_obra, contrato_interventoria):
    group_id_actual = _texto(st.session_state.get("group_id"))
    cache_group = _texto(st.session_state.get("_acta_reunion_group"))

    if cache_group != group_id_actual or "acta_reunion_datos" not in st.session_state:
        cargado = cargar_estado(CLAVE_GUARDADO) or {}
        if not isinstance(cargado, dict):
            cargado = {}

        actas = cargado.get("actas", [])
        if not isinstance(actas, list):
            actas = []

        actas_normalizadas = [
            _normalizar_acta(x, acta_inicio, contrato_obra, contrato_interventoria)
            for x in actas
        ]

        if not actas_normalizadas:
            actas_normalizadas = [
                _acta_vacia(1, acta_inicio, contrato_obra, contrato_interventoria)
            ]

        st.session_state["acta_reunion_datos"] = {
            "actas": actas_normalizadas,
            "acta_activa": int(cargado.get("acta_activa") or actas_normalizadas[-1]["acta_no"]),
        }
        st.session_state["_acta_reunion_group"] = group_id_actual


def _guardar():
    guardar_estado(CLAVE_GUARDADO, st.session_state["acta_reunion_datos"])
    st.success("Acta de reunión guardada correctamente.")


def _obtener_acta_activa():
    datos = st.session_state["acta_reunion_datos"]
    actas = datos.get("actas", [])
    activa = int(datos.get("acta_activa") or 1)

    for acta in actas:
        if int(acta.get("acta_no") or 0) == activa:
            return acta

    if actas:
        datos["acta_activa"] = int(actas[0]["acta_no"])
        return actas[0]

    nueva = _acta_vacia(
        1,
        _leer_acta_inicio(),
        _leer_contrato_obra(),
        _leer_contrato_interventoria(),
    )
    datos["actas"] = [nueva]
    datos["acta_activa"] = 1
    return nueva


def _crear_nueva_acta(acta_inicio, contrato_obra, contrato_interventoria):
    datos = st.session_state["acta_reunion_datos"]
    actas = datos.get("actas", [])
    ultima = max([int(x.get("acta_no") or 0) for x in actas], default=0)
    nueva = _acta_vacia(ultima + 1, acta_inicio, contrato_obra, contrato_interventoria)
    actas.append(nueva)
    datos["acta_activa"] = int(nueva["acta_no"])
    return int(nueva["acta_no"])


acta_inicio = _leer_acta_inicio()
contrato_obra = _leer_contrato_obra()
contrato_interventoria = _leer_contrato_interventoria()

_inicializar_estado(acta_inicio, contrato_obra, contrato_interventoria)

datos = st.session_state["acta_reunion_datos"]
actas = datos.get("actas", [])

st.markdown(
    """
    <style>
    .titulo-acta-reunion {
        text-align: center;
        font-size: 30px;
        font-weight: 800;
        margin-bottom: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="titulo-acta-reunion">ACTA DE REUNIÓN</div>', unsafe_allow_html=True)

acta_opciones = [int(x.get("acta_no") or 0) for x in actas]
acta_activa_default = int(datos.get("acta_activa") or acta_opciones[0])

col_nueva, col_acta = st.columns([1, 1])

with col_nueva:
    if st.button("➕ Nueva acta", type="primary", key="acta_reunion_nueva"):
        nueva_no = _crear_nueva_acta(acta_inicio, contrato_obra, contrato_interventoria)
        _guardar()
        st.session_state["acta_reunion_selector"] = nueva_no
        st.rerun()

with col_acta:
    acta_activa = st.selectbox(
        "ACTA DE REUNIÓN No.",
        options=acta_opciones,
        index=acta_opciones.index(acta_activa_default) if acta_activa_default in acta_opciones else 0,
        key="acta_reunion_selector",
    )
    datos["acta_activa"] = int(acta_activa)

acta = _obtener_acta_activa()
encabezado = _datos_encabezado(acta_inicio, contrato_obra, contrato_interventoria)

acta["contrato_obra_no"] = _primero_no_vacio(
    acta.get("contrato_obra_no"),
    encabezado["contrato_obra_no"],
)
acta["contratista"] = _primero_no_vacio(
    acta.get("contratista"),
    encabezado["contratista"],
)
acta["objeto_contrato_obra"] = _primero_no_vacio(
    acta.get("objeto_contrato_obra"),
    encabezado["objeto_contrato_obra"],
)
acta["interventor"] = _primero_no_vacio(
    acta.get("interventor"),
    encabezado["interventor"],
)

st.markdown("### CONSULTA DE ACTAS")
df_consulta = pd.DataFrame(
    [
        {
            "ACTA No.": int(x.get("acta_no") or 0),
            "Fecha": _parse_fecha(x.get("fecha")).strftime("%d/%m/%Y"),
            "Contrato obra": _texto(x.get("contrato_obra_no")),
            "Contratista": _texto(x.get("contratista")),
            "Interventor": _texto(x.get("interventor")),
        }
        for x in actas
    ]
)
st.dataframe(df_consulta, use_container_width=True, hide_index=True)

compromisos_iniciales = pd.DataFrame(
    _normalizar_compromisos(acta.get("compromisos", [])),
    columns=["COMPROMISOS PACTADOS", "RESPONSABLES", "FECHA DE CUMPLIMIENTO"],
)

participantes_iniciales = pd.DataFrame(
    _normalizar_participantes(acta.get("participantes", [])),
    columns=["NOMBRE DEL PARTICIPANTE", "CARGO", "EMPRESA / ENTIDAD"],
)

with st.form(key=f"form_acta_reunion_{acta_activa}", clear_on_submit=False):
    col1, col2 = st.columns(2)
    with col1:
        fecha_form = st.date_input(
            "FECHA",
            value=_parse_fecha(acta.get("fecha")),
            format="DD/MM/YYYY",
            key=f"acta_reunion_fecha_{acta_activa}",
        )
    with col2:
        st.text_input(
            "ACTA DE REUNIÓN No.",
            value=str(int(acta.get("acta_no") or 0)),
            disabled=True,
            key=f"acta_reunion_numero_{acta_activa}",
        )

    col3, col4 = st.columns(2)
    with col3:
        st.text_input(
            "CONTRATO DE OBRA No.",
            value=_texto(acta.get("contrato_obra_no")),
            disabled=True,
            key=f"acta_reunion_contrato_obra_{acta_activa}",
        )
    with col4:
        st.text_input(
            "CONTRATISTA",
            value=_texto(acta.get("contratista")),
            disabled=True,
            key=f"acta_reunion_contratista_{acta_activa}",
        )

    st.text_input(
        "OBJETO DEL CONTRATO DE OBRA",
        value=_texto(acta.get("objeto_contrato_obra")),
        disabled=True,
        key=f"acta_reunion_objeto_obra_{acta_activa}",
    )

    st.text_input(
        "INTERVENTOR",
        value=_texto(acta.get("interventor")),
        disabled=True,
        key=f"acta_reunion_interventor_{acta_activa}",
    )

    objetivos_form = st.text_area(
        "OBJETIVOS DE LA REUNIÓN",
        value=_texto(acta.get("objetivos_reunion")),
        height=140,
        key=f"acta_reunion_objetivos_{acta_activa}",
    )

    desarrollo_form = st.text_area(
        "DESARROLLO DE LA REUNIÓN",
        value=_texto(acta.get("desarrollo_reunion")),
        height=220,
        key=f"acta_reunion_desarrollo_{acta_activa}",
    )

    st.markdown("### COMPROMISOS PACTADOS")
    compromisos_editados = st.data_editor(
        compromisos_iniciales,
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic",
        key=f"acta_reunion_compromisos_{acta_activa}",
        column_config={
            "COMPROMISOS PACTADOS": st.column_config.TextColumn("COMPROMISOS PACTADOS"),
            "RESPONSABLES": st.column_config.TextColumn("RESPONSABLES"),
            "FECHA DE CUMPLIMIENTO": st.column_config.DateColumn(
                "FECHA DE CUMPLIMIENTO",
                format="DD/MM/YYYY",
            ),
        },
    )

    st.markdown(
        """
        1. Las decisiones tomadas en la presente Reunión, no pueden modificar ni modifican por sí solas el Contrato de Obra ni el contrato de Interventoría suscritos. En el evento de requerirse una modificación contractual debe surtirse de manera previa el trámite interno correspondiente.

        2. Se firma la presente Acta de Reunión bajo la responsabilidad expresa de quienes en ella intervienen, de conformidad con las obligaciones y funciones desempeñadas por cada uno de los mismos.

        **LA PRESENTE ACTA DE REUNIÓN ES LEÍDA EN SU INTEGRIDAD ANTES DE LA SUSCRIPCIÓN POR LOS PARTICIPANTES**
        """
    )
    
    st.markdown("### PARTICIPANTES")
    participantes_editados = st.data_editor(
        participantes_iniciales,
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic",
        key=f"acta_reunion_participantes_{acta_activa}",
        column_config={
            "NOMBRE DEL PARTICIPANTE": st.column_config.TextColumn("NOMBRE DEL PARTICIPANTE"),
            "CARGO": st.column_config.TextColumn("CARGO"),
            "EMPRESA / ENTIDAD": st.column_config.TextColumn("EMPRESA / ENTIDAD"),
        },
    )

    guardar_form = st.form_submit_button("💾 Guardar acta", use_container_width=True)

if guardar_form:
    acta["fecha"] = fecha_form.isoformat()
    acta["objetivos_reunion"] = _texto(objetivos_form)
    acta["desarrollo_reunion"] = _texto(desarrollo_form)
    acta["compromisos"] = _normalizar_compromisos(compromisos_editados.to_dict("records"))
    acta["participantes"] = _normalizar_participantes(participantes_editados.to_dict("records"))
    _guardar()
