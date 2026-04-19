import base64
import mimetypes
from datetime import date, datetime
from io import BytesIO

import pandas as pd
import streamlit as st
from docx import Document
from docx.shared import Inches

from supabase_state import cargar_estado
from supabase_state import guardar_estado as guardar_estado_bd


CLAVE_GUARDADO = "bitacora_obra"
MIN_FILAS_ACTIVIDADES = 1


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


def _safe_float(valor, default=0.0) -> float:
    try:
        if valor is None or valor == "":
            return float(default)
        txt = str(valor).strip().replace("$", "").replace(" ", "")
        txt = txt.replace(".", "").replace(",", ".")
        return float(txt)
    except Exception:
        return float(default)


def _leer_estado_directo(clave: str) -> dict:
    datos = cargar_estado(clave) or {}
    return datos if isinstance(datos, dict) else {}


def _leer_acta_inicio() -> dict:
    return _leer_estado_directo("acta_inicio_obra")


def _leer_contrato_obra() -> dict:
    return _leer_estado_directo("contrato_obra")


def _leer_presupuesto_obra() -> dict:
    return _leer_estado_directo("presupuesto_obra")


def _primero_no_vacio(*valores):
    for valor in valores:
        txt = _texto(valor)
        if txt:
            return txt
    return ""


def _construir_catalogo_presupuesto(presupuesto_obra: dict):
    catalogo = []
    mapa = {}

    if not isinstance(presupuesto_obra, dict):
        return catalogo, mapa

    tablas = presupuesto_obra.get("__tablas__", {}) or {}
    grupos = tablas.get("grupos_presupuesto_obra", []) or []

    for grupo in grupos:
        if not isinstance(grupo, dict):
            continue

        for fila in grupo.get("rows", []) or []:
            if not isinstance(fila, dict):
                continue

            item_no = _texto(fila.get("ITEM"))
            descripcion = _texto(fila.get("DESCRIPCIÓN"))
            valor_total = _safe_float(fila.get("VR TOTAL"), 0.0)

            if not descripcion:
                continue

            registro = {
                "descripcion": descripcion,
                "item_no": item_no,
                "valor_referencia": valor_total,
            }

            if descripcion not in mapa:
                catalogo.append(registro)
                mapa[descripcion] = registro

    resumen = tablas.get("resumen_presupuesto_obra", {}) or {}
    otros_costos_indirectos = resumen.get("otros_costos_indirectos", []) or []

    consecutivo_ci = 1
    for fila in otros_costos_indirectos:
        if not isinstance(fila, dict):
            continue

        descripcion = _texto(fila.get("nombre"))
        valor_total = _safe_float(fila.get("valor"), 0.0)

        if not descripcion or descripcion.upper() == "INTERVENTORIA":
            continue

        registro = {
            "descripcion": descripcion,
            "item_no": f"CI-{consecutivo_ci}",
            "valor_referencia": valor_total,
        }
        consecutivo_ci += 1

        if descripcion not in mapa:
            catalogo.append(registro)
            mapa[descripcion] = registro

    catalogo = sorted(catalogo, key=lambda x: (x["descripcion"], x["item_no"]))
    return catalogo, mapa


def _fila_actividad_vacia():
    return {
        "ÍTEM No.": "",
        "DESCRIPCIÓN DEL ÍTEM": "",
    }


def _normalizar_actividades(rows):
    filas = []
    for fila in rows or []:
        base = _fila_actividad_vacia()
        if isinstance(fila, dict):
            for k in base.keys():
                if k in fila:
                    base[k] = fila.get(k)
        filas.append(base)

    while len(filas) < MIN_FILAS_ACTIVIDADES:
        filas.append(_fila_actividad_vacia())

    return filas


def _incidencia_vacia(nuevo_folio: int, acta_inicio: dict, contrato_obra: dict):
    numero_contrato = _primero_no_vacio(
        acta_inicio.get("numero_contrato"),
        contrato_obra.get("numero_contrato"),
    )
    contratista = _primero_no_vacio(
        acta_inicio.get("nombre_firma_contratista"),
        contrato_obra.get("nombre_contratista"),
    )
    interventor = _primero_no_vacio(
        acta_inicio.get("nombre_firma_interventor"),
        contrato_obra.get("nombre_interventor"),
        contrato_obra.get("nombre_supervisor"),
    )

    return {
        "folio": int(nuevo_folio),
        "fecha": date.today().isoformat(),
        "numero_contrato": numero_contrato,
        "contratista": contratista,
        "interventor": interventor,
        "anotaciones": "",
        "actividades": _normalizar_actividades([]),
        "imagenes": [],
    }


def _normalizar_incidencia(incidencia, acta_inicio, contrato_obra):
    if not isinstance(incidencia, dict):
        incidencia = {}

    numero_contrato = _primero_no_vacio(
        incidencia.get("numero_contrato"),
        acta_inicio.get("numero_contrato"),
        contrato_obra.get("numero_contrato"),
    )
    contratista = _primero_no_vacio(
        incidencia.get("contratista"),
        acta_inicio.get("nombre_firma_contratista"),
        contrato_obra.get("nombre_contratista"),
    )
    interventor = _primero_no_vacio(
        incidencia.get("interventor"),
        acta_inicio.get("nombre_firma_interventor"),
        contrato_obra.get("nombre_interventor"),
        contrato_obra.get("nombre_supervisor"),
    )

    return {
        "folio": int(incidencia.get("folio") or 1),
        "fecha": _parse_fecha(incidencia.get("fecha")).isoformat(),
        "numero_contrato": numero_contrato,
        "contratista": contratista,
        "interventor": interventor,
        "anotaciones": _texto(incidencia.get("anotaciones")),
        "actividades": _normalizar_actividades(incidencia.get("actividades", [])),
        "imagenes": incidencia.get("imagenes", []) if isinstance(incidencia.get("imagenes"), list) else [],
    }


def _inicializar_estado(acta_inicio, contrato_obra):
    group_id_actual = _texto(st.session_state.get("group_id"))
    cache_group = _texto(st.session_state.get("_bitacora_obra_group"))

    if cache_group != group_id_actual or "bitacora_obra_datos" not in st.session_state:
        cargado = cargar_estado(CLAVE_GUARDADO) or {}
        if not isinstance(cargado, dict):
            cargado = {}

        incidencias = cargado.get("incidencias", [])
        if not isinstance(incidencias, list):
            incidencias = []

        incidencias_normalizadas = [
            _normalizar_incidencia(x, acta_inicio, contrato_obra)
            for x in incidencias
        ]

        if not incidencias_normalizadas:
            incidencias_normalizadas = [
                _incidencia_vacia(1, acta_inicio, contrato_obra)
            ]

        st.session_state["bitacora_obra_datos"] = {
            "incidencias": incidencias_normalizadas,
            "folio_activo": int(cargado.get("folio_activo") or incidencias_normalizadas[-1]["folio"]),
        }
        st.session_state["_bitacora_obra_group"] = group_id_actual


def _guardar():
    guardar_estado(CLAVE_GUARDADO, st.session_state["bitacora_obra_datos"])
    st.success("Bitácora de obra guardada correctamente.")


def _obtener_incidencia_activa():
    datos = st.session_state["bitacora_obra_datos"]
    incidencias = datos.get("incidencias", [])
    folio_activo = int(datos.get("folio_activo") or 1)

    for incidencia in incidencias:
        if int(incidencia.get("folio") or 0) == folio_activo:
            return incidencia

    if incidencias:
        datos["folio_activo"] = int(incidencias[0]["folio"])
        return incidencias[0]

    nueva = _incidencia_vacia(1, _leer_acta_inicio(), _leer_contrato_obra())
    datos["incidencias"] = [nueva]
    datos["folio_activo"] = 1
    return nueva


def _crear_nueva_incidencia(acta_inicio, contrato_obra):
    datos = st.session_state["bitacora_obra_datos"]
    incidencias = datos.get("incidencias", [])
    ultimo_folio = max([int(x.get("folio") or 0) for x in incidencias], default=0)
    nueva = _incidencia_vacia(ultimo_folio + 1, acta_inicio, contrato_obra)
    incidencias.append(nueva)
    datos["folio_activo"] = nuevo_folio = int(nueva["folio"])
    return nuevo_folio


def _recalcular_actividades(incidencia, mapa_catalogo):
    actividades_base = _normalizar_actividades(incidencia.get("actividades", []))
    actividades_out = []

def _recalcular_actividades(incidencia, mapa_catalogo):
    actividades_base = _normalizar_actividades(incidencia.get("actividades", []))
    actividades_out = []

    for fila in actividades_base:
        descripcion = _texto(fila.get("DESCRIPCIÓN DEL ÍTEM"))
        fila_nueva = _fila_actividad_vacia()
        fila_nueva["DESCRIPCIÓN DEL ÍTEM"] = descripcion

        if descripcion and descripcion in mapa_catalogo:
            fila_nueva["ÍTEM No."] = _texto(mapa_catalogo[descripcion].get("item_no"))

        actividades_out.append(fila_nueva)

    incidencia["actividades"] = actividades_out


def _archivo_a_base64(uploaded_file):
    contenido = uploaded_file.getvalue()
    mime = uploaded_file.type or mimetypes.guess_type(uploaded_file.name)[0] or "application/octet-stream"
    return {
        "nombre": uploaded_file.name,
        "mime": mime,
        "data": base64.b64encode(contenido).decode("utf-8"),
    }


def _bytes_desde_imagen(imagen):
    try:
        return base64.b64decode(imagen.get("data", ""))
    except Exception:
        return b""


acta_inicio = _leer_acta_inicio()
contrato_obra = _leer_contrato_obra()
presupuesto_obra = _leer_presupuesto_obra()
catalogo, mapa_catalogo = _construir_catalogo_presupuesto(presupuesto_obra)

_inicializar_estado(acta_inicio, contrato_obra)

datos = st.session_state["bitacora_obra_datos"]
incidencias = datos.get("incidencias", [])

st.markdown(
    """
    <style>
    .bitacora-titulo {
        text-align: center;
        font-size: 30px;
        font-weight: 800;
        margin-bottom: 8px;
    }
    .bitacora-subtitulo {
        text-align: center;
        font-size: 15px;
        font-weight: 600;
        margin-bottom: 18px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

folio_opciones = [int(x.get("folio") or 0) for x in incidencias]
folio_activo_default = int(datos.get("folio_activo") or folio_opciones[0])

st.markdown('<div class="bitacora-titulo">BITÁCORA DE OBRA</div>', unsafe_allow_html=True)
st.markdown('<div class="bitacora-subtitulo">Registro diario de obra</div>', unsafe_allow_html=True)

col_nueva, col_guardar, col_selector, col_fecha = st.columns([1, 1, 1, 1])

with col_nueva:
    if st.button("➕ Nueva incidencia", type="primary", key="bitacora_nueva_incidencia"):
        nuevo_folio = _crear_nueva_incidencia(acta_inicio, contrato_obra)
        _guardar()
        st.session_state["bitacora_selector_folio"] = nuevo_folio
        st.rerun()

with col_guardar:
    if st.button("💾 Guardar bitácora", key="bitacora_guardar_principal"):
        _guardar()

with col_selector:
    folio_activo = st.selectbox(
        "No. de Folio",
        options=folio_opciones,
        index=folio_opciones.index(folio_activo_default) if folio_activo_default in folio_opciones else 0,
        key="bitacora_selector_folio",
    )
    datos["folio_activo"] = int(folio_activo)

st.markdown("### CONSULTA DE INCIDENCIAS")

df_consulta = pd.DataFrame(
    [
        {
            "No. de Folio": int(x.get("folio") or 0),
            "Fecha": _parse_fecha(x.get("fecha")).strftime("%d/%m/%Y"),
            "No. de contrato": _texto(x.get("numero_contrato")),
            "Contratista": _texto(x.get("contratista")),
            "Interventor": _texto(x.get("interventor")),
        }
        for x in incidencias
    ]
)

st.dataframe(df_consulta, use_container_width=True, hide_index=True)

incidencia = _obtener_incidencia_activa()
incidencia["numero_contrato"] = _primero_no_vacio(
    incidencia.get("numero_contrato"),
    acta_inicio.get("numero_contrato"),
    contrato_obra.get("numero_contrato"),
)
incidencia["contratista"] = _primero_no_vacio(
    incidencia.get("contratista"),
    acta_inicio.get("nombre_firma_contratista"),
    contrato_obra.get("nombre_contratista"),
)
incidencia["interventor"] = _primero_no_vacio(
    incidencia.get("interventor"),
    acta_inicio.get("nombre_firma_interventor"),
    contrato_obra.get("nombre_interventor"),
    contrato_obra.get("nombre_supervisor"),
)

with col_fecha:
    incidencia["fecha"] = st.date_input(
        "FECHA",
        value=_parse_fecha(incidencia.get("fecha")),
        format="DD/MM/YYYY",
        key=f"bitacora_fecha_{folio_activo}",
    ).isoformat()

col1, col2 = st.columns(2)
with col1:
    st.text_input(
        "No. de contrato",
        value=_texto(incidencia.get("numero_contrato")),
        disabled=True,
        key=f"bitacora_numero_contrato_{folio_activo}",
    )
with col2:
    st.text_input(
        "Contratista",
        value=_texto(incidencia.get("contratista")),
        disabled=True,
        key=f"bitacora_contratista_{folio_activo}",
    )

st.text_input(
    "Interventor",
    value=_texto(incidencia.get("interventor")),
    disabled=True,
    key=f"bitacora_interventor_{folio_activo}",
)

st.markdown("### ACTIVIDADES A DESARROLLAR")

_descripciones_catalogo = [x["descripcion"] for x in catalogo]
_recalcular_actividades(incidencia, mapa_catalogo)

df_actividades = pd.DataFrame(
    incidencia.get("actividades", []),
    columns=["ÍTEM No.", "DESCRIPCIÓN DEL ÍTEM"],
)

df_editado = st.data_editor(
    df_actividades,
    num_rows="dynamic",
    hide_index=True,
    width="stretch",
    column_config={
        "ÍTEM No.": st.column_config.TextColumn("ÍTEM No.", disabled=True),
        "DESCRIPCIÓN DEL ÍTEM": st.column_config.SelectboxColumn(
            "DESCRIPCIÓN DEL ÍTEM",
            options=_descripciones_catalogo,
            required=False,
        ),
    },
    key=f"bitacora_actividades_{folio_activo}",
)

incidencia["actividades"] = df_editado.to_dict("records")
_recalcular_actividades(incidencia, mapa_catalogo)

st.markdown("### ANOTACIONES")
incidencia["anotaciones"] = st.text_area(
    "ANOTACIONES",
    value=_texto(incidencia.get("anotaciones")),
    height=180,
    label_visibility="collapsed",
    key=f"bitacora_anotaciones_{folio_activo}",
)

st.markdown("### REGISTRO FOTOGRÁFICO")
archivos = st.file_uploader(
    "Cargar imagen",
    type=["png", "jpg", "jpeg", "webp"],
    accept_multiple_files=True,
    key=f"bitacora_imagenes_uploader_{folio_activo}",
)

if archivos:
    nombres_existentes = {img.get("nombre") for img in incidencia.get("imagenes", []) if isinstance(img, dict)}
    for archivo in archivos:
        if archivo.name not in nombres_existentes:
            incidencia.setdefault("imagenes", []).append(_archivo_a_base64(archivo))

imagenes = incidencia.get("imagenes", [])
if imagenes:
    cols = st.columns(3)
    for idx, imagen in enumerate(imagenes):
        with cols[idx % 3]:
            contenido = _bytes_desde_imagen(imagen)
            if contenido:
                st.image(contenido, use_container_width=True)
            st.caption(_texto(imagen.get("nombre")))
            if st.button("Eliminar", key=f"bitacora_eliminar_imagen_{folio_activo}_{idx}"):
                incidencia["imagenes"].pop(idx)
                _guardar()
                st.rerun()
else:
    st.info("No hay imágenes cargadas para este folio.")

with st.container(border=True):
    st.markdown("### RESPONSABLES DE LA OBRA")
    c1, c2 = st.columns(2)
    with c1:
        st.text_input(
            "CONTRATISTA RESPONSABLE",
            value=_texto(incidencia.get("contratista")),
            disabled=True,
            key=f"bitacora_responsable_contratista_{folio_activo}",
        )
    with c2:
        st.text_input(
            "INTERVENTOR RESPONSABLE",
            value=_texto(incidencia.get("interventor")),
            disabled=True,
            key=f"bitacora_responsable_interventor_{folio_activo}",
            )

_guardar()
