from io import BytesIO
from datetime import date, datetime, timedelta
import re

import pandas as pd
import streamlit as st

from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT

from supabase_state import cargar_estado
from supabase_state import guardar_estado as guardar_estado_bd


CLAVE_GUARDADO = "acta_entrega_recibo_definitivo_obra"


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

    return guardar_estado_bd(clave, serializar(datos))


def _leer_estado(clave):
    datos = cargar_estado(clave) or {}
    return datos if isinstance(datos, dict) else {}


# ==========================================================
# Helpers
# ==========================================================
def _texto(valor):
    if valor is None:
        return ""
    return str(valor).strip()


def _primero_no_vacio(*valores):
    for valor in valores:
        txt = _texto(valor)
        if txt:
            return txt
    return ""


def _safe_float(valor, default=0.0):
    try:
        if valor is None or valor == "":
            return None if default is None else float(default)

        if isinstance(valor, (int, float)):
            return float(valor)

        txt = str(valor).strip()
        txt = txt.replace("$", "").replace(" ", "")

        if "," in txt and "." in txt:
            txt = txt.replace(".", "").replace(",", ".")
        elif "," in txt:
            txt = txt.replace(",", ".")

        return float(txt)
    except Exception:
        return None if default is None else float(default)


def _parse_fecha(valor, default=None):
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
    return default if default is not None else date.today()


def _fecha_texto(valor):
    fecha = _parse_fecha(valor, None)
    if not fecha:
        return ""
    return fecha.strftime("%d/%m/%Y")


def _moneda(valor):
    numero = _safe_float(valor, 0.0)
    return "$ " + f"{numero:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _numero(valor, decimales=2):
    numero = _safe_float(valor, 0.0)
    return f"{numero:,.{decimales}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _key_codigo_natural(valor):
    partes = []
    for chunk in _texto(valor).split("."):
        try:
            partes.append(int(chunk))
        except Exception:
            partes.append(chunk)
    return tuple(partes)


def _extraer_dias_plazo(valor):
    txt = _texto(valor).lower()
    nums = re.findall(r"\d+", txt)

    if not nums:
        return 0

    n = int(nums[0])

    if "mes" in txt:
        return n * 30
    if "semana" in txt:
        return n * 7

    return n


# ==========================================================
# Lectura de fuentes
# ==========================================================
def _leer_acta_inicio():
    return _leer_estado("acta_inicio_obra")


def _leer_contrato_obra():
    return _leer_estado("contrato_obra")


def _leer_contrato_interventoria():
    return _leer_estado("contrato_interventoria")


def _leer_control_obra():
    return _leer_estado("control_obra")


def _leer_presupuesto_obra():
    return _leer_estado("presupuesto_obra")


def _leer_plan_anticipo():
    return _leer_estado("plan_inversion_anticipo")


def _leer_actas_parciales():
    datos = _leer_estado("acta_recibo_parcial_obra")

    if isinstance(datos.get("actas"), dict):
        return list(datos.get("actas", {}).values())

    if isinstance(datos.get("actas"), list):
        return datos.get("actas", [])

    return []


# ==========================================================
# Datos generales
# ==========================================================
def _valor_contrato(contrato_obra, acta_inicio):
    for valor in [
        acta_inicio.get("valor_contrato"),
        acta_inicio.get("valor_inicial"),
        contrato_obra.get("valor_total_numeros"),
        contrato_obra.get("valor_contrato"),
        contrato_obra.get("valor"),
    ]:
        numero = _safe_float(valor, None)
        if numero is not None and numero > 0:
            return round(numero, 2)

    return 0.0


def _fecha_inicio(acta_inicio):
    return _parse_fecha(
        _primero_no_vacio(
            acta_inicio.get("fecha_inicio"),
            acta_inicio.get("fecha_presente_acta"),
        ),
        date.today(),
    )


def _fecha_vencimiento_inicial(acta_inicio, contrato_obra):
    fecha_directa = _primero_no_vacio(
        acta_inicio.get("fecha_terminacion"),
        acta_inicio.get("fecha_terminacion_contrato"),
        acta_inicio.get("fecha_finalizacion"),
    )

    if fecha_directa:
        return _parse_fecha(fecha_directa, date.today())

    fecha_inicio = _fecha_inicio(acta_inicio)
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


def _datos_generales(acta_inicio, contrato_obra, contrato_interventoria):
    return {
        "numero_contrato": _primero_no_vacio(
            acta_inicio.get("numero_contrato"),
            contrato_obra.get("numero_contrato"),
        ),
        "objeto": _primero_no_vacio(
            acta_inicio.get("objeto_contrato"),
            contrato_obra.get("objeto_general"),
            contrato_obra.get("objeto_contrato"),
            contrato_obra.get("objeto"),
        ),
        "contratista": _primero_no_vacio(
            acta_inicio.get("nombre_firma_contratista"),
            contrato_obra.get("nombre_contratista"),
            contrato_obra.get("contratista"),
        ),
        "interventor": _primero_no_vacio(
            acta_inicio.get("nombre_firma_interventor"),
            contrato_obra.get("nombre_interventor"),
            contrato_obra.get("interventor"),
        ),
        "supervisor": _primero_no_vacio(
            acta_inicio.get("nombre_firma_supervisor"),
            contrato_obra.get("nombre_supervisor"),
        ),
        "fecha_inicio": _fecha_inicio(acta_inicio),
        "plazo_inicial": _primero_no_vacio(
            acta_inicio.get("plazo_ejecucion"),
            contrato_obra.get("plazo_ejecucion"),
        ),
        "fecha_vencimiento_inicial": _fecha_vencimiento_inicial(acta_inicio, contrato_obra),
        "valor_inicial": _valor_contrato(contrato_obra, acta_inicio),
        "contrato_interventoria": _primero_no_vacio(
            contrato_interventoria.get("numero_proceso_contratacion"),
            contrato_interventoria.get("numero_contrato"),
            contrato_interventoria.get("contrato_interventoria"),
        ),
    }


# ==========================================================
# AIU y anticipo
# ==========================================================
def _aiu_desde_presupuesto(presupuesto_obra):
    config = presupuesto_obra.get("configuracion") or {}

    administracion = _safe_float(
        _primero_no_vacio(
            config.get("administracion"),
            config.get("administracion_pct"),
            config.get("a_pct"),
            presupuesto_obra.get("administracion"),
        ),
        0.0,
    )

    imprevistos = _safe_float(
        _primero_no_vacio(
            config.get("imprevistos"),
            config.get("imprevistos_pct"),
            config.get("i_pct"),
            presupuesto_obra.get("imprevistos"),
        ),
        0.0,
    )

    utilidad = _safe_float(
        _primero_no_vacio(
            config.get("utilidad"),
            config.get("utilidad_pct"),
            config.get("u_pct"),
            presupuesto_obra.get("utilidad"),
        ),
        0.0,
    )

    aiu_total = _safe_float(
        _primero_no_vacio(
            config.get("aiu_pct_global"),
            config.get("aiu_total"),
            presupuesto_obra.get("aiu_pct_global"),
            presupuesto_obra.get("aiu_total"),
        ),
        0.0,
    )

    if aiu_total <= 0:
        aiu_total = administracion + imprevistos + utilidad

    return {
        "aiu_total": round(aiu_total, 2),
        "administracion": round(administracion, 2),
        "imprevistos": round(imprevistos, 2),
        "utilidad": round(utilidad, 2),
    }


def _valor_anticipo(plan_anticipo, valor_contrato):
    valor_directo = _safe_float(plan_anticipo.get("valor_anticipo"), None)

    if valor_directo is not None and valor_directo > 0:
        return round(valor_directo, 2)

    porcentaje = _safe_float(plan_anticipo.get("porcentaje_anticipo"), 0.0)

    if porcentaje > 0 and valor_contrato > 0:
        return round(valor_contrato * porcentaje / 100.0, 2)

    return 0.0


def _anticipo_desde_fuentes(plan_anticipo, control_obra, valor_contrato):
    valor_total_concedido = _valor_anticipo(plan_anticipo, valor_contrato)

    control_rows = control_obra.get("anticipo_rows", []) or []
    valor_amortizado = 0.0

    for fila in control_rows:
        if not isinstance(fila, dict):
            continue
        valor_amortizado += _safe_float(fila.get("VALOR AMORTIZADO"), 0.0)

    saldo = max(0.0, valor_total_concedido - valor_amortizado)

    return {
        "valor_total_concedido": round(valor_total_concedido, 2),
        "valor_total_amortizado": round(valor_amortizado, 2),
        "saldo_por_amortizar": round(saldo, 2),
    }


# ==========================================================
# Presupuesto / ítems
# ==========================================================
def _items_desde_presupuesto(presupuesto_obra):
    filas = []

    flujo_directos = presupuesto_obra.get("flujo_fondos_directos", []) or []

    tablas = presupuesto_obra.get("__tablas__", {}) or {}

    grupos_presupuesto = (
        tablas.get("grupos_presupuesto_obra", [])
        or presupuesto_obra.get("grupos_presupuesto_obra", [])
        or []
    )

    items_presupuesto = presupuesto_obra.get("items", {}) or {}

    cantidad_por_item = {}
    unidad_por_item = {}
    valor_unitario_afectado_por_item = {}

    for grupo in grupos_presupuesto:
        if not isinstance(grupo, dict):
            continue

        for fila in grupo.get("rows", []) or []:
            if not isinstance(fila, dict):
                continue

            item = _texto(fila.get("ITEM") or fila.get("ITEM GOBER"))
            if not item:
                continue

            cantidad_por_item[item] = _safe_float(
                _primero_no_vacio(
                    fila.get("CANT"),
                    fila.get("CANTIDAD"),
                    fila.get("cantidad"),
                ),
                0.0,
            )

            unidad_por_item[item] = _primero_no_vacio(
                fila.get("UNIDAD"),
                fila.get("unidad"),
                fila.get("UND"),
            )

            valor_unitario_afectado_por_item[item] = _safe_float(
                _primero_no_vacio(
                    fila.get("VR AFECTADO POR FACTOR"),
                    fila.get("VALOR AFECTADO POR FACTOR"),
                    fila.get("VR_AFECTADO_POR_FACTOR"),
                    fila.get("VALOR_UNITARIO_AFECTADO"),
                    fila.get("VALOR UNITARIO"),
                    fila.get("VR UNITARIO"),
                    fila.get("VALOR_UNITARIO"),
                ),
                0.0,
            )

    for _, rec in items_presupuesto.items():
        if not isinstance(rec, dict):
            continue

        item = _texto(rec.get("item_catalogo") or rec.get("ITEM"))
        if not item:
            continue

        cantidad_por_item.setdefault(
            item,
            _safe_float(
                _primero_no_vacio(
                    rec.get("cant"),
                    rec.get("CANT"),
                    rec.get("CANTIDAD"),
                ),
                0.0,
            ),
        )

        unidad
