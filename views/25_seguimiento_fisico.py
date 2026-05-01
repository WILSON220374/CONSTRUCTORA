from datetime import date, datetime
import re

import pandas as pd
import plotly.express as px
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
        txt = txt.replace(".", "").replace(",", ".")
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


def _valor_contrato_desde_fuentes(acta_inicio, contrato_obra):
    candidatos = [
        acta_inicio.get("valor_total_contrato_obra"),
        acta_inicio.get("valor_contrato"),
        acta_inicio.get("valor"),
        contrato_obra.get("valor_total_numeros"),
        contrato_obra.get("valor_contrato"),
    ]
    for valor in candidatos:
        numero = _safe_float(valor, None)
        if numero is not None and numero > 0:
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

    for fila in programa:
        if not isinstance(fila, dict):
            continue
        if _texto(fila.get("ITEM")) == item:
            fila_item = fila
            break

    if not fila_item:
        return 0.0, 0.0

    valor_total_item = _safe_float(fila_item.get("VALOR CON AIU"), 0.0)

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

    periodo_actual = int((dias_transcurridos - 1) // 30) + 1
    dia_periodo = ((dias_transcurridos - 1) % 30) + 1
    factor_periodo = dia_periodo / 30.0
    periodo_actual = min(periodo_actual, periodos[-1][0])

    valor_anterior = 0.0
    for numero, columna in periodos:
        if numero < periodo_actual:
            valor_anterior += _safe_float(fila_item.get(columna), 0.0)

    columna_actual = f"Periodo {periodo_actual} $"
    valor_mes_actual = _safe_float(fila_item.get(columna_actual), 0.0)

    valor_programado = valor_anterior + (valor_mes_actual * factor_periodo)
    pct_programado = (valor_programado / valor_total_item) * 100.0

    return round(pct_programado, 4), round(valor_programado, 2)


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


def _mapa_items_desde_flujo(flujo_fondos):
    programa = flujo_fondos.get("__tablas__", {}).get("df_calculado", [])
    mapa = {}

    if isinstance(programa, list):
        for fila in programa:
            if isinstance(fila, dict):
                item = _texto(fila.get("ITEM"))
                descripcion = _texto(fila.get("DESCRIPCIÓN"))
                if item:
                    mapa[item] = descripcion

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

fecha_inicio_acta = _fecha_inicio_desde_fuentes(acta_inicio)
valor_contrato = _valor_contrato_desde_fuentes(acta_inicio, contrato_obra)
mapa_items = _mapa_items_desde_flujo(flujo_fondos)
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
    st.markdown("### CREAR O CONSULTAR CORTE FÍSICO")

    col_fecha, col_consulta, col_cargar = st.columns([1, 1, 0.7])

    with col_fecha:
        fecha_corte = st.date_input(
            "FECHA DE CORTE",
            value=_parse_fecha(datos.get("ultima_fecha_corte")) if _texto(datos.get("ultima_fecha_corte")) else date.today(),
            key="seguimiento_fisico_fecha_corte_input",
        )

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
            fecha_objetivo = fecha_consulta if fecha_consulta else fecha_corte
            _cargar_corte_en_sesion(fecha_objetivo, flujo_fondos, fecha_inicio_acta, mapa_items)
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
    st.markdown("### TRAZABILIDAD HISTÓRICA")

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

        puntos_ejecutado = df_historico[["FECHA DE CORTE", "$ EJECUTADO"]].copy()
        puntos_ejecutado["FECHA DE CORTE"] = pd.to_datetime(puntos_ejecutado["FECHA DE CORTE"]).dt.date
        puntos_ejecutado = puntos_ejecutado.rename(columns={"$ EJECUTADO": "VALOR"})
        puntos_ejecutado["TIPO DE AVANCE"] = "$ EJECUTADO"

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
                "TIPO DE AVANCE": "$ PROGRAMADO",
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
                    "TIPO DE AVANCE": "$ PROGRAMADO",
                }
            )

        df_programado = pd.DataFrame(puntos_programado)
        df_grafica = pd.concat([puntos_ejecutado, df_programado], ignore_index=True)

        fig_avance = px.line(
            df_grafica,
            x="FECHA DE CORTE",
            y="VALOR",
            color="TIPO DE AVANCE",
            markers=True,
            title="Evolución financiera del avance físico: programado vs ejecutado",
            color_discrete_map={
                "$ EJECUTADO": "orange",
                "$ PROGRAMADO": "blue",
            },
        )

        fechas_corte = sorted(df_grafica["FECHA DE CORTE"].unique())

        fig_avance.update_layout(
            xaxis_title="Fecha de corte",
            yaxis_title="Valor",
            legend_title="Tipo de avance",
            xaxis=dict(
                tickmode="array",
                tickvals=fechas_corte,
                ticktext=[fecha.strftime("%b %d, %Y") for fecha in fechas_corte],
            ),
            yaxis_tickprefix="$ ",
            yaxis_tickformat=",",
        )

        st.plotly_chart(fig_avance, width="stretch")
    else:
        st.info("Todavía no hay seguimientos físicos guardados.")

with col_guardar:
    if st.button("💾 Guardar seguimiento físico", type="primary", key="seguimiento_fisico_guardar"):
        corte_activo["avance_general"] = _normalizar_avance_general(avance_general_editado.to_dict("records"))
        corte_activo["avance_actividad"] = _normalizar_avance_actividad(avance_actividad_editado.to_dict("records"))
        corte_activo = _recalcular_corte(corte_activo, flujo_fondos, fecha_inicio_acta, mapa_items)
        st.session_state["seguimiento_fisico_corte_activo"] = corte_activo
        _guardar_corte_activo()
        st.success("Seguimiento físico guardado.")
        st.rerun()

with col_limpiar:
    if st.button("🧹 Nuevo corte vacío", key="seguimiento_fisico_nuevo_corte"):
        st.session_state["seguimiento_fisico_corte_activo"] = _recalcular_corte(
            _corte_vacio(fecha_corte),
            flujo_fondos,
            fecha_inicio_acta,
            mapa_items,
        )
        st.session_state["seguimiento_fisico_fecha_activa"] = _parse_fecha(fecha_corte).isoformat()
        st.rerun()
