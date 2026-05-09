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
# Helpers generales
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

        txt = str(valor).strip().replace("$", "").replace(" ", "")
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
# Extracción de datos base
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


def _aiu_desde_presupuesto(presupuesto_obra):
    config = presupuesto_obra.get("configuracion") or {}

    aiu_total = _safe_float(
        _primero_no_vacio(
            config.get("aiu_pct_global"),
            config.get("aiu_total"),
            presupuesto_obra.get("aiu_pct_global"),
            presupuesto_obra.get("aiu_total"),
        ),
        0.0,
    )

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
    grupos_presupuesto = (
        (presupuesto_obra.get("__tablas__", {}) or {}).get("grupos_presupuesto_obra", [])
        or presupuesto_obra.get("grupos_presupuesto_obra", [])
        or []
    )
    items_presupuesto = presupuesto_obra.get("items", {}) or {}
    config = presupuesto_obra.get("configuracion") or {}
    aiu_pct = _safe_float(config.get("aiu_pct_global"), 0.0)

    cantidad_por_item = {}
    unidad_por_item = {}
    vu_por_item = {}

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
                fila.get("CANT", fila.get("CANTIDAD", fila.get("cantidad"))),
                0.0,
            )
            unidad_por_item[item] = _texto(fila.get("UNIDAD") or fila.get("unidad"))
            vu_por_item[item] = _safe_float(
                fila.get("VALOR UNITARIO", fila.get("VR UNITARIO", fila.get("VALOR_UNITARIO"))),
                0.0,
            )

    for node_id, rec in items_presupuesto.items():
        if not isinstance(rec, dict):
            continue

        item = _texto(rec.get("item_catalogo") or rec.get("ITEM"))
        if not item:
            continue

        cantidad_por_item.setdefault(
            item,
            _safe_float(rec.get("cant", rec.get("CANT", rec.get("CANTIDAD"))), 0.0),
        )
        unidad_por_item.setdefault(
            item,
            _texto(rec.get("unidad") or rec.get("UNIDAD") or rec.get("UND")),
        )
        vu_por_item.setdefault(
            item,
            _safe_float(rec.get("valor_unitario", rec.get("VALOR UNITARIO")), 0.0),
        )

    for rec in flujo_directos:
        if not isinstance(rec, dict):
            continue

        item = _texto(rec.get("ITEM"))
        descripcion = _texto(rec.get("DESCRIPCIÓN") or rec.get("DESCRIPCION"))
        if not item and not descripcion:
            continue

        valor_base = _safe_float(rec.get("VALOR BASE"), 0.0)
        cantidad = cantidad_por_item.get(item, _safe_float(rec.get("CANTIDAD TOTAL"), 0.0))
        unidad = unidad_por_item.get(item, _texto(rec.get("UNIDAD") or rec.get("unidad")))

        valor_unitario = vu_por_item.get(item, 0.0)
        if valor_unitario <= 0 and cantidad > 0:
            valor_unitario = valor_base / cantidad

        filas.append(
            {
                "No. ORDEN": item,
                "DESCRIPCIÓN ITEM": descripcion,
                "UNIDAD": unidad,
                "VALOR UNITARIO": round(valor_unitario, 2),
                "CANTIDAD": round(cantidad, 4),
                "VALOR TOTAL EJECUTADO": 0.0,
            }
        )

    if not filas:
        tablas = presupuesto_obra.get("__tablas__", {}) or {}
        resumen = tablas.get("resumen_presupuesto_obra", []) or presupuesto_obra.get("resumen_presupuesto_obra", []) or []
        for fila in resumen:
            if not isinstance(fila, dict):
                continue

            item = _texto(fila.get("ITEM"))
            descripcion = _texto(fila.get("DESCRIPCIÓN") or fila.get("DESCRIPCION"))
            if not item and not descripcion:
                continue

            cantidad = _safe_float(fila.get("CANT", fila.get("CANTIDAD")), 0.0)
            valor_unitario = _safe_float(fila.get("VALOR UNITARIO", fila.get("VR UNITARIO")), 0.0)
            valor_base = _safe_float(fila.get("VALOR BASE"), 0.0)

            if valor_unitario <= 0 and cantidad > 0:
                valor_unitario = valor_base / cantidad

            filas.append(
                {
                    "No. ORDEN": item,
                    "DESCRIPCIÓN ITEM": descripcion,
                    "UNIDAD": _texto(fila.get("UNIDAD")),
                    "VALOR UNITARIO": round(valor_unitario, 2),
                    "CANTIDAD": round(cantidad, 4),
                    "VALOR TOTAL EJECUTADO": 0.0,
                }
            )

    return sorted(filas, key=lambda x: _key_codigo_natural(x.get("No. ORDEN")))


def _mapa_items_presupuesto(items):
    return {_texto(fila.get("No. ORDEN")): fila for fila in items if _texto(fila.get("No. ORDEN"))}


def _normalizar_cantidades(rows, mapa_items):
    salida = []

    for fila in rows or []:
        if not isinstance(fila, dict):
            continue

        item = _texto(fila.get("No. ORDEN"))
        if not item:
            continue

        base = mapa_items.get(item, {})
        valor_unitario = _safe_float(
            fila.get("VALOR UNITARIO", base.get("VALOR UNITARIO")),
            0.0,
        )
        valor_total = _safe_float(fila.get("VALOR TOTAL EJECUTADO"), 0.0)

        cantidad = round(valor_total / valor_unitario, 4) if valor_unitario > 0 else 0.0

        salida.append(
            {
                "No. ORDEN": item,
                "DESCRIPCIÓN ITEM": _primero_no_vacio(
                    fila.get("DESCRIPCIÓN ITEM"),
                    base.get("DESCRIPCIÓN ITEM"),
                ),
                "UNIDAD": _primero_no_vacio(fila.get("UNIDAD"), base.get("UNIDAD")),
                "VALOR UNITARIO": round(valor_unitario, 2),
                "CANTIDAD": cantidad,
                "VALOR TOTAL EJECUTADO": round(valor_total, 2),
            }
        )

    return salida


# ==========================================================
# Control: adiciones / suspensiones
# ==========================================================
def _adiciones(control_obra):
    rows = control_obra.get("adiciones_rows", []) or []
    salida = []

    for fila in rows:
        if not isinstance(fila, dict):
            continue

        valor = _safe_float(fila.get("VALOR"), 0.0)
        if valor <= 0 and not _texto(fila.get("ADICIONAL No.")):
            continue

        salida.append(
            {
                "ADICIONAL No.": _texto(fila.get("ADICIONAL No.")),
                "FECHA": _parse_fecha(fila.get("FECHA"), None),
                "VALOR": round(valor, 2),
                "VALOR ACUMULADO DEL CONTRATO": round(
                    _safe_float(fila.get("VALOR ACUMULADO DEL CONTRATO"), 0.0),
                    2,
                ),
            }
        )

    return salida


def _suspensiones(control_obra):
    rows = control_obra.get("suspensiones_rows", []) or []
    salida = []

    for fila in rows:
        if not isinstance(fila, dict):
            continue

        numero = _primero_no_vacio(
            fila.get("ACTA DE SUSPENSIÓN No."),
            fila.get("ACTA DE AMPLIACIÓN SUSPENSIÓN No."),
        )
        desde = _parse_fecha(fila.get("DESDE"), None)
        hasta = _parse_fecha(fila.get("HASTA"), None)

        if not numero and not desde and not hasta:
            continue

        salida.append(
            {
                "ACTA": numero,
                "TIPO": "AMPLIACIÓN" if _texto(fila.get("ACTA DE AMPLIACIÓN SUSPENSIÓN No.")) else "SUSPENSIÓN",
                "FECHA DEL ACTA": _parse_fecha(fila.get("FECHA DEL ACTA"), None),
                "DESDE": desde,
                "HASTA": hasta,
                "PERIODO DE SUSPENSIÓN": int(_safe_float(fila.get("PERIODO DE SUSPENSIÓN"), 0.0)),
                "NUEVA FECHA DE FINALIZACIÓN": _parse_fecha(fila.get("NUEVA FECHA DE FINALIZACIÓN"), None),
            }
        )

    return salida


def _valor_acumulado(valor_inicial, adiciones):
    total = valor_inicial
    for fila in adiciones:
        total += _safe_float(fila.get("VALOR"), 0.0)
    return round(total, 2)


# ==========================================================
# Resumen financiero
# ==========================================================
def _filas_resumen_financiero_guardadas(guardado):
    rows = guardado.get("resumen_financiero_rows", [])
    if isinstance(rows, list) and rows:
        return rows

    return [
        {
            "ACTA No.": i,
            "MES": "",
            "ACTAS DE RECIBO PARCIAL - VALOR BÁSICO": 0.0,
            "ACTAS DE RECIBO PARCIAL - VALOR IVA": 0.0,
            "ACTAS DE RECIBO PARCIAL - VALOR TOTAL": 0.0,
            "AJUSTES PROVISIONALES - VALOR BÁSICO": 0.0,
            "AJUSTES PROVISIONALES - VALOR IVA": 0.0,
            "AJUSTES PROVISIONALES - VALOR TOTAL": 0.0,
            "AJUSTES DEFINITIVOS - VALOR BÁSICO": 0.0,
            "AJUSTES DEFINITIVOS - VALOR IVA": 0.0,
            "AJUSTES DEFINITIVOS - VALOR TOTAL": 0.0,
        }
        for i in range(1, 8)
    ]


def _normalizar_resumen_financiero(rows):
    salida = []
    for fila in rows or []:
        if not isinstance(fila, dict):
            continue

        salida.append(
            {
                "ACTA No.": _safe_float(fila.get("ACTA No."), 0.0),
                "MES": _texto(fila.get("MES")),
                "ACTAS DE RECIBO PARCIAL - VALOR BÁSICO": round(_safe_float(fila.get("ACTAS DE RECIBO PARCIAL - VALOR BÁSICO"), 0.0), 2),
                "ACTAS DE RECIBO PARCIAL - VALOR IVA": round(_safe_float(fila.get("ACTAS DE RECIBO PARCIAL - VALOR IVA"), 0.0), 2),
                "ACTAS DE RECIBO PARCIAL - VALOR TOTAL": round(_safe_float(fila.get("ACTAS DE RECIBO PARCIAL - VALOR TOTAL"), 0.0), 2),
                "AJUSTES PROVISIONALES - VALOR BÁSICO": round(_safe_float(fila.get("AJUSTES PROVISIONALES - VALOR BÁSICO"), 0.0), 2),
                "AJUSTES PROVISIONALES - VALOR IVA": round(_safe_float(fila.get("AJUSTES PROVISIONALES - VALOR IVA"), 0.0), 2),
                "AJUSTES PROVISIONALES - VALOR TOTAL": round(_safe_float(fila.get("AJUSTES PROVISIONALES - VALOR TOTAL"), 0.0), 2),
                "AJUSTES DEFINITIVOS - VALOR BÁSICO": round(_safe_float(fila.get("AJUSTES DEFINITIVOS - VALOR BÁSICO"), 0.0), 2),
                "AJUSTES DEFINITIVOS - VALOR IVA": round(_safe_float(fila.get("AJUSTES DEFINITIVOS - VALOR IVA"), 0.0), 2),
                "AJUSTES DEFINITIVOS - VALOR TOTAL": round(_safe_float(fila.get("AJUSTES DEFINITIVOS - VALOR TOTAL"), 0.0), 2),
            }
        )
    return salida


def _totales_resumen_financiero(rows):
    total_basico = 0.0
    total_iva = 0.0
    total_general = 0.0

    for fila in rows or []:
        total_basico += _safe_float(fila.get("ACTAS DE RECIBO PARCIAL - VALOR BÁSICO"), 0.0)
        total_basico += _safe_float(fila.get("AJUSTES PROVISIONALES - VALOR BÁSICO"), 0.0)
        total_basico += _safe_float(fila.get("AJUSTES DEFINITIVOS - VALOR BÁSICO"), 0.0)

        total_iva += _safe_float(fila.get("ACTAS DE RECIBO PARCIAL - VALOR IVA"), 0.0)
        total_iva += _safe_float(fila.get("AJUSTES PROVISIONALES - VALOR IVA"), 0.0)
        total_iva += _safe_float(fila.get("AJUSTES DEFINITIVOS - VALOR IVA"), 0.0)

        total_general += _safe_float(fila.get("ACTAS DE RECIBO PARCIAL - VALOR TOTAL"), 0.0)
        total_general += _safe_float(fila.get("AJUSTES PROVISIONALES - VALOR TOTAL"), 0.0)
        total_general += _safe_float(fila.get("AJUSTES DEFINITIVOS - VALOR TOTAL"), 0.0)

    return round(total_basico, 2), round(total_iva, 2), round(total_general, 2)


# ==========================================================
# Word
# ==========================================================
def _doc_parrafo(doc, texto="", bold=False, size=10, align=None):
    p = doc.add_paragraph()
    r = p.add_run(str(texto))
    r.bold = bold
    r.font.size = Pt(size)
    if align:
        p.alignment = align
    return p


def _doc_titulo(doc, texto):
    p = doc.add_paragraph()
    r = p.add_run(texto)
    r.bold = True
    r.font.size = Pt(12)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return p


def _doc_tabla_kv(doc, rows):
    table = doc.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    for etiqueta, valor in rows:
        cells = table.add_row().cells
        cells[0].text = str(etiqueta)
        cells[1].text = str(valor)
        for cell in cells:
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    return table


def _doc_tabla_df(doc, df, columnas=None):
    if columnas is None:
        columnas = list(df.columns)

    table = doc.add_table(rows=1, cols=len(columnas))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    hdr = table.rows[0].cells
    for i, col in enumerate(columnas):
        hdr[i].text = str(col)

    for _, row in df.iterrows():
        cells = table.add_row().cells
        for i, col in enumerate(columnas):
            val = row.get(col, "")
            if isinstance(val, (date, datetime)):
                val = _fecha_texto(val)
            elif isinstance(val, float):
                val = _numero(val, 2)
            cells[i].text = str(val)

    return table


def _generar_word(payload):
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Inches(0.6)
    section.bottom_margin = Inches(0.6)
    section.left_margin = Inches(0.7)
    section.right_margin = Inches(0.7)

    generales = payload.get("generales", {})
    aiu = payload.get("aiu", {})
    anticipo = payload.get("anticipo", {})

    _doc_titulo(doc, "ACTA DE ENTREGA Y RECIBO DEFINITIVO DE OBRA")

    _doc_tabla_kv(
        doc,
        [
            ("FECHA", _fecha_texto(payload.get("fecha"))),
            ("CONTRATO DE OBRA No.", generales.get("numero_contrato", "")),
            ("OBJETO DEL CONTRATO", generales.get("objeto", "")),
            ("CONTRATISTA", generales.get("contratista", "")),
            ("FECHA DE INICIO", _fecha_texto(generales.get("fecha_inicio"))),
            ("PLAZO INICIAL", generales.get("plazo_inicial", "")),
            ("VALOR INICIAL", _moneda(generales.get("valor_inicial", 0.0))),
            ("FECHA DE VENCIMIENTO", _fecha_texto(payload.get("fecha_vencimiento"))),
            ("VALOR ACUMULADO", _moneda(payload.get("valor_acumulado", 0.0))),
            ("CONTRATO DE INTERVENTORÍA No.", generales.get("contrato_interventoria", "")),
            ("INTERVENTOR", generales.get("interventor", "")),
        ],
    )

    doc.add_paragraph()
    _doc_parrafo(doc, "ADICIONALES", bold=True)
    _doc_tabla_df(doc, pd.DataFrame(payload.get("adiciones", [])))

    doc.add_paragraph()
    _doc_parrafo(doc, "RELACIÓN SUSPENSIONES Y AMPLIACIONES DE SUSPENSIÓN", bold=True)
    _doc_tabla_df(doc, pd.DataFrame(payload.get("suspensiones", [])))

    doc.add_paragraph()
    _doc_parrafo(doc, "DESCRIPCIÓN GENERAL DE LA OBRA EJECUTADA", bold=True)
    _doc_parrafo(doc, "LOCALIZACIÓN Y LONGITUD DE LA META FÍSICA EJECUTADA:")
    _doc_parrafo(doc, payload.get("localizacion_meta", ""))
    _doc_parrafo(doc, "CARACTERÍSTICAS TÉCNICAS GENERALES Y ALCANCE DE LA OBRA QUE SE ENTREGA Y RECIBE:")
    _doc_parrafo(doc, payload.get("caracteristicas_tecnicas", ""))
    _doc_parrafo(doc, "RELACIÓN DE SITIOS CRÍTICOS ATENDIDOS Y/O SEÑALIZADOS:")
    _doc_parrafo(doc, payload.get("sitios_criticos", ""))

    doc.add_paragraph()
    _doc_parrafo(
        doc,
        "Con la suscripción del Acta de Entrega y Recibo Definitivo de Obra el Contratista y el Interventor certifican que las obras ejecutadas cumplen con la calidad, normas y especificaciones contractuales.",
    )

    doc.add_paragraph()
    _doc_parrafo(doc, "VALOR TOTAL EJECUTADO DEL CONTRATO DE OBRA", bold=True)
    _doc_tabla_kv(
        doc,
        [
            ("Valor total ejecutado del contrato", _moneda(payload.get("valor_total_ejecutado", 0.0))),
            ("AIU", f"{_numero(aiu.get('aiu_total', 0.0), 2)}%"),
            ("A", f"{_numero(aiu.get('administracion', 0.0), 2)}%"),
            ("I", f"{_numero(aiu.get('imprevistos', 0.0), 2)}%"),
            ("U", f"{_numero(aiu.get('utilidad', 0.0), 2)}%"),
        ],
    )

    doc.add_paragraph()
    _doc_parrafo(doc, "DESCRIPCIÓN CANTIDADES DE OBRA EJECUTADAS", bold=True)
    _doc_tabla_df(doc, pd.DataFrame(payload.get("cantidades_rows", [])))

    doc.add_paragraph()
    _doc_parrafo(doc, "ANTICIPO", bold=True)
    _doc_tabla_kv(
        doc,
        [
            ("Valor total concedido", _moneda(anticipo.get("valor_total_concedido", 0.0))),
            ("Valor total amortizado", _moneda(anticipo.get("valor_total_amortizado", 0.0))),
            ("Saldo por amortizar", _moneda(anticipo.get("saldo_por_amortizar", 0.0))),
        ],
    )
    _doc_parrafo(doc, "OBSERVACIONES DEL INTERVENTOR RESPECTO DEL ESTADO DE EJECUCIÓN Y AMORTIZACIÓN DEL ANTICIPO Y/O EJECUCIÓN Y LEGALIZACIÓN DEL PAGO ANTICIPADO")
    _doc_parrafo(doc, payload.get("observaciones_anticipo", ""))

    doc.add_paragraph()
    _doc_parrafo(doc, "RESUMEN FINANCIERO DEL CONTRATO", bold=True)
    _doc_tabla_df(doc, pd.DataFrame(payload.get("resumen_financiero_rows", [])))

    _doc_tabla_kv(
        doc,
        [
            ("VALOR BÁSICO TOTAL EJECUTADO", _moneda(payload.get("valor_basico_total_ejecutado", 0.0))),
            ("VALOR IVA TOTAL EJECUTADO", _moneda(payload.get("valor_iva_total_ejecutado", 0.0))),
            ("VALOR TOTAL EJECUTADO", _moneda(payload.get("valor_total_resumen_ejecutado", 0.0))),
        ],
    )

    doc.add_paragraph()
    _doc_parrafo(doc, "CONCEPTO DE LA INTERVENTORÍA RECIBO DE LAS OBRAS", bold=True)
    _doc_parrafo(doc, payload.get("concepto_interventoria", ""))

    doc.add_paragraph()
    _doc_parrafo(doc, "CONCEPTO DE LA INTERVENTORÍA SOBRE LA APROBACIÓN DE LOS PLANOS RECORD", bold=True)
    _doc_parrafo(doc, payload.get("concepto_planos_record", ""))

    doc.add_paragraph()
    _doc_parrafo(doc, "GESTIÓN AMBIENTAL, SOCIAL, PREDIAL Y DE SOSTENIBILIDAD", bold=True)
    _doc_parrafo(doc, payload.get("gestion_ambiental_social_predial", ""))

    doc.add_paragraph()
    _doc_parrafo(doc, "OTRAS ACTIVIDADES APROBADAS POR EL INTERVENTOR", bold=True)
    _doc_parrafo(doc, payload.get("otras_actividades", ""))

    doc.add_paragraph()
    _doc_parrafo(doc, "OBSERVACIONES DEL INTERVENTOR RESPECTO DEL ESTADO DE LAS GARANTÍAS Y SEGUROS CONTRACTUALES EXIGIDOS AL CONTRATISTA DE OBRA", bold=True)
    _doc_parrafo(doc, payload.get("observaciones_garantias", ""))

    doc.add_paragraph()
    _doc_parrafo(doc, "OBSERVACIONES", bold=True)
    _doc_parrafo(doc, payload.get("observaciones_generales", ""))

    doc.add_paragraph()
    _doc_parrafo(
        doc,
        "Mediante la suscripción del Acta de entrega y recibo Definitivo de obra se asume plena responsabilidad por la veracidad de los valores registrados en los formatos descritos, así como por las operaciones aritméticas contenidas en los mismos, pero no exonera al Contratista ni al Interventor de las obligaciones y responsabilidades estipuladas en el contrato.",
    )
    _doc_parrafo(
        doc,
        "Para constancia de lo anterior, suscriben la presente Acta de Entrega y Recibo Definitivo de Obra quienes en ella intervienen.",
    )

    doc.add_paragraph()
    _doc_parrafo(doc, "FIRMAS", bold=True)
    _doc_tabla_kv(
        doc,
        [
            ("Contratista", payload.get("firma_contratista", "")),
            ("Interventoría", payload.get("firma_interventoria", "")),
            ("Residente contratista", payload.get("firma_residente_contratista", "")),
            ("Residente interventoría", payload.get("firma_residente_interventoria", "")),
        ],
    )

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


# ==========================================================
# Estado inicial
# ==========================================================
def _estado_inicial(generales, adiciones, suspensiones, anticipo):
    return {
        "fecha": date.today(),
        "fecha_vencimiento": generales.get("fecha_vencimiento_inicial", date.today()),
        "valor_acumulado": generales.get("valor_inicial", 0.0),
        "localizacion_meta": "",
        "caracteristicas_tecnicas": "",
        "sitios_criticos": "",
        "valor_total_ejecutado": 0.0,
        "cantidades_rows": [],
        "observaciones_anticipo": "",
        "resumen_financiero_rows": _filas_resumen_financiero_guardadas({}),
        "concepto_interventoria": "La interventoría deja constancia que las obras recibidas cumplen con los requerimientos de calidad, con las normas, especificaciones generales y particulares de construcción y demás condiciones contractuales, de acuerdo con los diseños, planos y especificaciones estipuladas para el proyecto.",
        "concepto_planos_record": "Con la suscripción de la presente Acta la interventoría deja constancia de la revisión y aprobación de los planos record elaborados y entregados por el Contratista.",
        "gestion_ambiental_social_predial": "Las actividades del componente ambiental, social, predial y de sostenibilidad son recibidas y aprobadas por la Interventoría.",
        "otras_actividades": "",
        "observaciones_garantias": "",
        "observaciones_generales": "",
        "firma_contratista": generales.get("contratista", ""),
        "firma_interventoria": generales.get("interventor", ""),
        "firma_residente_contratista": "",
        "firma_residente_interventoria": "",
    }


# ==========================================================
# Interfaz
# ==========================================================
st.set_page_config(page_title="Acta entrega y recibo definitivo de obra", layout="wide")
st.title("📄 ACTA DE ENTREGA Y RECIBO DEFINITIVO DE OBRA")

acta_inicio = _leer_acta_inicio()
contrato_obra = _leer_contrato_obra()
contrato_interventoria = _leer_contrato_interventoria()
control_obra = _leer_control_obra()
presupuesto_obra = _leer_presupuesto_obra()
plan_anticipo = _leer_plan_anticipo()

generales = _datos_generales(acta_inicio, contrato_obra, contrato_interventoria)
adiciones = _adiciones(control_obra)
suspensiones = _suspensiones(control_obra)
aiu = _aiu_desde_presupuesto(presupuesto_obra)
anticipo = _anticipo_desde_fuentes(plan_anticipo, control_obra, generales.get("valor_inicial", 0.0))

guardado = _leer_estado(CLAVE_GUARDADO)
if not guardado:
    guardado = _estado_inicial(generales, adiciones, suspensiones, anticipo)

items_presupuesto = _items_desde_presupuesto(presupuesto_obra)
mapa_items = _mapa_items_presupuesto(items_presupuesto)

valor_acumulado_fuente = _valor_acumulado(generales.get("valor_inicial", 0.0), adiciones)
if _safe_float(guardado.get("valor_acumulado"), 0.0) <= 0:
    guardado["valor_acumulado"] = valor_acumulado_fuente

if not guardado.get("cantidades_rows"):
    guardado["cantidades_rows"] = []

st.markdown("### INFORMACIÓN GENERAL")

c1, c2, c3 = st.columns(3)
with c1:
    fecha_acta = st.date_input("FECHA", value=_parse_fecha(guardado.get("fecha"), date.today()), format="DD/MM/YYYY")
with c2:
    st.text_input("CONTRATO DE OBRA No.", value=generales.get("numero_contrato", ""), disabled=True)
with c3:
    st.text_input("CONTRATO DE INTERVENTORÍA No.", value=generales.get("contrato_interventoria", ""), disabled=True)

st.text_area("OBJETO DEL CONTRATO", value=generales.get("objeto", ""), disabled=True, height=90)

c4, c5, c6 = st.columns(3)
with c4:
    st.text_input("CONTRATISTA", value=generales.get("contratista", ""), disabled=True)
with c5:
    st.date_input("FECHA DE INICIO", value=generales.get("fecha_inicio", date.today()), format="DD/MM/YYYY", disabled=True)
with c6:
    st.text_input("PLAZO INICIAL", value=generales.get("plazo_inicial", ""), disabled=True)

c7, c8, c9 = st.columns(3)
with c7:
    st.number_input("VALOR INICIAL", value=float(generales.get("valor_inicial", 0.0)), format="%.2f", disabled=True)
with c8:
    fecha_vencimiento = st.date_input("FECHA DE VENCIMIENTO", value=_parse_fecha(guardado.get("fecha_vencimiento"), generales.get("fecha_vencimiento_inicial", date.today())), format="DD/MM/YYYY")
with c9:
    valor_acumulado = st.number_input("VALOR ACUMULADO", value=float(_safe_float(guardado.get("valor_acumulado"), valor_acumulado_fuente)), step=1000.0, format="%.2f")

st.text_input("INTERVENTOR", value=generales.get("interventor", ""), disabled=True)

st.markdown("### ADICIONALES")
df_adiciones = pd.DataFrame(adiciones)
if df_adiciones.empty:
    df_adiciones = pd.DataFrame(columns=["ADICIONAL No.", "FECHA", "VALOR", "VALOR ACUMULADO DEL CONTRATO"])

st.dataframe(
    df_adiciones,
    hide_index=True,
    width="stretch",
    column_config={
        "FECHA": st.column_config.DateColumn("FECHA", format="DD/MM/YYYY"),
        "VALOR": st.column_config.NumberColumn("VALOR", format="$ %.2f"),
        "VALOR ACUMULADO DEL CONTRATO": st.column_config.NumberColumn("VALOR ACUMULADO DEL CONTRATO", format="$ %.2f"),
    },
)

st.markdown("### RELACIÓN SUSPENSIONES Y AMPLIACIONES DE SUSPENSIÓN")
df_suspensiones = pd.DataFrame(suspensiones)
if df_suspensiones.empty:
    df_suspensiones = pd.DataFrame(columns=["ACTA", "TIPO", "FECHA DEL ACTA", "DESDE", "HASTA", "PERIODO DE SUSPENSIÓN", "NUEVA FECHA DE FINALIZACIÓN"])

st.dataframe(
    df_suspensiones,
    hide_index=True,
    width="stretch",
    column_config={
        "FECHA DEL ACTA": st.column_config.DateColumn("FECHA DEL ACTA", format="DD/MM/YYYY"),
        "DESDE": st.column_config.DateColumn("DESDE", format="DD/MM/YYYY"),
        "HASTA": st.column_config.DateColumn("HASTA", format="DD/MM/YYYY"),
        "NUEVA FECHA DE FINALIZACIÓN": st.column_config.DateColumn("NUEVA FECHA DE FINALIZACIÓN", format="DD/MM/YYYY"),
    },
)

st.markdown("### DESCRIPCIÓN GENERAL DE LA OBRA EJECUTADA")

localizacion_meta = st.text_area(
    "LOCALIZACIÓN Y LONGITUD DE LA META FÍSICA EJECUTADA",
    value=guardado.get("localizacion_meta", ""),
    height=90,
)

caracteristicas_tecnicas = st.text_area(
    "CARACTERÍSTICAS TÉCNICAS GENERALES Y ALCANCE DE LA OBRA QUE SE ENTREGA Y RECIBE",
    value=guardado.get("caracteristicas_tecnicas", ""),
    height=120,
)

sitios_criticos = st.text_area(
    "RELACIÓN DE SITIOS CRÍTICOS ATENDIDOS Y/O SEÑALIZADOS",
    value=guardado.get("sitios_criticos", ""),
    height=90,
)

st.markdown("### VALOR TOTAL EJECUTADO DEL CONTRATO DE OBRA")
valor_total_ejecutado = st.number_input(
    "Valor total ejecutado del contrato",
    value=float(_safe_float(guardado.get("valor_total_ejecutado"), 0.0)),
    min_value=0.0,
    step=1000.0,
    format="%.2f",
)

c_aiu1, c_aiu2, c_aiu3, c_aiu4 = st.columns(4)
with c_aiu1:
    st.number_input("AIU %", value=float(aiu.get("aiu_total", 0.0)), format="%.2f", disabled=True)
with c_aiu2:
    st.number_input("A %", value=float(aiu.get("administracion", 0.0)), format="%.2f", disabled=True)
with c_aiu3:
    st.number_input("I %", value=float(aiu.get("imprevistos", 0.0)), format="%.2f", disabled=True)
with c_aiu4:
    st.number_input("U %", value=float(aiu.get("utilidad", 0.0)), format="%.2f", disabled=True)

st.markdown("### DESCRIPCIÓN CANTIDADES DE OBRA ")

opciones_items = [""] + [fila["No. ORDEN"] for fila in items_presupuesto]
item_sel = st.selectbox("Seleccionar ítem desde presupuesto", options=opciones_items)

if st.button("➕ Agregar ítem", key="agregar_item_definitivo"):
    if item_sel:
        filas_actuales = guardado.get("cantidades_rows", [])
        if item_sel not in [_texto(f.get("No. ORDEN")) for f in filas_actuales if isinstance(f, dict)]:
            base = mapa_items.get(item_sel, {}).copy()
            base["VALOR TOTAL EJECUTADO"] = 0.0
            filas_actuales.append(base)
            guardado["cantidades_rows"] = _normalizar_cantidades(filas_actuales, mapa_items)
            guardar_estado(CLAVE_GUARDADO, guardado)
            st.rerun()

df_cantidades = pd.DataFrame(
    _normalizar_cantidades(guardado.get("cantidades_rows", []), mapa_items),
    columns=[
        "No. ORDEN",
        "DESCRIPCIÓN ITEM",
        "UNIDAD",
        "VALOR UNITARIO",
        "CANTIDAD",
        "VALOR TOTAL EJECUTADO",
    ],
)

cantidades_editadas = st.data_editor(
    df_cantidades,
    hide_index=True,
    width="stretch",
    num_rows="dynamic",
    key="cantidades_definitivas_editor",
    column_config={
        "No. ORDEN": st.column_config.TextColumn("No. ORDEN"),
        "DESCRIPCIÓN ITEM": st.column_config.TextColumn("DESCRIPCIÓN ITEM", disabled=True),
        "UNIDAD": st.column_config.TextColumn("UNIDAD", disabled=True),
        "VALOR UNITARIO": st.column_config.NumberColumn("VALOR UNITARIO", format="$ %.2f", disabled=True),
        "CANTIDAD": st.column_config.NumberColumn("CANTIDAD", format="%.4f", disabled=True),
        "VALOR TOTAL EJECUTADO": st.column_config.NumberColumn("VALOR TOTAL EJECUTADO", format="$ %.2f"),
    },
)

cantidades_recalculadas = _normalizar_cantidades(cantidades_editadas.to_dict("records"), mapa_items)

df_cantidades_recalculadas = pd.DataFrame(
    cantidades_recalculadas,
    columns=[
        "No. ORDEN",
        "DESCRIPCIÓN ITEM",
        "UNIDAD",
        "VALOR UNITARIO",
        "CANTIDAD",
        "VALOR TOTAL EJECUTADO",
    ],
)

st.markdown("#### Cantidades recalculadas")
st.dataframe(
    df_cantidades_recalculadas,
    hide_index=True,
    width="stretch",
    column_config={
        "No. ORDEN": st.column_config.TextColumn("No. ORDEN"),
        "DESCRIPCIÓN ITEM": st.column_config.TextColumn("DESCRIPCIÓN ITEM"),
        "UNIDAD": st.column_config.TextColumn("UNIDAD"),
        "VALOR UNITARIO": st.column_config.NumberColumn("VALOR UNITARIO", format="$ %.2f"),
        "CANTIDAD": st.column_config.NumberColumn("CANTIDAD", format="%.4f"),
        "VALOR TOTAL EJECUTADO": st.column_config.NumberColumn("VALOR TOTAL EJECUTADO", format="$ %.2f"),
    },
)

total_cantidades = round(
    sum(_safe_float(f.get("VALOR TOTAL EJECUTADO"), 0.0) for f in cantidades_recalculadas),
    2,
)

st.metric("VALOR TOTAL EJECUTADO SEGÚN CANTIDADES", _moneda(total_cantidades))

st.markdown("### ANTICIPO")

c_ant1, c_ant2, c_ant3 = st.columns(3)
with c_ant1:
    st.number_input("Valor total concedido", value=float(anticipo["valor_total_concedido"]), format="%.2f", disabled=True)
with c_ant2:
    st.number_input("Valor total amortizado", value=float(anticipo["valor_total_amortizado"]), format="%.2f", disabled=True)
with c_ant3:
    st.number_input("Saldo por amortizar", value=float(anticipo["saldo_por_amortizar"]), format="%.2f", disabled=True)

observaciones_anticipo = st.text_area(
    "OBSERVACIONES DEL INTERVENTOR RESPECTO DEL ESTADO DE EJECUCIÓN Y AMORTIZACIÓN DEL ANTICIPO Y/O EJECUCIÓN Y LEGALIZACIÓN DEL PAGO ANTICIPADO",
    value=guardado.get("observaciones_anticipo", ""),
    height=120,
)

st.markdown("### RESUMEN FINANCIERO DEL CONTRATO")

df_resumen = pd.DataFrame(
    _filas_resumen_financiero_guardadas(guardado),
    columns=[
        "ACTA No.",
        "MES",
        "ACTAS DE RECIBO PARCIAL - VALOR BÁSICO",
        "ACTAS DE RECIBO PARCIAL - VALOR IVA",
        "ACTAS DE RECIBO PARCIAL - VALOR TOTAL",
        "AJUSTES PROVISIONALES - VALOR BÁSICO",
        "AJUSTES PROVISIONALES - VALOR IVA",
        "AJUSTES PROVISIONALES - VALOR TOTAL",
        "AJUSTES DEFINITIVOS - VALOR BÁSICO",
        "AJUSTES DEFINITIVOS - VALOR IVA",
        "AJUSTES DEFINITIVOS - VALOR TOTAL",
    ],
)

resumen_editado = st.data_editor(
    df_resumen,
    hide_index=True,
    width="stretch",
    num_rows="dynamic",
    key="resumen_financiero_definitivo_editor",
    column_config={
        "ACTA No.": st.column_config.NumberColumn("ACTA No."),
        "MES": st.column_config.TextColumn("MES"),
        "ACTAS DE RECIBO PARCIAL - VALOR BÁSICO": st.column_config.NumberColumn("VALOR BÁSICO", format="$ %.2f"),
        "ACTAS DE RECIBO PARCIAL - VALOR IVA": st.column_config.NumberColumn("VALOR IVA", format="$ %.2f"),
        "ACTAS DE RECIBO PARCIAL - VALOR TOTAL": st.column_config.NumberColumn("VALOR TOTAL", format="$ %.2f"),
        "AJUSTES PROVISIONALES - VALOR BÁSICO": st.column_config.NumberColumn("VALOR BÁSICO", format="$ %.2f"),
        "AJUSTES PROVISIONALES - VALOR IVA": st.column_config.NumberColumn("VALOR IVA", format="$ %.2f"),
        "AJUSTES PROVISIONALES - VALOR TOTAL": st.column_config.NumberColumn("VALOR TOTAL", format="$ %.2f"),
        "AJUSTES DEFINITIVOS - VALOR BÁSICO": st.column_config.NumberColumn("VALOR BÁSICO", format="$ %.2f"),
        "AJUSTES DEFINITIVOS - VALOR IVA": st.column_config.NumberColumn("VALOR IVA", format="$ %.2f"),
        "AJUSTES DEFINITIVOS - VALOR TOTAL": st.column_config.NumberColumn("VALOR TOTAL", format="$ %.2f"),
    },
)

resumen_normalizado = _normalizar_resumen_financiero(resumen_editado.to_dict("records"))
valor_basico_total, valor_iva_total, valor_total_resumen = _totales_resumen_financiero(resumen_normalizado)

c_tot1, c_tot2, c_tot3 = st.columns(3)
with c_tot1:
    st.metric("VALOR BÁSICO TOTAL EJECUTADO", _moneda(valor_basico_total))
with c_tot2:
    st.metric("VALOR IVA TOTAL EJECUTADO", _moneda(valor_iva_total))
with c_tot3:
    st.metric("VALOR TOTAL EJECUTADO", _moneda(valor_total_resumen))

st.markdown("### CONCEPTOS, OBSERVACIONES Y FIRMAS")

concepto_interventoria = st.text_area(
    "CONCEPTO DE LA INTERVENTORÍA RECIBO DE LAS OBRAS",
    value=guardado.get("concepto_interventoria", ""),
    height=110,
)

concepto_planos_record = st.text_area(
    "CONCEPTO DE LA INTERVENTORÍA SOBRE LA APROBACIÓN DE LOS PLANOS RECORD",
    value=guardado.get("concepto_planos_record", ""),
    height=90,
)

gestion_ambiental_social_predial = st.text_area(
    "GESTIÓN AMBIENTAL, SOCIAL, PREDIAL Y DE SOSTENIBILIDAD",
    value=guardado.get("gestion_ambiental_social_predial", ""),
    height=140,
)

otras_actividades = st.text_area(
    "OTRAS ACTIVIDADES APROBADAS POR EL INTERVENTOR",
    value=guardado.get("otras_actividades", ""),
    height=90,
)

observaciones_garantias = st.text_area(
    "OBSERVACIONES DEL INTERVENTOR RESPECTO DEL ESTADO DE LAS GARANTÍAS Y SEGUROS CONTRACTUALES EXIGIDOS AL CONTRATISTA DE OBRA",
    value=guardado.get("observaciones_garantias", ""),
    height=90,
)

observaciones_generales = st.text_area(
    "OBSERVACIONES",
    value=guardado.get("observaciones_generales", ""),
    height=90,
)

c_f1, c_f2 = st.columns(2)
with c_f1:
    firma_contratista = st.text_input("Nombre representante legal o apoderado - Contratista", value=guardado.get("firma_contratista", generales.get("contratista", "")))
    firma_residente_contratista = st.text_input("Nombre ingeniero residente - Contratista", value=guardado.get("firma_residente_contratista", ""))
with c_f2:
    firma_interventoria = st.text_input("Nombre representante legal o apoderado - Interventoría", value=guardado.get("firma_interventoria", generales.get("interventor", "")))
    firma_residente_interventoria = st.text_input("Nombre ingeniero residente - Interventoría", value=guardado.get("firma_residente_interventoria", ""))


payload = {
    "fecha": fecha_acta,
    "generales": generales,
    "fecha_vencimiento": fecha_vencimiento,
    "valor_acumulado": round(valor_acumulado, 2),
    "adiciones": adiciones,
    "suspensiones": suspensiones,
    "localizacion_meta": localizacion_meta,
    "caracteristicas_tecnicas": caracteristicas_tecnicas,
    "sitios_criticos": sitios_criticos,
    "valor_total_ejecutado": round(valor_total_ejecutado, 2),
    "aiu": aiu,
    "cantidades_rows": cantidades_recalculadas,
    "anticipo": anticipo,
    "observaciones_anticipo": observaciones_anticipo,
    "resumen_financiero_rows": resumen_normalizado,
    "valor_basico_total_ejecutado": valor_basico_total,
    "valor_iva_total_ejecutado": valor_iva_total,
    "valor_total_resumen_ejecutado": valor_total_resumen,
    "concepto_interventoria": concepto_interventoria,
    "concepto_planos_record": concepto_planos_record,
    "gestion_ambiental_social_predial": gestion_ambiental_social_predial,
    "otras_actividades": otras_actividades,
    "observaciones_garantias": observaciones_garantias,
    "observaciones_generales": observaciones_generales,
    "firma_contratista": firma_contratista,
    "firma_interventoria": firma_interventoria,
    "firma_residente_contratista": firma_residente_contratista,
    "firma_residente_interventoria": firma_residente_interventoria,
}

c_btn1, c_btn2 = st.columns([1, 1])

with c_btn1:
    if st.button("💾 Guardar acta definitiva", key="guardar_acta_definitiva"):
        guardar_estado(CLAVE_GUARDADO, payload)
        st.success("Acta de entrega y recibo definitivo de obra guardada correctamente.")

with c_btn2:
    buffer = _generar_word(payload)
    st.download_button(
        "📥 Descargar Word",
        data=buffer,
        file_name="acta_entrega_recibo_definitivo_obra.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        key="descargar_word_acta_definitiva",
    )
