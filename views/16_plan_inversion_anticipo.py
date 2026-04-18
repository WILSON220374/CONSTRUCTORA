from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
from io import BytesIO

import pandas as pd
import streamlit as st
from docx import Document
from docx.shared import Inches

from supabase_state import cargar_estado
from supabase_state import guardar_estado as guardar_estado_bd


CLAVE_GUARDADO = "plan_inversion_anticipo"
PORCENTAJE_ANTICIPO = 30.0
FILAS_INICIALES = 3
MIN_MESES = 3


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
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(txt, fmt).date()
            except Exception:
                continue
        try:
            return datetime.fromisoformat(txt).date()
        except Exception:
            return None
    return None


def _fecha_texto(valor) -> str:
    f = _parse_fecha(valor)
    if not f:
        return ""
    return f.strftime("%d/%m/%Y")


def _safe_float(valor, default=0.0) -> float:
    if valor is None:
        return float(default)
    if isinstance(valor, (int, float)):
        return float(valor)
    txt = str(valor).strip()
    if not txt:
        return float(default)
    txt = txt.replace("$", "").replace("%", "").replace(" ", "")
    txt = txt.replace(".", "").replace(",", ".") if txt.count(",") == 1 and txt.count(".") >= 1 else txt
    txt = txt.replace(",", "")
    try:
        return float(txt)
    except Exception:
        return float(default)


def _formato_moneda(valor) -> str:
    return f"${_safe_float(valor):,.2f}"


def _leer_estado_directo(clave: str) -> dict:
    datos = cargar_estado(clave) or {}
    return datos if isinstance(datos, dict) else {}


def _leer_acta_inicio() -> dict:
    return _leer_estado_directo("acta_inicio_obra")


def _leer_contrato_interventoria() -> dict:
    return _leer_estado_directo("contrato_interventoria")


def _leer_presupuesto_obra() -> dict:
    return _leer_estado_directo("presupuesto_obra")


def _leer_contrato_obra() -> dict:
    return _leer_estado_directo("contrato_obra")


def _primero_no_vacio(*valores):
    for valor in valores:
        if isinstance(valor, str):
            if valor.strip():
                return valor.strip()
        elif valor not in (None, "", []):
            return valor
    return ""


def _valor_contrato_desde_fuentes(acta_inicio: dict, contrato_obra: dict) -> float:
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


def _construir_catalogo_presupuesto(presupuesto_obra: dict):
    tablas = presupuesto_obra.get("__tablas__", {}) if isinstance(presupuesto_obra, dict) else {}
    grupos = tablas.get("grupos_presupuesto_obra", []) or []

    catalogo = []
    mapa = {}

    for grupo in grupos:
        for fila in grupo.get("rows", []) or []:
            item_no = _texto(fila.get("ITEM"))
            descripcion = _texto(fila.get("DESCRIPCIÓN"))
            valor_total = _safe_float(fila.get("VR TOTAL"), 0.0)

            if not item_no or not descripcion:
                continue

            codigo = f"{item_no} | {descripcion}"
            registro = {
                "codigo": codigo,
                "item_no": item_no,
                "descripcion": descripcion,
                "valor": valor_total,
            }
            catalogo.append(registro)
            mapa[codigo] = registro

    catalogo = sorted(catalogo, key=lambda x: (x["item_no"], x["descripcion"]))
    return catalogo, mapa


def _columnas_meses(cantidad_meses: int):
    return [f"VR. MES {i}" for i in range(1, max(MIN_MESES, int(cantidad_meses)) + 1)]


def _fila_vacia(columnas_meses):
    fila = {
        "ACTIVIDAD": "",
        "ÍTEM No.": "",
        "DESCRIPCIÓN DEL ÍTEM": "",
        "VALOR": 0.0,
        "VALOR PROGRAMA APROBADO": 0.0,
        "%": 0.0,
    }
    for col in columnas_meses:
        fila[col] = 0.0
    return fila


def _normalizar_filas(rows, columnas_meses):
    rows_out = []
    for fila in rows or []:
        base = _fila_vacia(columnas_meses)
        if isinstance(fila, dict):
            for k, v in fila.items():
                if k in base:
                    base[k] = v
        rows_out.append(base)
    return rows_out


def _inicializar_estado():
    group_id_actual = _texto(st.session_state.get("group_id"))
    cache_group = _texto(st.session_state.get("_plan_inversion_anticipo_group"))

    if cache_group != group_id_actual or "plan_inversion_anticipo_datos" not in st.session_state:
        cargado = cargar_estado(CLAVE_GUARDADO) or {}
        if not isinstance(cargado, dict):
            cargado = {}

        cantidad_meses = int(cargado.get("cantidad_meses", MIN_MESES) or MIN_MESES)
        columnas_meses = _columnas_meses(cantidad_meses)
        rows = _normalizar_filas(cargado.get("rows", []), columnas_meses)

        if not rows:
            rows = [_fila_vacia(columnas_meses) for _ in range(FILAS_INICIALES)]

        st.session_state["plan_inversion_anticipo_datos"] = {
            "fecha_documento": _parse_fecha(cargado.get("fecha_documento")) or date.today(),
            "cantidad_meses": cantidad_meses,
            "rows": rows,
        }
        st.session_state["_plan_inversion_anticipo_group"] = group_id_actual


def _guardar():
    guardar_estado(CLAVE_GUARDADO, st.session_state["plan_inversion_anticipo_datos"])
    st.success("Plan de inversión del anticipo guardado correctamente.")


def _sincronizar_filas_con_meses(datos):
    cantidad_meses = int(datos.get("cantidad_meses", MIN_MESES) or MIN_MESES)
    columnas_meses = _columnas_meses(cantidad_meses)
    datos["rows"] = _normalizar_filas(datos.get("rows", []), columnas_meses)
    return columnas_meses


def _recalcular_filas(datos, mapa_catalogo, valor_anticipo):
    columnas_meses = _sincronizar_filas_con_meses(datos)
    filas_actualizadas = []

    for fila in datos.get("rows", []):
        fila_nueva = _fila_vacia(columnas_meses)
        actividad = _texto(fila.get("ACTIVIDAD"))

        if actividad and actividad in mapa_catalogo:
            info = mapa_catalogo[actividad]
            fila_nueva["ACTIVIDAD"] = actividad
            fila_nueva["ÍTEM No."] = info["item_no"]
            fila_nueva["DESCRIPCIÓN DEL ÍTEM"] = info["descripcion"]
            fila_nueva["VALOR"] = _safe_float(info["valor"], 0.0)
        else:
            fila_nueva["ACTIVIDAD"] = actividad

        suma_meses = 0.0
        for col in columnas_meses:
            valor_mes = _safe_float(fila.get(col), 0.0)
            fila_nueva[col] = valor_mes
            suma_meses += valor_mes

        fila_nueva["VALOR PROGRAMA APROBADO"] = round(suma_meses, 2)
        fila_nueva["%"] = round((suma_meses / valor_anticipo) * 100.0, 4) if valor_anticipo > 0 else 0.0
        filas_actualizadas.append(fila_nueva)

    datos["rows"] = filas_actualizadas
    return columnas_meses


def _dataframe_para_editor(datos, columnas_meses):
    columnas = ["ACTIVIDAD", "ÍTEM No.", "DESCRIPCIÓN DEL ÍTEM", "VALOR"] + columnas_meses + ["VALOR PROGRAMA APROBADO", "%"]
    return pd.DataFrame(datos.get("rows", []), columns=columnas)


def _sumas_totales(df, columnas_meses):
    total_valor = _safe_float(df["VALOR"].sum(), 0.0) if "VALOR" in df.columns else 0.0
    total_programado = _safe_float(df["VALOR PROGRAMA APROBADO"].sum(), 0.0) if "VALOR PROGRAMA APROBADO" in df.columns else 0.0
    total_porcentaje = _safe_float(df["%"].sum(), 0.0) if "%" in df.columns else 0.0
    totales_meses = {col: _safe_float(df[col].sum(), 0.0) for col in columnas_meses if col in df.columns}
    return total_valor, total_programado, total_porcentaje, totales_meses


def _duplicados_actividad(rows):
    vistos = set()
    repetidos = set()
    for fila in rows:
        actividad = _texto(fila.get("ACTIVIDAD"))
        if not actividad:
            continue
        if actividad in vistos:
            repetidos.add(actividad)
        vistos.add(actividad)
    return repetidos


def _agregar_fila(datos):
    columnas_meses = _sincronizar_filas_con_meses(datos)
    datos["rows"].append(_fila_vacia(columnas_meses))


def _quitar_fila(datos):
    if len(datos.get("rows", [])) > 1:
        datos["rows"].pop()


def _generar_word(
    datos,
    contrato_obra_no,
    contratista,
    objeto_contrato,
    contrato_interventoria_no,
    interventor,
    valor_contrato,
    valor_anticipo,
    porcentaje_anticipo,
    nombre_firma_contratista,
    nombre_firma_interventor,
):
    columnas_meses = _columnas_meses(datos.get("cantidad_meses", MIN_MESES))
    df = _dataframe_para_editor(datos, columnas_meses)

    doc = Document()
    doc.add_heading("PLAN DE INVERSIÓN DEL ANTICIPO", level=1)

    doc.add_paragraph(f"Fecha: {_fecha_texto(datos.get('fecha_documento'))}")
    doc.add_paragraph(f"Contrato de obra No.: {contrato_obra_no}")
    doc.add_paragraph(f"Contratista: {contratista}")
    doc.add_paragraph(f"Objeto del contrato: {objeto_contrato}")
    doc.add_paragraph(f"Contrato de interventoría No.: {contrato_interventoria_no}")
    doc.add_paragraph(f"Interventor: {interventor}")

    doc.add_paragraph("")
    doc.add_paragraph(f"Valor del contrato: {_formato_moneda(valor_contrato)}")
    doc.add_paragraph(f"Porcentaje del anticipo: {porcentaje_anticipo:.2f}%")
    doc.add_paragraph(f"Valor del anticipo: {_formato_moneda(valor_anticipo)}")

    doc.add_paragraph("")
    tabla = doc.add_table(rows=1, cols=4 + len(columnas_meses) + 2)
    tabla.style = "Table Grid"

    encabezados = ["ÍTEM No.", "DESCRIPCIÓN DEL ÍTEM", "VALOR"] + columnas_meses + ["VALOR PROGRAMA APROBADO", "%"]
    for i, enc in enumerate(encabezados):
        tabla.rows[0].cells[i].text = enc

    for _, fila in df.iterrows():
        row_cells = tabla.add_row().cells
        row_cells[0].text = _texto(fila.get("ÍTEM No.", ""))
        row_cells[1].text = _texto(fila.get("DESCRIPCIÓN DEL ÍTEM", ""))
        row_cells[2].text = _formato_moneda(fila.get("VALOR", 0.0))

        idx = 3
        for col in columnas_meses:
            row_cells[idx].text = _formato_moneda(fila.get(col, 0.0))
            idx += 1

        row_cells[idx].text = _formato_moneda(fila.get("VALOR PROGRAMA APROBADO", 0.0))
        row_cells[idx + 1].text = f"{_safe_float(fila.get('%', 0.0)):.4f}%"

    total_valor, total_programado, total_porcentaje, totales_meses = _sumas_totales(df, columnas_meses)

    doc.add_paragraph("")
    doc.add_paragraph(f"Total valor: {_formato_moneda(total_valor)}")
    for col in columnas_meses:
        doc.add_paragraph(f"Total {col}: {_formato_moneda(totales_meses.get(col, 0.0))}")
    doc.add_paragraph(f"Total valor programa aprobado: {_formato_moneda(total_programado)}")
    doc.add_paragraph(f"Total %: {total_porcentaje:.4f}%")

    doc.add_paragraph("")
    tabla_firmas = doc.add_table(rows=2, cols=2)
    tabla_firmas.style = "Table Grid"
    tabla_firmas.cell(0, 0).text = "CONTRATISTA"
    tabla_firmas.cell(0, 1).text = "INTERVENTOR"
    tabla_firmas.cell(1, 0).text = _texto(nombre_firma_contratista)
    tabla_firmas.cell(1, 1).text = _texto(nombre_firma_interventor)

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


# ==========================================================
# CARGA SEGURA POR GRUPO ACTUAL
# ==========================================================
_inicializar_estado()
datos = st.session_state["plan_inversion_anticipo_datos"]

acta_inicio = _leer_acta_inicio()
contrato_interventoria = _leer_contrato_interventoria()
presupuesto_obra = _leer_presupuesto_obra()
contrato_obra = _leer_contrato_obra()

catalogo_presupuesto, mapa_catalogo = _construir_catalogo_presupuesto(presupuesto_obra)

valor_contrato = _valor_contrato_desde_fuentes(acta_inicio, contrato_obra)
valor_anticipo = round(valor_contrato * (PORCENTAJE_ANTICIPO / 100.0), 2)

contrato_obra_no = _primero_no_vacio(
    acta_inicio.get("numero_contrato"),
    contrato_obra.get("numero_contrato"),
)
contratista = _primero_no_vacio(
    acta_inicio.get("nombre_firma_contratista"),
    contrato_obra.get("nombre_contratista"),
)
objeto_contrato = _primero_no_vacio(
    acta_inicio.get("objeto_contrato_obra"),
    acta_inicio.get("objeto_general"),
    contrato_obra.get("objeto_general"),
)
contrato_interventoria_no = _primero_no_vacio(
    contrato_interventoria.get("numero_proceso_contratacion"),
    contrato_interventoria.get("numero_contrato"),
)
interventor = _primero_no_vacio(
    acta_inicio.get("nombre_firma_interventor"),
    contrato_interventoria.get("nombre_interventor"),
    contrato_interventoria.get("firmante_interventor"),
)

nombre_firma_contratista = _primero_no_vacio(
    acta_inicio.get("nombre_firma_contratista"),
    contratista,
)
nombre_firma_interventor = _primero_no_vacio(
    acta_inicio.get("nombre_firma_interventor"),
    interventor,
)

# ==========================================================
# UI
# ==========================================================
st.markdown(
    """
    <style>
    .titulo-plan {
        font-size: 30px;
        font-weight: 800;
        margin-bottom: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="titulo-plan">PLAN DE INVERSIÓN DEL ANTICIPO</div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("🧭 Acciones")
    if st.button("💾 Guardar plan", type="primary", key="guardar_plan_anticipo_sidebar"):
        _guardar()

with st.container(border=True):
    col1, col2 = st.columns([1, 1])
    with col1:
        datos["fecha_documento"] = st.date_input(
            "Fecha del documento",
            value=_parse_fecha(datos.get("fecha_documento")) or date.today(),
            format="DD/MM/YYYY",
            key="plan_anticipo_fecha_documento",
        )
    with col2:
        datos["cantidad_meses"] = int(
            st.number_input(
                "Cantidad total de meses",
                min_value=MIN_MESES,
                value=int(datos.get("cantidad_meses", MIN_MESES) or MIN_MESES),
                step=1,
                key="plan_anticipo_cantidad_meses",
            )
        )

columnas_meses = _sincronizar_filas_con_meses(datos)

with st.container(border=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        st.text_input("Valor del contrato", value=_formato_moneda(valor_contrato), disabled=True, key="pia_valor_contrato")
    with c2:
        st.text_input("Porcentaje del anticipo", value=f"{PORCENTAJE_ANTICIPO:.2f}%", disabled=True, key="pia_porcentaje_anticipo")
    with c3:
        st.text_input("Valor del anticipo", value=_formato_moneda(valor_anticipo), disabled=True, key="pia_valor_anticipo")

with st.container(border=True):
    c1, c2 = st.columns(2)
    with c1:
        st.text_input("Contrato de obra No.", value=_texto(contrato_obra_no), disabled=True, key="pia_contrato_obra")
        st.text_input("Contratista", value=_texto(contratista), disabled=True, key="pia_contratista")
        st.text_area("Objeto del contrato", value=_texto(objeto_contrato), disabled=True, height=110, key="pia_objeto")
    with c2:
        st.text_input("Contrato de interventoría No.", value=_texto(contrato_interventoria_no), disabled=True, key="pia_contrato_interventoria")
        st.text_input("Interventor", value=_texto(interventor), disabled=True, key="pia_interventor")

with st.container(border=True):
    col_btn_1, col_btn_2 = st.columns(2)
    with col_btn_1:
        if st.button("➕ Agregar fila", use_container_width=True, key="pia_agregar_fila"):
            _agregar_fila(datos)
    with col_btn_2:
        if st.button("➖ Quitar última fila", use_container_width=True, key="pia_quitar_fila"):
            _quitar_fila(datos)

columnas_meses = _recalcular_filas(datos, mapa_catalogo, valor_anticipo)

with st.container(border=True):
    st.subheader("Detalle del plan de inversión del anticipo")

    df_editor = _dataframe_para_editor(datos, columnas_meses)

    config = {
        "ACTIVIDAD": st.column_config.SelectboxColumn(
            "Seleccionar actividad",
            options=[x["codigo"] for x in catalogo_presupuesto],
            required=False,
        ),
        "ÍTEM No.": st.column_config.TextColumn("Ítem No.", disabled=True),
        "DESCRIPCIÓN DEL ÍTEM": st.column_config.TextColumn("Descripción del ítem", disabled=True, width="large"),
        "VALOR": st.column_config.NumberColumn("Valor", format="$ %.2f", disabled=True),
        "VALOR PROGRAMA APROBADO": st.column_config.NumberColumn("Valor programa aprobado", format="$ %.2f", disabled=True),
        "%": st.column_config.NumberColumn("%", format="%.4f", disabled=True),
    }

    for col in columnas_meses:
        config[col] = st.column_config.NumberColumn(col, min_value=0.0, step=0.01, format="$ %.2f")

    columnas_editor = ["ACTIVIDAD", "ÍTEM No.", "DESCRIPCIÓN DEL ÍTEM", "VALOR"] + columnas_meses + ["VALOR PROGRAMA APROBADO", "%"]

    df_editado = st.data_editor(
        df_editor,
        width="stretch",
        hide_index=True,
        num_rows="fixed",
        key="plan_anticipo_editor",
        column_order=columnas_editor,
        column_config=config,
        disabled=["ÍTEM No.", "DESCRIPCIÓN DEL ÍTEM", "VALOR", "VALOR PROGRAMA APROBADO", "%"],
    )

    datos["rows"] = df_editado.to_dict(orient="records")
    columnas_meses = _recalcular_filas(datos, mapa_catalogo, valor_anticipo)
    df_final = _dataframe_para_editor(datos, columnas_meses)

    repetidos = _duplicados_actividad(datos["rows"])
    if repetidos:
        st.error("No se puede repetir un ítem del presupuesto en más de una fila.")

    total_valor, total_programado, total_porcentaje, totales_meses = _sumas_totales(df_final, columnas_meses)

    resumen = {
        "Concepto": ["Valor del anticipo", "Total valor programa aprobado", "Total porcentaje"],
        "Valor": [
            _formato_moneda(valor_anticipo),
            _formato_moneda(total_programado),
            f"{total_porcentaje:.4f}%",
        ],
    }
    st.dataframe(pd.DataFrame(resumen), width="stretch", hide_index=True)

    resumen_meses = pd.DataFrame(
        [{"Mes": col, "Total": _formato_moneda(totales_meses.get(col, 0.0))} for col in columnas_meses]
    )
    st.dataframe(resumen_meses, width="stretch", hide_index=True)

    validacion_valor = abs(total_programado - valor_anticipo) < 0.01
    validacion_pct = abs(total_porcentaje - 100.0) < 0.0001

    if validacion_valor:
        st.success("La suma de Valor programa aprobado coincide con el valor del anticipo.")
    else:
        st.warning("La suma de Valor programa aprobado debe ser igual al valor del anticipo.")

    if validacion_pct:
        st.success("La suma de porcentajes es 100%.")
    else:
        st.warning("La suma de porcentajes debe ser 100%.")

with st.container(border=True):
    st.subheader("Firmas")
    cf1, cf2 = st.columns(2)
    with cf1:
        st.text_input("Contratista", value=_texto(nombre_firma_contratista), disabled=True, key="pia_firma_contratista")
    with cf2:
        st.text_input("Interventor", value=_texto(nombre_firma_interventor), disabled=True, key="pia_firma_interventor")

with st.container(border=True):
    col_guardar, col_word = st.columns(2)

    with col_guardar:
        if st.button("💾 Guardar plan de inversión del anticipo", type="primary", use_container_width=True, key="pia_guardar_principal"):
            _guardar()

    with col_word:
        word_plan = _generar_word(
            datos,
            contrato_obra_no,
            contratista,
            objeto_contrato,
            contrato_interventoria_no,
            interventor,
            valor_contrato,
            valor_anticipo,
            PORCENTAJE_ANTICIPO,
            nombre_firma_contratista,
            nombre_firma_interventor,
        )
        st.download_button(
            "📥 Descargar en Word",
            data=word_plan,
            file_name="plan_inversion_anticipo.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
            key="pia_descargar_word",
        )
