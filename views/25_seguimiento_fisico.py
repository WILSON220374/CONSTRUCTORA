from datetime import date, datetime, timedelta
import re

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from supabase_state import cargar_estado
from supabase_state import guardar_estado as guardar_estado_bd


# ==========================================================
# Persistencia
# ==========================================================
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


# ==========================================================
# Helpers generales
# ==========================================================
def _texto(valor):
    if valor is None:
        return ""
    return str(valor).strip()


def _key_codigo_natural(value):
    partes = []
    for chunk in _texto(value).split("."):
        try:
            partes.append(int(chunk))
        except Exception:
            partes.append(chunk)
    return tuple(partes)


def _safe_float(valor, default=0.0):
    try:
        if valor is None or valor == "":
            return None if default is None else float(default)
        if isinstance(valor, (int, float)):
            return float(valor)
        txt = str(valor).strip().replace("$", "").replace(" ", "")
        if "," in txt and "." in txt:
            txt = txt.replace(".", "").replace(",", ".")
        elif "," in txt:
            txt = txt.replace(",", ".")
        else:
            txt = txt

        return float(txt)
    except Exception:
        return None if default is None else float(default)


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


def _primero_no_vacio(*valores):
    for valor in valores:
        txt = _texto(valor)
        if txt:
            return txt
    return ""

def _es_interventoria(descripcion):
    return _texto(descripcion).upper() == "INTERVENTORIA"


def _item_visible_flujo(fila, consecutivo_indirecto=0):
    item = _texto(fila.get("ITEM"))
    tipo = _texto(fila.get("TIPO")).upper()
    descripcion = _primero_no_vacio(
        fila.get("DESCRIPCIÓN"),
        fila.get("DESCRIPCION"),
        fila.get("DESCRIPCIÓN DEL ÍTEM"),
        fila.get("DESCRIPCION DEL ITEM"),
    )

    if tipo == "INDIRECTO" and not item:
        return f"CI-{consecutivo_indirecto}" if consecutivo_indirecto else ""

    return item

def _leer_estado_directo(clave):
    datos = cargar_estado(clave) or {}
    return datos if isinstance(datos, dict) else {}


def _leer_acta_inicio():
    return _leer_estado_directo("acta_inicio_obra")


def _leer_contrato_obra():
    return _leer_estado_directo("contrato_obra")


def _leer_flujo_fondos():
    return _leer_estado_directo("flujo_fondos")


def _fecha_inicio_desde_fuentes(acta_inicio):
    return _parse_fecha(
        _primero_no_vacio(
            acta_inicio.get("fecha_inicio"),
            acta_inicio.get("fecha_presente_acta"),
        )
    )


def _valor_contrato_desde_contrato_obra(contrato_obra):
    for valor in [
        contrato_obra.get("valor_total_numeros"),
        contrato_obra.get("valor_contrato"),
        contrato_obra.get("valor"),
    ]:
        numero = _safe_float(valor, 0.0)
        if numero > 0:
            return numero
    return 0.0

# ==========================================================
# Programado desde flujo de fondos
# ==========================================================
def _programado_desde_flujo(flujo_fondos, fecha_corte, fecha_inicio):
    tablas = flujo_fondos.get("__tablas__", {})
    resumen = tablas.get("df_resumen", [])

    if not isinstance(resumen, list) or not resumen:
        return 0.0, 0.0

    fila_acumulado = {}
    fila_pct = {}

    for fila in resumen:
        if not isinstance(fila, dict):
            continue

        concepto = _texto(fila.get("CONCEPTO")).upper()

        if concepto == "ACUMULADO":
            fila_acumulado = fila
        if concepto == "% ACUMULADO":
            fila_pct = fila

    if not fila_acumulado or not fila_pct:
        return 0.0, 0.0

    periodos = []
    for columna in fila_acumulado.keys():
        nombre = _texto(columna)
        if nombre.startswith("Periodo "):
            try:
                numero = int(nombre.replace("Periodo ", "").strip())
                periodos.append((numero, nombre))
            except Exception:
                continue

    if not periodos:
        return 0.0, 0.0

    periodos = sorted(periodos, key=lambda x: x[0])
    fecha_corte = _parse_fecha(fecha_corte)
    fecha_inicio = _parse_fecha(fecha_inicio)
    dias_transcurridos = (fecha_corte - fecha_inicio).days + 1

    if dias_transcurridos <= 0:
        return 0.0, 0.0

    periodo_actual = int((dias_transcurridos - 1) // 30) + 1
    dia_periodo = ((dias_transcurridos - 1) % 30) + 1
    factor_periodo = dia_periodo / 30.0
    periodo_actual = min(periodo_actual, periodos[-1][0])

    nombre_actual = f"Periodo {periodo_actual}"
    nombre_anterior = f"Periodo {periodo_actual - 1}"

    valor_anterior = _safe_float(fila_acumulado.get(nombre_anterior), 0.0) if periodo_actual > 1 else 0.0
    pct_anterior = _safe_float(fila_pct.get(nombre_anterior), 0.0) if periodo_actual > 1 else 0.0

    valor_actual = _safe_float(fila_acumulado.get(nombre_actual), valor_anterior)
    pct_actual = _safe_float(fila_pct.get(nombre_actual), pct_anterior)

    valor_programado = valor_anterior + ((valor_actual - valor_anterior) * factor_periodo)
    pct_programado = pct_anterior + ((pct_actual - pct_anterior) * factor_periodo)

    return round(pct_programado, 4), round(valor_programado, 2)


def _programado_actividad_desde_flujo(flujo_fondos, item, fecha_corte, fecha_inicio):
    tablas = flujo_fondos.get("__tablas__", {})
    programa = tablas.get("df_calculado", [])

    if not isinstance(programa, list) or not programa:
        return 0.0, 0.0

    item = _texto(item)
    fila_item = {}

    programa_obra = _tabla_programa_obra_desde_flujo(flujo_fondos)
    mapa_codigo_descripcion = {}
    consecutivo_indirecto = 1

    for fila in programa_obra:
        if not isinstance(fila, dict):
            continue

        tipo = _texto(fila.get("TIPO")).upper()
        descripcion = _primero_no_vacio(
            fila.get("DESCRIPCIÓN"),
            fila.get("DESCRIPCION"),
            fila.get("DESCRIPCIÓN DEL ÍTEM"),
            fila.get("DESCRIPCION DEL ITEM"),
        )

        if tipo == "INDIRECTO":
            if _es_interventoria(descripcion):
                continue
            codigo_visible = _item_visible_flujo(fila, consecutivo_indirecto)
            consecutivo_indirecto += 1
        else:
            codigo_visible = _texto(fila.get("ITEM"))

        if codigo_visible:
            mapa_codigo_descripcion[codigo_visible] = descripcion

    descripcion_buscada = mapa_codigo_descripcion.get(item, "")

    for fila in programa:
        if not isinstance(fila, dict):
            continue

        if _texto(fila.get("ITEM")) == item:
            fila_item = fila
            break

        if descripcion_buscada and _texto(fila.get("TIPO")).upper() == "INDIRECTO":
            descripcion_fila = _primero_no_vacio(
                fila.get("DESCRIPCIÓN"),
                fila.get("DESCRIPCION"),
            )
            if descripcion_fila == descripcion_buscada:
                fila_item = fila
                break

    if not fila_item:
        return 0.0, 0.0

    fila_programa_obra = {}
    consecutivo_indirecto = 1

    for fila in programa_obra:
        if not isinstance(fila, dict):
            continue

        tipo = _texto(fila.get("TIPO")).upper()
        descripcion = _primero_no_vacio(
            fila.get("DESCRIPCIÓN"),
            fila.get("DESCRIPCION"),
            fila.get("DESCRIPCIÓN DEL ÍTEM"),
            fila.get("DESCRIPCION DEL ITEM"),
        )

        if tipo == "INDIRECTO":
            if _es_interventoria(descripcion):
                continue
            codigo_visible = _item_visible_flujo(fila, consecutivo_indirecto)
            consecutivo_indirecto += 1
        else:
            codigo_visible = _texto(fila.get("ITEM"))

        if codigo_visible == item:
            fila_programa_obra = fila
            break

    valor_total_item = _safe_float(
        _primero_no_vacio(
            fila_programa_obra.get("VALOR CON AIU"),
            fila_programa_obra.get("VALOR TOTAL CON AIU"),
            fila_item.get("VALOR CON AIU"),
        ),
        0.0,
    )
    periodos = []
    for columna in fila_item.keys():
        nombre = _texto(columna)
        if nombre.startswith("Periodo ") and nombre.endswith(" $"):
            try:
                numero = int(nombre.replace("Periodo ", "").replace(" $", "").strip())
                periodos.append((numero, nombre))
            except Exception:
                continue

    if not periodos or valor_total_item <= 0:
        return 0.0, 0.0

    periodos = sorted(periodos, key=lambda x: x[0])
    fecha_corte = _parse_fecha(fecha_corte)
    fecha_inicio = _parse_fecha(fecha_inicio)
    dias_transcurridos = (fecha_corte - fecha_inicio).days + 1

    if dias_transcurridos <= 0:
        return 0.0, 0.0

    ultimo_periodo = periodos[-1][0]

    periodo_calculado = int((dias_transcurridos - 1) // 30) + 1

    if periodo_calculado > ultimo_periodo:
        return 100.0, round(valor_total_item, 2)

    periodo_actual = periodo_calculado
    dia_periodo = ((dias_transcurridos - 1) % 30) + 1
    factor_periodo = dia_periodo / 30.0

    valor_anterior = 0.0
    for numero, columna in periodos:
        if numero < periodo_actual:
            valor_anterior += _safe_float(fila_item.get(columna), 0.0)

    columna_actual = f"Periodo {periodo_actual} $"
    valor_mes_actual = _safe_float(fila_item.get(columna_actual), 0.0)

    valor_programado_base = valor_anterior + (valor_mes_actual * factor_periodo)
    pct_programado = (valor_programado_base / valor_total_item) * 100.0
    pct_programado = max(0.0, min(100.0, pct_programado))
    pct_programado = round(pct_programado, 4)

    if pct_programado >= 100.0:
        return 100.0, round(valor_total_item, 2)

    valor_programado = (pct_programado / 100.0) * valor_total_item

    return pct_programado, round(valor_programado, 2)

# ==========================================================
# Filas y normalizadores
# ==========================================================
def _fila_avance_general_vacia():
    return {
        "% EJECUTADO": 0.0,
        "$ EJECUTADO": 0.0,
        "% PROGRAMADO": 0.0,
        "$ PROGRAMADO": 0.0,
    }


def _fila_avance_actividad_vacia():
    return {
        "ITEM": "",
        "DESCRIPCIÓN": "",
        "% EJECUTADO": 0.0,
        "$ EJECUTADO": 0.0,
        "% PROGRAMADO": 0.0,
        "$ PROGRAMADO": 0.0,
    }


def _normalizar_avance_general(rows):
    filas = []
    for fila in rows or []:
        base = _fila_avance_general_vacia()
        if isinstance(fila, dict):
            base["% EJECUTADO"] = _safe_float(fila.get("% EJECUTADO"), 0.0)
            base["$ EJECUTADO"] = _safe_float(fila.get("$ EJECUTADO"), 0.0)
            base["% PROGRAMADO"] = _safe_float(fila.get("% PROGRAMADO"), 0.0)
            base["$ PROGRAMADO"] = _safe_float(fila.get("$ PROGRAMADO"), 0.0)
        filas.append(base)

    if not filas:
        filas.append(_fila_avance_general_vacia())

    return filas[:1]


def _normalizar_avance_actividad(rows):
    filas = []
    for fila in rows or []:
        base = _fila_avance_actividad_vacia()
        if isinstance(fila, dict):
            base["ITEM"] = _texto(fila.get("ITEM"))
            base["DESCRIPCIÓN"] = _texto(fila.get("DESCRIPCIÓN"))
            base["% EJECUTADO"] = _safe_float(fila.get("% EJECUTADO"), 0.0)
            base["$ EJECUTADO"] = _safe_float(fila.get("$ EJECUTADO"), 0.0)
            base["% PROGRAMADO"] = _safe_float(fila.get("% PROGRAMADO"), 0.0)
            base["$ PROGRAMADO"] = _safe_float(fila.get("$ PROGRAMADO"), 0.0)
        if _texto(base.get("ITEM")):
            filas.append(base)

    return filas


def _mapa_programa_obra_desde_flujo(flujo_fondos):
    programa = _tabla_programa_obra_desde_flujo(flujo_fondos)
    mapa = {}
    consecutivo_indirecto = 1

    for fila in programa:
        if not isinstance(fila, dict):
            continue

        tipo = _texto(fila.get("TIPO")).upper()
        descripcion = _primero_no_vacio(
            fila.get("DESCRIPCIÓN"),
            fila.get("DESCRIPCION"),
            fila.get("DESCRIPCIÓN DEL ÍTEM"),
            fila.get("DESCRIPCION DEL ITEM"),
        )

        if tipo == "INDIRECTO":
            if _es_interventoria(descripcion):
                continue
            item = _item_visible_flujo(fila, consecutivo_indirecto)
            consecutivo_indirecto += 1
        else:
            item = _texto(fila.get("ITEM"))

        if not item:
            continue

        mapa[item] = {
            "DESCRIPCIÓN": descripcion,
            "UNIDAD": _primero_no_vacio(
                fila.get("UNIDAD"),
                fila.get("unidad"),
                fila.get("UND"),
                fila.get("und"),
            ) or "GLOBAL",
            "CANTIDAD": _safe_float(
                fila.get(
                    "CANTIDAD TOTAL",
                    fila.get("CANTIDAD", fila.get("CANT", fila.get("cantidad", 1.0))),
                ),
                1.0,
            ),
        }

    return mapa

    return mapa


def _recalcular_corte(corte, flujo_fondos, fecha_inicio, mapa_items):
    fecha_corte = _parse_fecha(corte.get("fecha_corte"))

    avance_general = _normalizar_avance_general(corte.get("avance_general", []))
    pct_general, valor_general = _programado_desde_flujo(flujo_fondos, fecha_corte, fecha_inicio)

    for fila in avance_general:
        fila["% PROGRAMADO"] = pct_general
        fila["$ PROGRAMADO"] = valor_general

    avance_actividad = _normalizar_avance_actividad(corte.get("avance_actividad", []))

    for fila in avance_actividad:
        item = _texto(fila.get("ITEM"))
        fila["DESCRIPCIÓN"] = mapa_items.get(item, _texto(fila.get("DESCRIPCIÓN")))

        pct_programado, valor_programado = _programado_actividad_desde_flujo(
            flujo_fondos,
            item,
            fecha_corte,
            fecha_inicio,
        )
        fila["% PROGRAMADO"] = pct_programado
        fila["$ PROGRAMADO"] = valor_programado

    return {
        "fecha_corte": fecha_corte,
        "avance_general": avance_general,
        "avance_actividad": avance_actividad,
    }


def _corte_vacio(fecha_corte):
    return {
        "fecha_corte": _parse_fecha(fecha_corte),
        "avance_general": [_fila_avance_general_vacia()],
        "avance_actividad": [],
    }


# ==========================================================
# Estado principal
# ==========================================================
def _inicializar_estado():
    group_id_actual = _texto(st.session_state.get("group_id"))
    cache_group = _texto(st.session_state.get("_seguimiento_fisico_group"))

    if cache_group != group_id_actual or "seguimiento_fisico_datos" not in st.session_state:
        cargado = cargar_estado("seguimiento_fisico") or {}
        if not isinstance(cargado, dict):
            cargado = {}

        seguimientos = cargado.get("seguimientos_fisicos", {})
        if not isinstance(seguimientos, dict):
            seguimientos = {}

        st.session_state["seguimiento_fisico_datos"] = {
            "seguimientos_fisicos": seguimientos,
            "ultima_fecha_corte": _texto(cargado.get("ultima_fecha_corte")),
        }
        st.session_state["_seguimiento_fisico_group"] = group_id_actual
        st.session_state.pop("seguimiento_fisico_corte_activo", None)
        st.session_state.pop("seguimiento_fisico_fecha_activa", None)


def _guardar():
    guardar_estado("seguimiento_fisico", st.session_state["seguimiento_fisico_datos"])


def _cargar_corte_en_sesion(fecha_corte, flujo_fondos, fecha_inicio, mapa_items):
    datos = st.session_state["seguimiento_fisico_datos"]
    clave_fecha = _parse_fecha(fecha_corte).isoformat()
    seguimientos = datos.get("seguimientos_fisicos", {})

    corte = seguimientos.get(clave_fecha, _corte_vacio(fecha_corte))
    if not isinstance(corte, dict):
        corte = _corte_vacio(fecha_corte)

    st.session_state["seguimiento_fisico_fecha_activa"] = clave_fecha
    st.session_state["seguimiento_fisico_corte_activo"] = _recalcular_corte(
        corte,
        flujo_fondos,
        fecha_inicio,
        mapa_items,
    )


def _guardar_corte_activo():
    datos = st.session_state["seguimiento_fisico_datos"]
    corte = st.session_state.get("seguimiento_fisico_corte_activo", {})
    clave_fecha = _parse_fecha(corte.get("fecha_corte")).isoformat()

    if "seguimientos_fisicos" not in datos or not isinstance(datos.get("seguimientos_fisicos"), dict):
        datos["seguimientos_fisicos"] = {}

    datos["seguimientos_fisicos"][clave_fecha] = corte
    datos["ultima_fecha_corte"] = clave_fecha
    _guardar()


# ==========================================================
# Interfaz
# ==========================================================
st.set_page_config(page_title="Seguimiento físico", layout="wide")
st.title("25. Seguimiento físico")

_inicializar_estado()

acta_inicio = _leer_acta_inicio()
contrato_obra = _leer_contrato_obra()
flujo_fondos = _leer_flujo_fondos()

def _tabla_programa_obra_desde_flujo(flujo_fondos):
    tablas = flujo_fondos.get("__tablas__", {}) or {}
    programa_obra = tablas.get("df_programa_obra", []) or []

    if isinstance(programa_obra, list):
        return programa_obra

    return []


def _mapa_items_desde_flujo(flujo_fondos):
    programa = _tabla_programa_obra_desde_flujo(flujo_fondos)
    mapa = {}
    consecutivo_indirecto = 1

    for fila in programa:
        if not isinstance(fila, dict):
            continue

        tipo = _texto(fila.get("TIPO")).upper()
        descripcion = _primero_no_vacio(
            fila.get("DESCRIPCIÓN"),
            fila.get("DESCRIPCION"),
            fila.get("DESCRIPCIÓN DEL ÍTEM"),
            fila.get("DESCRIPCION DEL ITEM"),
        )

        if tipo == "INDIRECTO":
            if _es_interventoria(descripcion):
                continue
            item = _item_visible_flujo(fila, consecutivo_indirecto)
            consecutivo_indirecto += 1
        else:
            item = _texto(fila.get("ITEM"))

        if item:
            mapa[item] = descripcion

    return mapa

fecha_inicio_acta = _fecha_inicio_desde_fuentes(acta_inicio)
valor_contrato = _valor_contrato_desde_contrato_obra(contrato_obra)
mapa_items = _mapa_items_desde_flujo(flujo_fondos)
mapa_programa_obra = _mapa_programa_obra_desde_flujo(flujo_fondos)
opciones_items = [""] + sorted(mapa_items.keys(), key=_key_codigo_natural)

datos = st.session_state["seguimiento_fisico_datos"]
seguimientos = datos.get("seguimientos_fisicos", {})
fechas_guardadas = sorted(seguimientos.keys()) if isinstance(seguimientos, dict) else []

numero_contrato = _primero_no_vacio(
    acta_inicio.get("numero_contrato"),
    acta_inicio.get("contrato_no"),
    contrato_obra.get("numero_contrato"),
)
contratista = _primero_no_vacio(
    acta_inicio.get("nombre_firma_contratista"),
    acta_inicio.get("contratista"),
    acta_inicio.get("nombre_contratista"),
    contrato_obra.get("nombre_contratista"),
    contrato_obra.get("contratista"),
)

objeto_contrato = _primero_no_vacio(
    acta_inicio.get("objeto_contrato"),
    acta_inicio.get("objeto"),
    contrato_obra.get("objeto_general"),
    contrato_obra.get("objeto_contrato"),
    contrato_obra.get("objeto"),
)

with st.container(border=True):
    st.markdown("### DATOS GENERALES")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.text_input("CONTRATO DE OBRA No.", value=numero_contrato, disabled=True)
    with c2:
        st.text_input("CONTRATISTA", value=contratista, disabled=True)
    with c3:
        st.text_input("VALOR DEL CONTRATO", value=f"$ {valor_contrato:,.2f}", disabled=True)

    st.text_area("OBJETO DEL CONTRATO", value=objeto_contrato, disabled=True, height=100)

with st.container(border=True):
    st.markdown("### CREAR NUEVO CORTE")

    col_fecha_nuevo, col_boton_nuevo = st.columns([1, 0.7])

    with col_fecha_nuevo:
        fecha_corte = st.date_input(
            "FECHA DE CORTE",
            value=_parse_fecha(datos.get("ultima_fecha_corte")) if _texto(datos.get("ultima_fecha_corte")) else date.today(),
            key="seguimiento_fisico_fecha_corte_input",
        )

    with col_boton_nuevo:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if st.button("➕ Crear nuevo corte", key="seguimiento_fisico_nuevo_vacio", type="primary"):
            st.session_state["seguimiento_fisico_corte_activo"] = _recalcular_corte(
                _corte_vacio(fecha_corte),
                flujo_fondos,
                fecha_inicio_acta,
                mapa_items,
            )
            st.session_state["seguimiento_fisico_fecha_activa"] = _parse_fecha(fecha_corte).isoformat()
            st.rerun()
            
with st.container(border=True):
    st.markdown("### CONSULTAR CORTE FÍSICO")

    col_consulta, col_cargar = st.columns([1, 0.7])

    with col_consulta:
        fecha_consulta = st.selectbox(
            "Consultar seguimiento guardado",
            options=[""] + fechas_guardadas,
            format_func=lambda x: "" if not x else _parse_fecha(x).strftime("%d/%m/%Y"),
            key="seguimiento_fisico_fecha_consulta",
        )

    with col_cargar:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if st.button("Cargar", key="seguimiento_fisico_cargar"):
            if fecha_consulta:
                _cargar_corte_en_sesion(fecha_consulta, flujo_fondos, fecha_inicio_acta, mapa_items)
                st.rerun()

if "seguimiento_fisico_corte_activo" not in st.session_state:
    fecha_inicial = datos.get("ultima_fecha_corte") if _texto(datos.get("ultima_fecha_corte")) else fecha_corte
    _cargar_corte_en_sesion(fecha_inicial, flujo_fondos, fecha_inicio_acta, mapa_items)

corte_activo = st.session_state["seguimiento_fisico_corte_activo"]
fecha_corte_activa = _parse_fecha(corte_activo.get("fecha_corte"))

st.info(f"Corte físico activo: {fecha_corte_activa.strftime('%d/%m/%Y')}")

with st.container(border=True):
    st.markdown("### AVANCE GENERAL DE OBRA")

    corte_activo = _recalcular_corte(corte_activo, flujo_fondos, fecha_inicio_acta, mapa_items)
    st.session_state["seguimiento_fisico_corte_activo"] = corte_activo

    df_avance_general = pd.DataFrame(
        corte_activo.get("avance_general", []),
        columns=["% EJECUTADO", "$ EJECUTADO", "% PROGRAMADO", "$ PROGRAMADO"],
    )

    avance_general_editado = st.data_editor(
        df_avance_general,
        hide_index=True,
        width="stretch",
        num_rows="fixed",
        disabled=["% PROGRAMADO", "$ PROGRAMADO"],
        key="seguimiento_fisico_avance_general_editor",
        column_config={
            "% EJECUTADO": st.column_config.NumberColumn("% EJECUTADO", format="%.4f"),
            "$ EJECUTADO": st.column_config.NumberColumn("$ EJECUTADO", format="$ %.2f"),
            "% PROGRAMADO": st.column_config.NumberColumn("% PROGRAMADO", format="%.4f"),
            "$ PROGRAMADO": st.column_config.NumberColumn("$ PROGRAMADO", format="$ %.2f"),
        },
    )

with st.container(border=True):
    st.markdown("### AVANCE POR ACTIVIDAD")

    col_item_nuevo, col_boton_item = st.columns([2, 1])

    with col_item_nuevo:
        item_nuevo_avance = st.selectbox(
            "Agregar actividad al seguimiento",
            options=opciones_items,
            key="seguimiento_fisico_item_nuevo_avance",
        )

    with col_boton_item:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if st.button("➕ Agregar actividad", key="seguimiento_fisico_agregar_actividad"):
            if item_nuevo_avance:
                nueva = _fila_avance_actividad_vacia()
                nueva["ITEM"] = item_nuevo_avance
                nueva["DESCRIPCIÓN"] = mapa_items.get(item_nuevo_avance, "")
                nueva["FECHA"] = fecha_corte_activa

                pct_programado, valor_programado = _programado_actividad_desde_flujo(
                    flujo_fondos,
                    item_nuevo_avance,
                    fecha_corte_activa,
                    fecha_inicio_acta,
                )
                nueva["% PROGRAMADO"] = pct_programado
                nueva["$ PROGRAMADO"] = valor_programado

                filas_actuales = [
                    fila for fila in _normalizar_avance_actividad(corte_activo.get("avance_actividad", []))
                    if _texto(fila.get("ITEM"))
                ]

                corte_activo["avance_actividad"] = filas_actuales + [nueva]
                corte_activo = _recalcular_corte(corte_activo, flujo_fondos, fecha_inicio_acta, mapa_items)
                st.session_state["seguimiento_fisico_corte_activo"] = corte_activo
                st.rerun()

    avance_actividad_rows = [
        fila for fila in _normalizar_avance_actividad(corte_activo.get("avance_actividad", []))
        if _texto(fila.get("ITEM"))
    ]

    for fila in avance_actividad_rows:
        item = _texto(fila.get("ITEM"))
        fila["DESCRIPCIÓN"] = mapa_items.get(item, _texto(fila.get("DESCRIPCIÓN")))

        pct_programado, valor_programado = _programado_actividad_desde_flujo(
            flujo_fondos,
            item,
            fecha_corte_activa,
            fecha_inicio_acta,
        )
        fila["FECHA"] = fecha_corte_activa
        fila["% PROGRAMADO"] = pct_programado
        fila["$ PROGRAMADO"] = valor_programado

    df_avance_actividad = pd.DataFrame(
        avance_actividad_rows,
        columns=["ITEM", "DESCRIPCIÓN", "% EJECUTADO", "$ EJECUTADO", "% PROGRAMADO", "$ PROGRAMADO"],
    )

    avance_actividad_editado = st.data_editor(
        df_avance_actividad,
        hide_index=True,
        width="stretch",
        num_rows="dynamic",
        disabled=["ITEM", "DESCRIPCIÓN", "% PROGRAMADO", "$ PROGRAMADO"],
        key="seguimiento_fisico_avance_actividad_editor",
        column_config={
            "ITEM": st.column_config.TextColumn("ITEM"),
            "DESCRIPCIÓN": st.column_config.TextColumn("DESCRIPCIÓN"),
            "% EJECUTADO": st.column_config.NumberColumn("% EJECUTADO", format="%.4f"),
            "$ EJECUTADO": st.column_config.NumberColumn("$ EJECUTADO", format="$ %.2f"),
            "% PROGRAMADO": st.column_config.NumberColumn("% PROGRAMADO", format="%.4f"),
            "$ PROGRAMADO": st.column_config.NumberColumn("$ PROGRAMADO", format="$ %.2f"),
        },
    )

    if st.button("💾 Guardar avance por actividad", key="seguimiento_fisico_guardar_avance_actividad"):
        corte_activo["avance_actividad"] = [
            fila for fila in _normalizar_avance_actividad(
                avance_actividad_editado.to_dict("records")
            )
            if _texto(fila.get("ITEM"))
        ]

        corte_activo = _recalcular_corte(
            corte_activo,
            flujo_fondos,
            fecha_inicio_acta,
            mapa_items,
        )

        st.session_state["seguimiento_fisico_corte_activo"] = corte_activo
        _guardar_corte_activo()
        st.success("Avance por actividad guardado.")
        st.rerun()
    
    ejecutado_general = _safe_float(
        _normalizar_avance_general(avance_general_editado.to_dict("records"))[0].get("$ EJECUTADO"),
        0.0,
    )

    ejecutado_actividades = 0.0
    for fila in _normalizar_avance_actividad(avance_actividad_editado.to_dict("records")):
        ejecutado_actividades += _safe_float(fila.get("$ EJECUTADO"), 0.0)

    diferencia_ejecutado = ejecutado_general - ejecutado_actividades

    if abs(diferencia_ejecutado) <= 1:
        st.success(
            f"Validación correcta: la suma del $ ejecutado por actividad coincide con el $ ejecutado general. "
            f"Total actividades: $ {ejecutado_actividades:,.2f}"
        )
    elif diferencia_ejecutado > 0:
        st.warning(
            f"Falta distribuir en actividades: $ {diferencia_ejecutado:,.2f}. "
            f"$ ejecutado general: $ {ejecutado_general:,.2f} | "
            f"Suma actividades: $ {ejecutado_actividades:,.2f}"
        )
    else:
        st.error(
            f"Las actividades superan el $ ejecutado general en: $ {abs(diferencia_ejecutado):,.2f}. "
            f"$ ejecutado general: $ {ejecutado_general:,.2f} | "
            f"Suma actividades: $ {ejecutado_actividades:,.2f}"
        )

with st.container(border=True):
    st.markdown("### AVANCE FÍSICO POR ACTIVIDAD")

    filas_avance_fisico = []

    for fila in _normalizar_avance_actividad(avance_actividad_editado.to_dict("records")):
        item = _texto(fila.get("ITEM"))
        if not item:
            continue

        datos_programa = mapa_programa_obra.get(item, {})

        descripcion = _primero_no_vacio(
            datos_programa.get("DESCRIPCIÓN"),
            fila.get("DESCRIPCIÓN"),
        )
        unidad = _texto(datos_programa.get("UNIDAD"))
        cantidad_total = _safe_float(datos_programa.get("CANTIDAD"), 0.0)

        porcentaje_ejecutado = _safe_float(fila.get("% EJECUTADO"), 0.0)
        porcentaje_programado = _safe_float(fila.get("% PROGRAMADO"), 0.0)

        cantidad_ejecutada = cantidad_total * (porcentaje_ejecutado / 100.0)
        cantidad_programada = cantidad_total * (porcentaje_programado / 100.0)
        balance = cantidad_ejecutada - cantidad_programada

        filas_avance_fisico.append(
            {
                "ITEM": item,
                "DESCRIPCIÓN": descripcion,
                "UNIDAD": unidad,
                "CANTIDAD": round(cantidad_total, 4),
                "% EJECUTADO": round(porcentaje_ejecutado, 4),
                "EJECUTADO": round(cantidad_ejecutada, 4),
                "% PROGRAMADO": round(porcentaje_programado, 4),
                "PROYECTADO": round(cantidad_programada, 4),
                "BALANCE": round(balance, 4),
            }
        )

    df_avance_fisico = pd.DataFrame(
        filas_avance_fisico,
        columns=[
            "ITEM",
            "DESCRIPCIÓN",
            "UNIDAD",
            "CANTIDAD",
            "% EJECUTADO",
            "EJECUTADO",
            "% PROGRAMADO",
            "PROYECTADO",
            "BALANCE",
        ],
    )

    st.dataframe(
        df_avance_fisico,
        hide_index=True,
        width="stretch",
        column_config={
            "CANTIDAD": st.column_config.NumberColumn("CANTIDAD", format="%.4f"),
            "% EJECUTADO": st.column_config.NumberColumn("% EJECUTADO", format="%.4f"),
            "EJECUTADO": st.column_config.NumberColumn("EJECUTADO", format="%.4f"),
            "% PROGRAMADO": st.column_config.NumberColumn("% PROGRAMADO", format="%.4f"),
            "PROYECTADO": st.column_config.NumberColumn("PROYECTADO", format="%.4f"),
            "BALANCE": st.column_config.NumberColumn("BALANCE", format="%.4f"),
        },
    )

with st.container(border=True):
    st.markdown("### EVOLUCIÓN")

    filas_historico = []
    for clave_fecha, corte in seguimientos.items():
        if not isinstance(corte, dict):
            continue
        corte_tmp = _recalcular_corte(corte, flujo_fondos, fecha_inicio_acta, mapa_items)
        avance_general = _normalizar_avance_general(corte_tmp.get("avance_general", []))[0]
        filas_historico.append(
            {
                "FECHA DE CORTE": _parse_fecha(clave_fecha),
                "% EJECUTADO": avance_general.get("% EJECUTADO", 0.0),
                "% PROGRAMADO": avance_general.get("% PROGRAMADO", 0.0),
                "DIFERENCIA %": round(
                    _safe_float(avance_general.get("% EJECUTADO"), 0.0)
                    - _safe_float(avance_general.get("% PROGRAMADO"), 0.0),
                    4,
                ),
                "$ EJECUTADO": avance_general.get("$ EJECUTADO", 0.0),
                "$ PROGRAMADO": avance_general.get("$ PROGRAMADO", 0.0),
            }
        )

    if filas_historico:
        df_historico = pd.DataFrame(filas_historico).sort_values("FECHA DE CORTE")
        st.dataframe(df_historico, hide_index=True, width="stretch")

        puntos_ac = df_historico[["FECHA DE CORTE", "$ EJECUTADO"]].copy()
        puntos_ac["FECHA DE CORTE"] = pd.to_datetime(puntos_ac["FECHA DE CORTE"]).dt.date
        puntos_ac = puntos_ac.rename(columns={"$ EJECUTADO": "VALOR"})
        puntos_ac["TIPO DE AVANCE"] = "AC - COSTO REAL"

        puntos_ev = df_historico[["FECHA DE CORTE", "% EJECUTADO"]].copy()
        puntos_ev["FECHA DE CORTE"] = pd.to_datetime(puntos_ev["FECHA DE CORTE"]).dt.date
        puntos_ev["VALOR"] = valor_contrato * (_safe_float(0.0) + puntos_ev["% EJECUTADO"].astype(float) / 100.0)
        puntos_ev = puntos_ev[["FECHA DE CORTE", "VALOR"]]
        puntos_ev["TIPO DE AVANCE"] = "EV - VALOR GANADO"

        tablas_flujo = flujo_fondos.get("__tablas__", {})
        resumen_flujo = tablas_flujo.get("df_resumen", [])

        fila_acumulado = {}
        if isinstance(resumen_flujo, list):
            for fila in resumen_flujo:
                if isinstance(fila, dict) and _texto(fila.get("CONCEPTO")).upper() == "ACUMULADO":
                    fila_acumulado = fila
                    break

        puntos_programado = []

        fecha_inicio_programacion = _parse_fecha(fecha_inicio_acta)
        puntos_programado.append(
            {
                "FECHA DE CORTE": fecha_inicio_programacion,
                "VALOR": 0.0,
                "TIPO DE AVANCE": "PV - VALOR PLANEADO",
            }
        )

        periodos_programacion = []
        for columna in fila_acumulado.keys():
            nombre = _texto(columna)
            if nombre.startswith("Periodo "):
                try:
                    numero_periodo = int(nombre.replace("Periodo ", "").strip())
                    periodos_programacion.append((numero_periodo, nombre))
                except Exception:
                    pass

        for numero_periodo, columna in sorted(periodos_programacion, key=lambda x: x[0]):
            puntos_programado.append(
                {
                    "FECHA DE CORTE": fecha_inicio_programacion + timedelta(days=(numero_periodo * 30) - 1),
                    "VALOR": _safe_float(fila_acumulado.get(columna), 0.0),
                    "TIPO DE AVANCE": "PV - VALOR PLANEADO",
                }
            )

        df_programado = pd.DataFrame(puntos_programado)
        df_grafica = pd.concat([df_programado, puntos_ev, puntos_ac], ignore_index=True)

        fig_avance = px.line(
            df_grafica,
            x="FECHA DE CORTE",
            y="VALOR",
            color="TIPO DE AVANCE",
            markers=True,
            title="Valor ganado",
            color_discrete_map={
                "PV - VALOR PLANEADO": "blue",
                "EV - VALOR GANADO": "green",
                "AC - COSTO REAL": "orange",
            },
        )

        fechas_programado = sorted(df_programado["FECHA DE CORTE"].unique())
        fechas_ejecutado = sorted(puntos_ac["FECHA DE CORTE"].unique())
        fechas_todas = sorted(df_grafica["FECHA DE CORTE"].unique())

        fecha_min = min(fechas_todas)
        fecha_max = max(fechas_todas)

        puntos_programado_corte = []

        for fecha in fechas_ejecutado:
            pct_programado, valor_programado = _programado_desde_flujo(
                flujo_fondos,
                fecha,
                fecha_inicio_acta,
            )
            puntos_programado_corte.append(
                {
                    "FECHA DE CORTE": fecha,
                    "VALOR": valor_programado,
                }
            )

        df_programado_corte = pd.DataFrame(puntos_programado_corte)

        if not df_programado_corte.empty:
            fig_avance.add_trace(
                go.Scatter(
                    x=df_programado_corte["FECHA DE CORTE"],
                    y=df_programado_corte["VALOR"],
                    mode="markers",
                    marker=dict(color="blue", size=9),
                    name="$ PROGRAMADO EN CORTE",
                    showlegend=False,
                    hovertemplate="Fecha: %{x|%d/%m/%Y}<br>Programado: $ %{y:,.2f}<extra></extra>",
                )
            )

        for fecha in fechas_ejecutado:
            fig_avance.add_vline(
                x=fecha,
                line_width=1,
                line_dash="dot",
                line_color="gray",
                opacity=0.45,
            )

        fig_avance.add_trace(
            go.Scatter(
                x=fechas_ejecutado,
                y=[None] * len(fechas_ejecutado),
                mode="markers",
                marker=dict(opacity=0),
                showlegend=False,
                xaxis="x2",
                hoverinfo="skip",
            )
        )

        fig_avance.update_layout(
            xaxis_title="Fecha de programación",
            yaxis_title="Valor",
            legend_title="Tipo de avance",
            xaxis=dict(
                tickmode="array",
                tickvals=fechas_programado,
                ticktext=[fecha.strftime("%d-%m-%y") for fecha in fechas_programado],
                tickangle=0,
                range=[fecha_min, fecha_max],
            ),
            xaxis2=dict(
                overlaying="x",
                side="top",
                tickmode="array",
                tickvals=fechas_ejecutado,
                ticktext=[fecha.strftime("%d/%m") for fecha in fechas_ejecutado],
                tickangle=0,
                range=[fecha_min, fecha_max],
                showgrid=False,
            ),
            yaxis_tickprefix="$ ",
            yaxis_tickformat=",",
        )

        st.plotly_chart(fig_avance, width="stretch")


        avance_general_actual = _normalizar_avance_general(corte_activo.get("avance_general", []))[0]

        pv = _safe_float(avance_general_actual.get("$ PROGRAMADO"), 0.0)
        ev = valor_contrato * (_safe_float(avance_general_actual.get("% EJECUTADO"), 0.0) / 100.0)
        ac = _safe_float(avance_general_actual.get("$ EJECUTADO"), 0.0)

        df_valor_ganado = pd.DataFrame(
            [
                {
                    "ÍNDICE": "PV",
                    "DESCRIPCIÓN": "VALOR PLANEADO",
                    "VALOR": pv,
                    "CÁLCULO": "Avance en $ programado a la fecha de corte",
                },
                {
                    "ÍNDICE": "EV",
                    "DESCRIPCIÓN": "VALOR GANADO",
                    "VALOR": ev,
                    "CÁLCULO": "Valor del contrato × porcentaje real de avance",
                },
                {
                    "ÍNDICE": "AC",
                    "DESCRIPCIÓN": "COSTO DE LAS ACTIVIDADES",
                    "VALOR": ac,
                    "CÁLCULO": "Costo cargado como $ ejecutado",
                },
            ]
        )

        st.markdown("### INDICADORES DE VALOR GANADO")
        st.dataframe(
            df_valor_ganado,
            hide_index=True,
            width="stretch",
            column_config={
                "VALOR": st.column_config.NumberColumn("VALOR", format="$ %.2f"),
            },
        )

        spi = ev / pv if pv > 0 else 0.0
        cpi = ev / ac if ac > 0 else 0.0
        eac = valor_contrato / cpi if cpi > 0 else 0.0

        fecha_programacion_ganada = None

        if not df_programado.empty and ev > 0:
            df_programado_ordenado = df_programado.sort_values("FECHA DE CORTE").copy()

            puntos_programacion = []
            for _, fila_prog in df_programado_ordenado.iterrows():
                puntos_programacion.append(
                    {
                        "fecha": _parse_fecha(fila_prog.get("FECHA DE CORTE")),
                        "valor": _safe_float(fila_prog.get("VALOR"), 0.0),
                    }
                )

            for i in range(1, len(puntos_programacion)):
                punto_anterior = puntos_programacion[i - 1]
                punto_actual = puntos_programacion[i]

                valor_anterior = punto_anterior["valor"]
                valor_actual = punto_actual["valor"]

                if valor_anterior <= ev <= valor_actual and valor_actual > valor_anterior:
                    proporcion = (ev - valor_anterior) / (valor_actual - valor_anterior)
                    dias_tramo = (punto_actual["fecha"] - punto_anterior["fecha"]).days
                    fecha_programacion_ganada = punto_anterior["fecha"] + timedelta(
                        days=round(dias_tramo * proporcion)
                    )
                    break

            if fecha_programacion_ganada is None:
                if ev <= puntos_programacion[0]["valor"]:
                    fecha_programacion_ganada = puntos_programacion[0]["fecha"]
                else:
                    fecha_programacion_ganada = puntos_programacion[-1]["fecha"]

            if fecha_programacion_ganada is None:
                fecha_programacion_ganada = _parse_fecha(df_programado_ordenado.iloc[-1]["FECHA DE CORTE"])

        if fecha_programacion_ganada:
            retraso_dias = (fecha_corte_activa - fecha_programacion_ganada).days
        else:
            retraso_dias = 0

        df_indices_valor_ganado = pd.DataFrame(
            [
                {
                    "ÍNDICE": "SPI",
                    "DESCRIPCIÓN": "ÍNDICE DE DESEMPEÑO DEL CRONOGRAMA",
                    "VALOR": spi,
                    "CÁLCULO": "EV / PV",
                },
                {
                    "ÍNDICE": "CPI",
                    "DESCRIPCIÓN": "ÍNDICE DE DESEMPEÑO DEL COSTO",
                    "VALOR": cpi,
                    "CÁLCULO": "EV / AC",
                },
                {
                    "ÍNDICE": "EAC",
                    "DESCRIPCIÓN": "ESTIMACIÓN DEL COSTO AL TERMINAR",
                    "VALOR": eac,
                    "CÁLCULO": "Valor total del contrato / CPI",
                },
                {
                    "ÍNDICE": "PROGRAMACIÓN GANADA",
                    "DESCRIPCIÓN": "FECHA EN QUE SE DEBÍA LOGRAR EL AVANCE ACTUAL",
                    "VALOR": fecha_programacion_ganada.strftime("%d/%m/%Y") if fecha_programacion_ganada else "",
                    "CÁLCULO": "Fecha donde el valor programado acumulado alcanza el EV actual",
                },
                {
                    "ÍNDICE": "RETRASO",
                    "DESCRIPCIÓN": "DIFERENCIA EN DÍAS CALENDARIO",
                    "VALOR": retraso_dias,
                    "CÁLCULO": "Fecha de corte actual - fecha de programación ganada",
                },
            ]
        )

        st.markdown("### ÍNDICES DE VALOR GANADO")
        st.dataframe(
            df_indices_valor_ganado,
            hide_index=True,
            width="stretch",
        )
        
    else:
        st.info("Todavía no hay seguimientos físicos guardados.")
        
col_guardar = st.columns([1])[0]
        
with col_guardar:
    if st.button("💾 Guardar seguimiento físico", type="primary", key="seguimiento_fisico_guardar"):
        corte_activo["avance_general"] = _normalizar_avance_general(avance_general_editado.to_dict("records"))
        corte_activo["avance_actividad"] = _normalizar_avance_actividad(avance_actividad_editado.to_dict("records"))
        corte_activo = _recalcular_corte(corte_activo, flujo_fondos, fecha_inicio_acta, mapa_items)
        st.session_state["seguimiento_fisico_corte_activo"] = corte_activo
        _guardar_corte_activo()
        st.success("Seguimiento físico guardado.")
        st.rerun()
