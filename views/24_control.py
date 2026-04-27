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


def _fila_avance_vacia():
    return {
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


def _normalizar_financiero(rows, valor_anticipo):
    filas = []
    for fila in rows or []:
        base = _fila_financiera_vacia()
        if isinstance(fila, dict):
            base["FECHA"] = _parse_fecha(fila.get("FECHA"))
            base["VALOR AMORTIZADO"] = _safe_float(fila.get("VALOR AMORTIZADO"), 0.0)
            base["VALOR FACTURADO"] = _safe_float(fila.get("VALOR FACTURADO"), 0.0)
            base["PENDIENTE POR FACTURAR"] = _safe_float(fila.get("PENDIENTE POR FACTURAR"), 0.0)
        base["ANTICIPO"] = round(valor_anticipo, 2)
        base["SALDO POR AMOTIZAR"] = round(valor_anticipo - base["VALOR AMORTIZADO"], 2)
        filas.append(base)

    if not filas:
        fila = _fila_financiera_vacia()
        fila["ANTICIPO"] = round(valor_anticipo, 2)
        fila["SALDO POR AMOTIZAR"] = round(valor_anticipo, 2)
        filas.append(fila)

    return filas


def _normalizar_suspensiones(rows, fecha_inicio_acta):
    filas = []
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
        base["NUEVA FECHA DE FINALIZACIÓN"] = fecha_inicio_acta + timedelta(days=dias)
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
            "financiero_rows": _normalizar_financiero(cargado.get("financiero_rows", []), valor_anticipo),
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

st.markdown("### AVANCE DE OBRA")
df_avance = pd.DataFrame(
    _normalizar_avance(datos.get("avance_rows", [])),
    columns=["FECHA", "% EJECUTADO", "$ EJECUTADO", "% PROGRAMADO", "$ PROGRAMADO"],
)
avance_editado = st.data_editor(
    df_avance,
    hide_index=True,
    width="stretch",
    num_rows="dynamic",
    column_config={
        "FECHA": st.column_config.DateColumn("FECHA", format="DD/MM/YYYY"),
        "% EJECUTADO": st.column_config.NumberColumn("% EJECUTADO", format="%.4f"),
        "$ EJECUTADO": st.column_config.NumberColumn("$ EJECUTADO", format="$ %.2f"),
        "% PROGRAMADO": st.column_config.NumberColumn("% PROGRAMADO", format="%.4f"),
        "$ PROGRAMADO": st.column_config.NumberColumn("$ PROGRAMADO", format="$ %.2f"),
    },
)

st.markdown("### RESUMEN FINANCIERO")
df_financiero = pd.DataFrame(
    _normalizar_financiero(datos.get("financiero_rows", []), valor_anticipo),
    columns=["FECHA", "ANTICIPO", "VALOR AMORTIZADO", "SALDO POR AMOTIZAR", "VALOR FACTURADO", "PENDIENTE POR FACTURAR"],
)
financiero_editado = st.data_editor(
    df_financiero,
    hide_index=True,
    width="stretch",
    num_rows="dynamic",
    column_config={
        "FECHA": st.column_config.DateColumn("FECHA", format="DD/MM/YYYY"),
        "ANTICIPO": st.column_config.NumberColumn("ANTICIPO", format="$ %.2f", disabled=True),
        "VALOR AMORTIZADO": st.column_config.NumberColumn("VALOR AMORTIZADO", format="$ %.2f"),
        "SALDO POR AMOTIZAR": st.column_config.NumberColumn("SALDO POR AMOTIZAR", format="$ %.2f", disabled=True),
        "VALOR FACTURADO": st.column_config.NumberColumn("VALOR FACTURADO", format="$ %.2f"),
        "PENDIENTE POR FACTURAR": st.column_config.NumberColumn("PENDIENTE POR FACTURAR", format="$ %.2f"),
    },
)

st.markdown("### SUSPENSIONES")
c3, c4 = st.columns(2)
with c3:
    st.date_input("FECHA DE INICIO SEGÚN ACTA DE INICIO", value=fecha_inicio_acta, format="DD/MM/YYYY", disabled=True)
with c4:
    st.date_input("FECHA INICIAL DE TERMINACIÓN", value=fecha_inicial_terminacion, format="DD/MM/YYYY", disabled=True)

df_suspensiones = pd.DataFrame(
    _normalizar_suspensiones(datos.get("suspensiones_rows", []), fecha_inicio_acta),
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

guardar_form = st.button("💾 Guardar control")

if guardar_form:
    datos["salario_minimo_anio_contrato"] = salario_minimo_anio_contrato
    datos["avance_rows"] = _normalizar_avance(avance_editado.to_dict("records"))
    datos["financiero_rows"] = _normalizar_financiero(financiero_editado.to_dict("records"), valor_anticipo)
    datos["suspensiones_rows"] = _normalizar_suspensiones(suspensiones_editado.to_dict("records"), fecha_inicio_acta)
    datos["adiciones_rows"] = _normalizar_adiciones(adiciones_editado.to_dict("records"), valor_contrato)
    datos["prorrogas_rows"] = _normalizar_prorrogas(prorrogas_editado.to_dict("records"))
    _guardar()
