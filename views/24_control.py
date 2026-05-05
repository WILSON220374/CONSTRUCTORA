from datetime import date, datetime, timedelta
import re

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

def _texto(valor):
    if valor is None:
        return ""
    return str(valor).strip()

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


def _extraer_dias_plazo(valor):
    txt = _texto(valor).lower()
    if not txt:
        return 0
    nums = re.findall(r"\d+", txt)
    if not nums:
        return 0
    n = int(nums[0])
    if "mes" in txt:
        return n * 30
    if "semana" in txt:
        return n * 7
    return n


def _leer_estado_directo(clave):
    datos = cargar_estado(clave) or {}
    return datos if isinstance(datos, dict) else {}


def _leer_acta_inicio():
    return _leer_estado_directo("acta_inicio_obra")


def _leer_contrato_obra():
    return _leer_estado_directo("contrato_obra")

def _leer_plan_anticipo():
    return _leer_estado_directo("plan_inversion_anticipo")

def _leer_flujo_fondos():
    return _leer_estado_directo("flujo_fondos")


def _primero_no_vacio(*valores):
    for valor in valores:
        txt = _texto(valor)
        if txt:
            return txt
    return ""


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


def _fecha_inicio_desde_fuentes(acta_inicio):
    return _parse_fecha(
        _primero_no_vacio(
            acta_inicio.get("fecha_inicio"),
            acta_inicio.get("fecha_presente_acta"),
        )
    )


def _duracion_inicial_texto(acta_inicio, contrato_obra):
    return _primero_no_vacio(
        acta_inicio.get("plazo_ejecucion"),
        contrato_obra.get("plazo_ejecucion"),
    )


def _fecha_terminacion_inicial(acta_inicio, contrato_obra):
    fecha_directa = _primero_no_vacio(
        acta_inicio.get("fecha_terminacion"),
        acta_inicio.get("fecha_terminacion_contrato"),
    )
    if fecha_directa:
        return _parse_fecha(fecha_directa)

    fecha_inicio = _fecha_inicio_desde_fuentes(acta_inicio)
    plazo_dias = int(acta_inicio.get("plazo_ejecucion_dias", 0) or 0)
    if plazo_dias <= 0:
        plazo_dias = int(contrato_obra.get("plazo_ejecucion_dias", 0) or 0)
    if plazo_dias <= 0:
        plazo_dias = _extraer_dias_plazo(
            _primero_no_vacio(
                acta_inicio.get("plazo_ejecucion"),
                contrato_obra.get("plazo_ejecucion"),
            )
        )
    return fecha_inicio + timedelta(days=plazo_dias)


def _valor_anticipo_desde_fuentes(plan_anticipo, acta_inicio, contrato_obra):
    valor_directo = _safe_float(plan_anticipo.get("valor_anticipo"), None)
    if valor_directo is not None and valor_directo > 0:
        return round(valor_directo, 2)

    valor_contrato = _valor_contrato_desde_fuentes(acta_inicio, contrato_obra)
    porcentaje = _safe_float(plan_anticipo.get("porcentaje_anticipo"), 0.0)
    if porcentaje <= 0:
        return 0.0
    return round(valor_contrato * porcentaje / 100.0, 2)

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


def _fila_avance_vacia():
    return {
        "FECHA": date.today(),
        "% EJECUTADO": 0.0,
        "$ EJECUTADO": 0.0,
        "% PROGRAMADO": 0.0,
        "$ PROGRAMADO": 0.0,
    }

def _fila_avance_actividad_vacia():
    return {
        "ITEM": "",
        "DESCRIPCIÓN": "",
        "FECHA": date.today(),
        "% EJECUTADO": 0.0,
        "$ EJECUTADO": 0.0,
        "% PROGRAMADO": 0.0,
        "$ PROGRAMADO": 0.0,
    }


def _fila_financiera_vacia():
    return {
        "FECHA": date.today(),
        "ANTICIPO": 0.0,
        "VALOR AMORTIZADO": 0.0,
        "SALDO POR AMOTIZAR": 0.0,
        "VALOR FACTURADO": 0.0,
        "PENDIENTE POR FACTURAR": 0.0,
    }


def _fila_suspension_vacia():
    hoy = date.today()
    return {
        "ACTA DE SUSPENSIÓN No.": "",
        "ACTA DE AMPLIACIÓN SUSPENSIÓN No.": "",
        "FECHA DEL ACTA": hoy,
        "DESDE": hoy,
        "HASTA": hoy,
        "PERIODO DE SUSPENSIÓN": 0,
        "NUEVA FECHA DE FINALIZACIÓN": hoy,
    }


def _fila_adicion_vacia():
    return {
        "ADICIONAL No.": "",
        "FECHA": date.today(),
        "VALOR": 0.0,
        "SMMLV DEL AÑO DE LA ADICIÓN": 0.0,
        "ADICIÓN EN SALARIOS MÍNIMOS": 0.0,
        "VALOR ACUMULADO DEL CONTRATO": 0.0,
    }


def _fila_prorroga_vacia():
    hoy = date.today()
    return {
        "PRÓRROGA No.": "",
        "FECHA": hoy,
        "DESDE": hoy,
        "HASTA": hoy,
        "NUEVA DURACIÓN": "",
        "NUEVA FECHA DE TERMINACIÓN": hoy,
    }


def _normalizar_avance(rows):
    filas = []
    for fila in rows or []:
        base = _fila_avance_vacia()
        if isinstance(fila, dict):
            base["FECHA"] = _parse_fecha(fila.get("FECHA"))
            base["% EJECUTADO"] = _safe_float(fila.get("% EJECUTADO"), 0.0)
            base["$ EJECUTADO"] = _safe_float(fila.get("$ EJECUTADO"), 0.0)
            base["% PROGRAMADO"] = _safe_float(fila.get("% PROGRAMADO"), 0.0)
            base["$ PROGRAMADO"] = _safe_float(fila.get("$ PROGRAMADO"), 0.0)
        filas.append(base)

    if not filas:
        filas.append(_fila_avance_vacia())

    return filas

def _normalizar_avance_actividad(rows):
    filas = []
    for fila in rows or []:
        base = _fila_avance_actividad_vacia()
        if isinstance(fila, dict):
            base["ITEM"] = _texto(fila.get("ITEM"))
            base["DESCRIPCIÓN"] = _texto(fila.get("DESCRIPCIÓN"))
            base["FECHA"] = _parse_fecha(fila.get("FECHA"))
            base["% EJECUTADO"] = _safe_float(fila.get("% EJECUTADO"), 0.0)
            base["$ EJECUTADO"] = _safe_float(fila.get("$ EJECUTADO"), 0.0)
            base["% PROGRAMADO"] = _safe_float(fila.get("% PROGRAMADO"), 0.0)
            base["$ PROGRAMADO"] = _safe_float(fila.get("$ PROGRAMADO"), 0.0)
        filas.append(base)

    if not filas:
        filas.append(_fila_avance_actividad_vacia())

    return filas


def _normalizar_pagos(rows, valor_contrato):
    filas = []
    saldo = round(valor_contrato, 2)

    for fila in rows or []:
        valor_inicial = saldo

        base = {
            "FECHA": date.today(),
            "VALOR INICIAL": valor_inicial,
            "VALOR FACTURADO": 0.0,
            "PENDIENTE POR FACTURAR": valor_inicial,
        }

        if isinstance(fila, dict):
            base["FECHA"] = _parse_fecha(fila.get("FECHA"))
            base["VALOR FACTURADO"] = _safe_float(fila.get("VALOR FACTURADO"), 0.0)

        saldo = round(valor_inicial - base["VALOR FACTURADO"], 2)
        base["PENDIENTE POR FACTURAR"] = saldo
        filas.append(base)

    if not filas:
        filas.append(
            {
                "FECHA": date.today(),
                "VALOR INICIAL": round(valor_contrato, 2),
                "VALOR FACTURADO": 0.0,
                "PENDIENTE POR FACTURAR": round(valor_contrato, 2),
            }
        )

    return filas


def _normalizar_anticipo(rows, valor_anticipo):
    filas = []
    saldo = round(valor_anticipo, 2)

    for fila in rows or []:
        base = {
            "FECHA": date.today(),
            "VALOR INICIAL": saldo,
            "VALOR AMORTIZADO": 0.0,
            "SALDO": saldo,
        }

        if isinstance(fila, dict):
            base["FECHA"] = _parse_fecha(fila.get("FECHA"))
            base["VALOR AMORTIZADO"] = _safe_float(fila.get("VALOR AMORTIZADO"), 0.0)

        base["VALOR INICIAL"] = saldo
        saldo = round(saldo - base["VALOR AMORTIZADO"], 2)
        base["SALDO"] = saldo
        filas.append(base)

    if not filas:
        filas.append(
            {
                "FECHA": date.today(),
                "VALOR INICIAL": round(valor_anticipo, 2),
                "VALOR AMORTIZADO": 0.0,
                "SALDO": round(valor_anticipo, 2),
            }
        )

    return filas


def _normalizar_suspensiones(rows, fecha_inicial_terminacion):
    filas = []
    fecha_base = _parse_fecha(fecha_inicial_terminacion)

    for fila in rows or []:
        base = _fila_suspension_vacia()
        if isinstance(fila, dict):
            base["ACTA DE SUSPENSIÓN No."] = _texto(fila.get("ACTA DE SUSPENSIÓN No."))
            base["ACTA DE AMPLIACIÓN SUSPENSIÓN No."] = _texto(fila.get("ACTA DE AMPLIACIÓN SUSPENSIÓN No."))
            base["FECHA DEL ACTA"] = _parse_fecha(fila.get("FECHA DEL ACTA"))
            base["DESDE"] = _parse_fecha(fila.get("DESDE"))
            base["HASTA"] = _parse_fecha(fila.get("HASTA"))

        dias = (base["HASTA"] - base["DESDE"]).days
        if dias < 0:
            dias = 0

        base["PERIODO DE SUSPENSIÓN"] = dias
        base["NUEVA FECHA DE FINALIZACIÓN"] = fecha_base + timedelta(days=dias)
        filas.append(base)

    if not filas:
        filas.append(_fila_suspension_vacia())

    return filas


def _normalizar_adiciones(rows, valor_inicial_contrato):
    filas = []
    for fila in rows or []:
        base = _fila_adicion_vacia()
        if isinstance(fila, dict):
            base["ADICIONAL No."] = _texto(fila.get("ADICIONAL No."))
            base["FECHA"] = _parse_fecha(fila.get("FECHA"))
            base["VALOR"] = _safe_float(fila.get("VALOR"), 0.0)
            base["SMMLV DEL AÑO DE LA ADICIÓN"] = _safe_float(fila.get("SMMLV DEL AÑO DE LA ADICIÓN"), 0.0)

        smmlv = base["SMMLV DEL AÑO DE LA ADICIÓN"]
        base["ADICIÓN EN SALARIOS MÍNIMOS"] = round(base["VALOR"] / smmlv, 4) if smmlv > 0 else 0.0
        base["VALOR ACUMULADO DEL CONTRATO"] = round(valor_inicial_contrato + base["VALOR"], 2)
        filas.append(base)

    if not filas:
        filas.append(_fila_adicion_vacia())

    return filas


def _normalizar_prorrogas(rows):
    filas = []
    for fila in rows or []:
        base = _fila_prorroga_vacia()
        if isinstance(fila, dict):
            base["PRÓRROGA No."] = _texto(fila.get("PRÓRROGA No."))
            base["FECHA"] = _parse_fecha(fila.get("FECHA"))
            base["DESDE"] = _parse_fecha(fila.get("DESDE"))
            base["HASTA"] = _parse_fecha(fila.get("HASTA"))
            base["NUEVA DURACIÓN"] = _texto(fila.get("NUEVA DURACIÓN"))
            base["NUEVA FECHA DE TERMINACIÓN"] = _parse_fecha(fila.get("NUEVA FECHA DE TERMINACIÓN"))
        filas.append(base)

    if not filas:
        filas.append(_fila_prorroga_vacia())

    return filas


def _inicializar_estado(acta_inicio, contrato_obra, plan_anticipo):
    group_id_actual = _texto(st.session_state.get("group_id"))
    cache_group = _texto(st.session_state.get("_control_obra_group"))

    if cache_group != group_id_actual or "control_obra_datos" not in st.session_state:
        cargado = cargar_estado("control_obra") or {}
        if not isinstance(cargado, dict):
            cargado = {}

        valor_contrato = _valor_contrato_desde_fuentes(acta_inicio, contrato_obra)
        valor_anticipo = _valor_anticipo_desde_fuentes(plan_anticipo, acta_inicio, contrato_obra)
        fecha_inicio_acta = _fecha_inicio_desde_fuentes(acta_inicio)

        st.session_state["control_obra_datos"] = {
            "salario_minimo_anio_contrato": _safe_float(cargado.get("salario_minimo_anio_contrato"), 0.0),
            "avance_rows": _normalizar_avance(cargado.get("avance_rows", [])),
            "pagos_rows": _normalizar_pagos(cargado.get("pagos_rows", []), valor_contrato),
            "anticipo_rows": _normalizar_anticipo(cargado.get("anticipo_rows", []), valor_anticipo),
            "suspensiones_rows": _normalizar_suspensiones(cargado.get("suspensiones_rows", []), fecha_inicio_acta),
            "adiciones_rows": _normalizar_adiciones(cargado.get("adiciones_rows", []), valor_contrato),
            "prorrogas_rows": _normalizar_prorrogas(cargado.get("prorrogas_rows", [])),
        }

        st.session_state["_control_obra_group"] = group_id_actual


def _guardar():
    guardar_estado("control_obra", st.session_state["control_obra_datos"])
    st.success("Control guardado correctamente.")


acta_inicio = _leer_acta_inicio()
contrato_obra = _leer_contrato_obra()
plan_anticipo = _leer_plan_anticipo()
flujo_fondos = _leer_flujo_fondos()

_inicializar_estado(acta_inicio, contrato_obra, plan_anticipo)

datos = st.session_state["control_obra_datos"]

fecha_inicio_acta = _fecha_inicio_desde_fuentes(acta_inicio)
valor_contrato = _valor_contrato_desde_fuentes(acta_inicio, contrato_obra)
valor_anticipo = _valor_anticipo_desde_fuentes(plan_anticipo, acta_inicio, contrato_obra)
duracion_inicial = _duracion_inicial_texto(acta_inicio, contrato_obra)
fecha_inicial_terminacion = _fecha_terminacion_inicial(acta_inicio, contrato_obra)
fecha_actual_terminacion = _fecha_terminacion_inicial(acta_inicio, contrato_obra)

objeto_contrato = _primero_no_vacio(
    acta_inicio.get("objeto_contrato"),
    contrato_obra.get("objeto_general"),
    contrato_obra.get("objeto_contrato"),
    contrato_obra.get("objeto"),
)

numero_contrato = _primero_no_vacio(
    acta_inicio.get("numero_contrato"),
    contrato_obra.get("numero_contrato"),
)

contratista = _primero_no_vacio(
    acta_inicio.get("nombre_firma_contratista"),
    contrato_obra.get("nombre_contratista"),
)

st.markdown(
    """
    <style>
    .control-titulo {
        text-align: center;
        font-size: 30px;
        font-weight: 800;
        margin-bottom: 14px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="control-titulo">CONTROL</div>', unsafe_allow_html=True)

st.markdown("### DATOS GENERALES")

c1, c2 = st.columns(2)
with c1:
    st.text_input("CONTRATO DE OBRA No.", value=numero_contrato, disabled=True)
with c2:
    st.text_input("CONTRATISTA", value=contratista, disabled=True)

st.text_area("OBJETO DEL CONTRATO DE OBRA", value=objeto_contrato, disabled=True, height=120)

c3, c4, c5 = st.columns(3)
with c3:
    st.number_input(
        "VALOR DEL CONTRATO",
        min_value=0.0,
        value=valor_contrato,
        step=1000.0,
        format="%.2f",
        disabled=True,
    )
with c4:
    st.text_input(
        "PLAZO DE EJECUCIÓN",
        value=duracion_inicial,
        disabled=True,
    )
with c5:
    st.number_input(
        "VALOR DEL ANTICIPO",
        min_value=0.0,
        value=valor_anticipo,
        step=1000.0,
        format="%.2f",
        disabled=True,
    )
tab_financiero, tab_modificaciones = st.tabs(
    [
        "Seguimiento financiero",
        "Modificaciones del contrato",
    ]
)

with tab_financiero:
    st.markdown("### PAGOS")

    df_pagos = pd.DataFrame(
        _normalizar_pagos(datos.get("pagos_rows", []), valor_contrato),
        columns=["FECHA", "VALOR INICIAL", "VALOR FACTURADO", "PENDIENTE POR FACTURAR"],
    )

    pagos_editado = st.data_editor(
        df_pagos,
        hide_index=True,
        width="stretch",
        num_rows="dynamic",
        disabled=["VALOR INICIAL", "PENDIENTE POR FACTURAR"],
        key="control_pagos_editor",
        column_config={
            "FECHA": st.column_config.DateColumn("FECHA", format="DD/MM/YYYY"),
            "VALOR INICIAL": st.column_config.NumberColumn("VALOR INICIAL", format="$ %.2f"),
            "VALOR FACTURADO": st.column_config.NumberColumn("VALOR FACTURADO", format="$ %.2f"),
            "PENDIENTE POR FACTURAR": st.column_config.NumberColumn("PENDIENTE POR FACTURAR", format="$ %.2f"),
        },
    )

    pagos_recalculados = _normalizar_pagos(pagos_editado.to_dict("records"), valor_contrato)
    if pagos_recalculados != datos.get("pagos_rows", []):
        datos["pagos_rows"] = pagos_recalculados

    st.markdown("### ANTICIPO")

    df_anticipo = pd.DataFrame(
        _normalizar_anticipo(datos.get("anticipo_rows", []), valor_anticipo),
        columns=["FECHA", "VALOR INICIAL", "VALOR AMORTIZADO", "SALDO"],
    )

    anticipo_editado = st.data_editor(
        df_anticipo,
        hide_index=True,
        width="stretch",
        num_rows="dynamic",
        disabled=["VALOR INICIAL", "SALDO"],
        key="control_anticipo_editor",
        column_config={
            "FECHA": st.column_config.DateColumn("FECHA", format="DD/MM/YYYY"),
            "VALOR INICIAL": st.column_config.NumberColumn("VALOR INICIAL", format="$ %.2f"),
            "VALOR AMORTIZADO": st.column_config.NumberColumn("VALOR AMORTIZADO", format="$ %.2f"),
            "SALDO": st.column_config.NumberColumn("SALDO", format="$ %.2f"),
        },
    )

    anticipo_recalculado = _normalizar_anticipo(anticipo_editado.to_dict("records"), valor_anticipo)
    if anticipo_recalculado != datos.get("anticipo_rows", []):
        datos["anticipo_rows"] = anticipo_recalculado

    if (
        pagos_recalculados != df_pagos.to_dict("records")
        or anticipo_recalculado != df_anticipo.to_dict("records")
    ):
        st.rerun()
        
with tab_modificaciones:
    st.markdown("### SUSPENSIONES")
    c3, c4 = st.columns(2)
    with c3:
        st.date_input("FECHA DE INICIO SEGÚN ACTA DE INICIO", value=fecha_inicio_acta, format="DD/MM/YYYY", disabled=True)
    with c4:
        st.date_input("FECHA INICIAL DE TERMINACIÓN", value=fecha_inicial_terminacion, format="DD/MM/YYYY", disabled=True)

    df_suspensiones = pd.DataFrame(
        _normalizar_suspensiones(datos.get("suspensiones_rows", []), fecha_inicial_terminacion),
        columns=[
            "ACTA DE SUSPENSIÓN No.",
            "ACTA DE AMPLIACIÓN SUSPENSIÓN No.",
            "FECHA DEL ACTA",
            "DESDE",
            "HASTA",
            "PERIODO DE SUSPENSIÓN",
            "NUEVA FECHA DE FINALIZACIÓN",
        ],
    )
    suspensiones_editado = st.data_editor(
        df_suspensiones,
        hide_index=True,
        width="stretch",
        num_rows="dynamic",
        key="control_suspensiones_editor",
        column_config={
            "ACTA DE SUSPENSIÓN No.": st.column_config.TextColumn("ACTA DE SUSPENSIÓN No."),
            "ACTA DE AMPLIACIÓN SUSPENSIÓN No.": st.column_config.TextColumn("ACTA DE AMPLIACIÓN SUSPENSIÓN No."),
            "FECHA DEL ACTA": st.column_config.DateColumn("FECHA DEL ACTA", format="DD/MM/YYYY"),
            "DESDE": st.column_config.DateColumn("DESDE", format="DD/MM/YYYY"),
            "HASTA": st.column_config.DateColumn("HASTA", format="DD/MM/YYYY"),
            "PERIODO DE SUSPENSIÓN": st.column_config.NumberColumn("PERIODO DE SUSPENSIÓN", disabled=True),
            "NUEVA FECHA DE FINALIZACIÓN": st.column_config.DateColumn("NUEVA FECHA DE FINALIZACIÓN", format="DD/MM/YYYY", disabled=True),
        },
    )

    suspensiones_recalculadas = _normalizar_suspensiones(
        suspensiones_editado.to_dict("records"),
        fecha_inicial_terminacion,
    )

    if suspensiones_recalculadas != df_suspensiones.to_dict("records"):
        datos["suspensiones_rows"] = suspensiones_recalculadas
        _guardar()
        st.rerun()

    datos["suspensiones_rows"] = suspensiones_recalculadas
    
    st.markdown("### ADICIONES")
    salario_minimo_anio_contrato = st.number_input(
        "Salario mínimo del año del contrato",
        min_value=0.0,
        value=_safe_float(datos.get("salario_minimo_anio_contrato"), 0.0),
        step=1000.0,
        format="%.2f",
    )

    c5, c6, c7 = st.columns(3)
    with c5:
        st.number_input("VALOR INICIAL DEL CONTRATO", min_value=0.0, value=valor_contrato, step=1000.0, format="%.2f", disabled=True)
    with c6:
        valor_contrato_smmlv = round(valor_contrato / salario_minimo_anio_contrato, 4) if salario_minimo_anio_contrato > 0 else 0.0
        st.number_input("Valor del contrato en salarios mínimos", min_value=0.0, value=valor_contrato_smmlv, step=0.0001, format="%.4f", disabled=True)
    with c7:
        maxima_adicion_smmlv = round(valor_contrato_smmlv * 0.5, 4)
        st.number_input("Máxima adición en salarios mínimos", min_value=0.0, value=maxima_adicion_smmlv, step=0.0001, format="%.4f", disabled=True)

    df_adiciones = pd.DataFrame(
        _normalizar_adiciones(datos.get("adiciones_rows", []), valor_contrato),
        columns=[
            "ADICIONAL No.",
            "FECHA",
            "VALOR",
            "SMMLV DEL AÑO DE LA ADICIÓN",
            "ADICIÓN EN SALARIOS MÍNIMOS",
            "VALOR ACUMULADO DEL CONTRATO",
        ],
    )
    adiciones_editado = st.data_editor(
        df_adiciones,
        hide_index=True,
        width="stretch",
        num_rows="dynamic",
        column_config={
            "ADICIONAL No.": st.column_config.TextColumn("ADICIONAL No."),
            "FECHA": st.column_config.DateColumn("FECHA", format="DD/MM/YYYY"),
            "VALOR": st.column_config.NumberColumn("VALOR", format="$ %.2f"),
            "SMMLV DEL AÑO DE LA ADICIÓN": st.column_config.NumberColumn("SMMLV DEL AÑO DE LA ADICIÓN", format="$ %.2f"),
            "ADICIÓN EN SALARIOS MÍNIMOS": st.column_config.NumberColumn("ADICIÓN EN SALARIOS MÍNIMOS", format="%.4f", disabled=True),
            "VALOR ACUMULADO DEL CONTRATO": st.column_config.NumberColumn("VALOR ACUMULADO DEL CONTRATO", format="$ %.2f", disabled=True),
        },
    )

    st.markdown("### PRÓRROGAS")
    c8, c9, c10 = st.columns(3)
    with c8:
        st.text_input("Duración inicial del contrato", value=duracion_inicial, disabled=True)
    with c9:
        st.date_input("Fecha inicial de terminación", value=fecha_inicial_terminacion, format="DD/MM/YYYY", disabled=True)
    with c10:
        st.date_input("Fecha actual de terminación", value=fecha_actual_terminacion, format="DD/MM/YYYY", disabled=True)

    df_prorrogas = pd.DataFrame(
        _normalizar_prorrogas(datos.get("prorrogas_rows", [])),
        columns=["PRÓRROGA No.", "FECHA", "DESDE", "HASTA", "NUEVA DURACIÓN", "NUEVA FECHA DE TERMINACIÓN"],
    )
    prorrogas_editado = st.data_editor(
        df_prorrogas,
        hide_index=True,
        width="stretch",
        num_rows="dynamic",
        column_config={
            "PRÓRROGA No.": st.column_config.TextColumn("PRÓRROGA No."),
            "FECHA": st.column_config.DateColumn("FECHA", format="DD/MM/YYYY"),
            "DESDE": st.column_config.DateColumn("DESDE", format="DD/MM/YYYY"),
            "HASTA": st.column_config.DateColumn("HASTA", format="DD/MM/YYYY"),
            "NUEVA DURACIÓN": st.column_config.TextColumn("NUEVA DURACIÓN"),
            "NUEVA FECHA DE TERMINACIÓN": st.column_config.DateColumn("NUEVA FECHA DE TERMINACIÓN", format="DD/MM/YYYY"),
        },
    )

    st.markdown("### SEGUIMIENTO A GARANTÍAS")
    st.markdown("#### CONDICIONES INICIALES")

    garantias_contrato = contrato_obra.get("garantias", []) or []

    df_garantias = pd.DataFrame(
        garantias_contrato,
        columns=["amparo", "suficiencia", "desde", "hasta"],
    )

    if df_garantias.empty:
        df_garantias = pd.DataFrame(
            [
                {
                    "amparo": "",
                    "suficiencia": "",
                    "desde": "",
                    "hasta": "",
                }
            ]
        )

    for col in ["desde", "hasta"]:
        df_garantias[col] = pd.to_datetime(df_garantias[col], errors="coerce").dt.date

    df_garantias = df_garantias[
        [
            "amparo",
            "suficiencia",
            "desde",
            "hasta",
        ]
    ]

    st.dataframe(
        df_garantias,
        hide_index=True,
        width="stretch",
        column_config={
            "amparo": st.column_config.TextColumn("AMPARO"),
            "suficiencia": st.column_config.TextColumn("SUFICIENCIA"),
            "desde": st.column_config.DateColumn("DESDE", format="DD/MM/YYYY"),
            "hasta": st.column_config.DateColumn("HASTA", format="DD/MM/YYYY"),
        },
    )

guardar_form = st.button("💾 Guardar control")

if guardar_form:
    datos["salario_minimo_anio_contrato"] = salario_minimo_anio_contrato
    datos["pagos_rows"] = _normalizar_pagos(pagos_editado.to_dict("records"), valor_contrato)
    datos["anticipo_rows"] = _normalizar_anticipo(anticipo_editado.to_dict("records"), valor_anticipo)
    datos["suspensiones_rows"] = _normalizar_suspensiones(suspensiones_editado.to_dict("records"), fecha_inicial_terminacion)
    datos["adiciones_rows"] = _normalizar_adiciones(adiciones_editado.to_dict("records"), valor_contrato)
    datos["prorrogas_rows"] = _normalizar_prorrogas(prorrogas_editado.to_dict("records"))
    _guardar()
    st.rerun()
