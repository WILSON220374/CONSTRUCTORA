from datetime import date, datetime

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
        "FECHA DE CUMPLIMIENTO": date.today(),
        "RESPONSABLES": "",
    }


def _fila_participante_vacia():
    return {
        "NOMBRE DEL PARTICIPANTE": "",
        "CARGO": "",
        "EMPRESA / ENTIDAD": "",
        "FIRMA": "",
    }


def _normalizar_compromisos(rows):
    filas = []
    for fila in rows or []:
        base = _fila_compromiso_vacia()
        if isinstance(fila, dict):
            base["COMPROMISOS PACTADOS"] = _texto(fila.get("COMPROMISOS PACTADOS"))
            base["FECHA DE CUMPLIMIENTO"] = _parse_fecha(fila.get("FECHA DE CUMPLIMIENTO"))
            base["RESPONSABLES"] = _texto(fila.get("RESPONSABLES"))
        filas.append(base)

    while len(filas) < 1:
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
            base["FIRMA"] = _texto(fila.get("FIRMA"))
        filas.append(base)

    while len(filas) < 1:
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
        "lectura_acta_anterior": "",
        "temas_comite": "",
        "desarrollo_comite": "",
        "compromisos": _normalizar_compromisos([]),
        "fecha_proximo_comite": date.today().isoformat(),
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
        "lectura_acta_anterior": _texto(acta.get("lectura_acta_anterior")),
        "temas_comite": _texto(acta.get("temas_comite")),
        "desarrollo_comite": _texto(acta.get("desarrollo_comite")),
        "compromisos": _normalizar_compromisos(acta.get("compromisos", [])),
        "fecha_proximo_comite": _parse_fecha(acta.get("fecha_proximo_comite")).isoformat(),
        "participantes": _normalizar_participantes(acta.get("participantes", [])),
    }


def _inicializar_estado(acta_inicio, contrato_obra, contrato_interventoria):
    group_id_actual = _texto(st.session_state.get("group_id"))
    cache_group = _texto(st.session_state.get("_acta_comite_obra_group"))

    if cache_group != group_id_actual or "acta_comite_obra_datos" not in st.session_state:
        cargado = cargar_estado("acta_comite_obra") or {}
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

        st.session_state["acta_comite_obra_datos"] = {
            "actas": actas_normalizadas,
            "acta_activa": int(cargado.get("acta_activa") or actas_normalizadas[-1]["acta_no"]),
        }
        st.session_state["_acta_comite_obra_group"] = group_id_actual


def _guardar():
    guardar_estado("acta_comite_obra", st.session_state["acta_comite_obra_datos"])
    st.success("Acta de comité de obra guardada correctamente.")


def _obtener_acta_activa():
    datos = st.session_state["acta_comite_obra_datos"]
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
    datos = st.session_state["acta_comite_obra_datos"]
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

datos = st.session_state["acta_comite_obra_datos"]
actas = datos.get("actas", [])

st.markdown(
    """
    <style>
    .titulo-acta-comite {
        text-align: center;
        font-size: 30px;
        font-weight: 800;
        margin-bottom: 8px;
    }
    .subtitulo-acta-comite {
        text-align: left;
        font-size: 14px;
        font-style: italic;
        margin-bottom: 14px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="titulo-acta-comite">ACTA DE COMITÉ DE OBRA</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitulo-acta-comite">(Este formato aplica únicamente para Comité de Obra)</div>',
    unsafe_allow_html=True,
)

acta_opciones = [int(x.get("acta_no") or 0) for x in actas]
acta_activa_default = int(datos.get("acta_activa") or acta_opciones[0])

col_nueva, col_acta = st.columns([1, 1])

with col_nueva:
    if st.button("➕ Nueva acta", type="primary", key="acta_comite_nueva"):
        nueva_no = _crear_nueva_acta(acta_inicio, contrato_obra, contrato_interventoria)
        _guardar()
        st.session_state["acta_comite_selector"] = nueva_no
        st.rerun()

with col_acta:
    acta_activa = st.selectbox(
        "ACTA DE COMITÉ DE OBRA No.",
        options=acta_opciones,
        index=acta_opciones.index(acta_activa_default) if acta_activa_default in acta_opciones else 0,
        key="acta_comite_selector",
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
st.dataframe(df_consulta, width="stretch", hide_index=True)

compromisos_iniciales = pd.DataFrame(
    _normalizar_compromisos(acta.get("compromisos", [])),
    columns=["COMPROMISOS PACTADOS", "FECHA DE CUMPLIMIENTO", "RESPONSABLES"],
)

participantes_iniciales = pd.DataFrame(
    _normalizar_participantes(acta.get("participantes", [])),
    columns=["NOMBRE DEL PARTICIPANTE", "CARGO", "EMPRESA / ENTIDAD", "FIRMA"],
)

with st.form(key=f"form_acta_comite_obra_{acta_activa}", clear_on_submit=False):
    col1, col2 = st.columns(2)
    with col1:
        fecha_form = st.date_input(
            "FECHA",
            value=_parse_fecha(acta.get("fecha")),
            format="DD/MM/YYYY",
            key=f"acta_comite_fecha_{acta_activa}",
        )
    with col2:
        st.text_input(
            "ACTA DE COMITÉ DE OBRA No.",
            value=str(int(acta.get("acta_no") or 0)),
            disabled=True,
            key=f"acta_comite_numero_{acta_activa}",
        )

    col3, col4 = st.columns(2)
    with col3:
        st.text_input(
            "CONTRATO DE OBRA No.",
            value=_texto(acta.get("contrato_obra_no")),
            disabled=True,
            key=f"acta_comite_contrato_obra_{acta_activa}",
        )
    with col4:
        st.text_input(
            "CONTRATISTA",
            value=_texto(acta.get("contratista")),
            disabled=True,
            key=f"acta_comite_contratista_{acta_activa}",
        )

    col5, col6 = st.columns(2)
    with col5:
        st.text_input(
            "OBJETO DEL CONTRATO DE OBRA",
            value=_texto(acta.get("objeto_contrato_obra")),
            disabled=True,
            key=f"acta_comite_objeto_obra_{acta_activa}",
        )
    with col6:
        st.text_input(
            "INTERVENTOR",
            value=_texto(acta.get("interventor")),
            disabled=True,
            key=f"acta_comite_interventor_{acta_activa}",
        )

    lectura_acta_anterior_form = st.text_area(
        "LECTURA ACTA ANTERIOR Y VERIFICACIÓN DE CUMPLIMIENTO DE COMPROMISOS",
        value=_texto(acta.get("lectura_acta_anterior")),
        height=180,
        key=f"acta_comite_lectura_anterior_{acta_activa}",
    )

    temas_comite_form = st.text_area(
        "TEMAS A DESARROLLAR EN EL PRESENTE COMITÉ DE OBRA",
        value=_texto(acta.get("temas_comite")),
        height=180,
        key=f"acta_comite_temas_{acta_activa}",
    )

    desarrollo_comite_form = st.text_area(
        "DESARROLLO DEL COMITÉ DE OBRA",
        value=_texto(acta.get("desarrollo_comite")),
        height=260,
        key=f"acta_comite_desarrollo_{acta_activa}",
    )

    st.markdown("### COMPROMISOS PACTADOS")
    compromisos_editados = st.data_editor(
        compromisos_iniciales,
        hide_index=True,
        width="stretch",
        num_rows="dynamic",
        key=f"acta_comite_compromisos_{acta_activa}",
        column_config={
            "COMPROMISOS PACTADOS": st.column_config.TextColumn("COMPROMISOS PACTADOS"),
            "FECHA DE CUMPLIMIENTO": st.column_config.DateColumn(
                "FECHA DE CUMPLIMIENTO",
                format="DD/MM/YYYY",
            ),
            "RESPONSABLES": st.column_config.TextColumn("RESPONSABLES"),
        },
    )

    fecha_proximo_comite_form = st.date_input(
        "FECHA PRÓXIMO COMITÉ DE OBRA",
        value=_parse_fecha(acta.get("fecha_proximo_comite")),
        format="DD/MM/YYYY",
        key=f"acta_comite_fecha_proximo_{acta_activa}",
    )

    st.markdown("### NOTAS")
    st.markdown(
        """
        1. Corresponde a la Interventoría ejercer el control y vigilancia de la obra, en consecuencia es el Interventor quien dirige los Comités de Obra.

        2. Las decisiones tomadas en el presente Comité de Obra, no pueden modificar ni modifican por si solas el Contrato de Obra ni el contrato de Interventoría suscritos. En el evento de requerirse una modificación contractual debe surtirse de manera previa el trámite interno correspondiente.

        3. Se firma la presente Acta de Comité de Obra bajo la responsabilidad expresa de quienes en él intervienen, de conformidad con las obligaciones y funciones desempeñadas por cada uno de los mismos.
        """
    )

    st.markdown(
        "**LA PRESENTE ACTA DE COMITÉ DE OBRA ES LEÍDA EN SU INTEGRIDAD ANTES DE LA SUSCRIPCIÓN POR LOS PARTICIPANTES:**"
    )

    st.markdown("### PARTICIPANTES")
    participantes_editados = st.data_editor(
        participantes_iniciales,
        hide_index=True,
        width="stretch",
        num_rows="dynamic",
        key=f"acta_comite_participantes_{acta_activa}",
        column_config={
            "NOMBRE DEL PARTICIPANTE": st.column_config.TextColumn("NOMBRE DEL PARTICIPANTE"),
            "CARGO": st.column_config.TextColumn("CARGO"),
            "EMPRESA / ENTIDAD": st.column_config.TextColumn("EMPRESA / ENTIDAD"),
            "FIRMA": st.column_config.TextColumn("FIRMA"),
        },
    )

    guardar_form = st.form_submit_button("💾 Guardar acta", use_container_width=True)

if guardar_form:
    acta["fecha"] = fecha_form.isoformat()
    acta["lectura_acta_anterior"] = _texto(lectura_acta_anterior_form)
    acta["temas_comite"] = _texto(temas_comite_form)
    acta["desarrollo_comite"] = _texto(desarrollo_comite_form)
    acta["compromisos"] = _normalizar_compromisos(compromisos_editados.to_dict("records"))
    acta["fecha_proximo_comite"] = fecha_proximo_comite_form.isoformat()
    acta["participantes"] = _normalizar_participantes(participantes_editados.to_dict("records"))
    _guardar()
