from io import BytesIO
from datetime import date, datetime

import pandas as pd
import streamlit as st
from docx import Document

from supabase_state import cargar_estado


def _texto(valor):
    if valor is None:
        return ""
    return str(valor).strip()


def _safe_float(valor, default=0.0):
    try:
        if valor is None or valor == "":
            return float(default)
        if isinstance(valor, (int, float)):
            return float(valor)
        txt = str(valor).strip().replace("$", "").replace(" ", "")
        txt = txt.replace(".", "").replace(",", ".")
        return float(txt)
    except Exception:
        return float(default)


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
    return None


def _fecha_texto(valor):
    fecha = _parse_fecha(valor)
    if not fecha:
        return ""
    return fecha.strftime("%d/%m/%Y")


def _moneda(valor):
    return f"$ {_safe_float(valor, 0.0):,.2f}"


def _leer_estado(clave):
    datos = cargar_estado(clave) or {}
    return datos if isinstance(datos, dict) else {}


def _primero_no_vacio(*valores):
    for valor in valores:
        txt = _texto(valor)
        if txt:
            return txt
    return ""


def _valor_contrato(acta_inicio, contrato_obra):
    for valor in [
        acta_inicio.get("valor_total_contrato_obra"),
        acta_inicio.get("valor_contrato"),
        acta_inicio.get("valor"),
        contrato_obra.get("valor_total_numeros"),
        contrato_obra.get("valor_contrato"),
        contrato_obra.get("valor"),
    ]:
        numero = _safe_float(valor, 0.0)
        if numero > 0:
            return numero
    return 0.0


def _datos_generales(acta_inicio, contrato_obra):
    return {
        "numero_contrato": _primero_no_vacio(
            acta_inicio.get("numero_contrato"),
            contrato_obra.get("numero_contrato"),
        ),
        "contratante": _primero_no_vacio(
            contrato_obra.get("nombre_entidad"),
            acta_inicio.get("contratante"),
        ),
        "nit_contratante": _primero_no_vacio(
            contrato_obra.get("nit_entidad"),
            acta_inicio.get("nit_contratante"),
        ),
        "contratista": _primero_no_vacio(
            acta_inicio.get("nombre_firma_contratista"),
            contrato_obra.get("nombre_contratista"),
        ),
        "nit_contratista": _primero_no_vacio(
            contrato_obra.get("nit_contratista"),
            acta_inicio.get("nit_contratista"),
        ),
        "interventor": _primero_no_vacio(
            acta_inicio.get("nombre_firma_interventor"),
            contrato_obra.get("nombre_interventor"),
            contrato_obra.get("nombre_supervisor"),
        ),
        "objeto": _primero_no_vacio(
            acta_inicio.get("objeto_contrato"),
            contrato_obra.get("objeto_general"),
            contrato_obra.get("objeto_contrato"),
            contrato_obra.get("objeto"),
        ),
        "valor_contrato": _valor_contrato(acta_inicio, contrato_obra),
        "plazo": _primero_no_vacio(
            acta_inicio.get("plazo_ejecucion"),
            contrato_obra.get("plazo_ejecucion"),
        ),
        "fecha_inicio": _parse_fecha(
            _primero_no_vacio(
                acta_inicio.get("fecha_inicio"),
                acta_inicio.get("fecha_presente_acta"),
            )
        ),
    }


def _suspensiones(control_obra):
    rows = control_obra.get("suspensiones_rows", []) or []
    return [fila for fila in rows if isinstance(fila, dict)]


def _tipo_acta(fila):
    if _texto(fila.get("ACTA DE AMPLIACIÓN SUSPENSIÓN No.")):
        return "AMPLIACIÓN DE SUSPENSIÓN"
    return "SUSPENSIÓN"


def _etiqueta_suspension(fila, idx):
    tipo = _tipo_acta(fila)
    numero_susp = _texto(fila.get("ACTA DE SUSPENSIÓN No."))
    numero_amp = _texto(fila.get("ACTA DE AMPLIACIÓN SUSPENSIÓN No."))
    numero = numero_amp if tipo == "AMPLIACIÓN DE SUSPENSIÓN" else numero_susp
    desde = _fecha_texto(fila.get("DESDE"))
    hasta = _fecha_texto(fila.get("HASTA"))
    return f"{idx + 1}. {tipo} No. {numero} | Desde {desde} hasta {hasta}"


def _generar_word(datos_generales, fila):
    doc = Document()
    tipo = _tipo_acta(fila)
    titulo = "ACTA DE AMPLIACIÓN DE SUSPENSIÓN" if tipo == "AMPLIACIÓN DE SUSPENSIÓN" else "ACTA DE SUSPENSIÓN"

    doc.add_heading(titulo, level=1)
    doc.add_paragraph(f"CONTRATO No.: {_texto(datos_generales.get('numero_contrato'))}")
    doc.add_paragraph(f"CONTRATANTE: {_texto(datos_generales.get('contratante'))}")
    doc.add_paragraph(f"NIT. C.C. CONTRATANTE: {_texto(datos_generales.get('nit_contratante'))}")
    doc.add_paragraph(f"CONTRATISTA: {_texto(datos_generales.get('contratista'))}")
    doc.add_paragraph(f"NIT. C.C. CONTRATISTA: {_texto(datos_generales.get('nit_contratista'))}")
    doc.add_paragraph(f"INTERVENTOR Y/O SUPERVISOR: {_texto(datos_generales.get('interventor'))}")
    doc.add_paragraph(f"OBJETO: {_texto(datos_generales.get('objeto'))}")
    doc.add_paragraph(f"VALOR DEL CONTRATO: {_moneda(datos_generales.get('valor_contrato'))}")
    doc.add_paragraph(f"PLAZO DE EJECUCIÓN: {_texto(datos_generales.get('plazo'))}")

    doc.add_paragraph("")
    doc.add_paragraph(f"ACTA DE SUSPENSIÓN No.: {_texto(fila.get('ACTA DE SUSPENSIÓN No.'))}")
    doc.add_paragraph(f"ACTA DE AMPLIACIÓN SUSPENSIÓN No.: {_texto(fila.get('ACTA DE AMPLIACIÓN SUSPENSIÓN No.'))}")
    doc.add_paragraph(f"FECHA DEL ACTA: {_fecha_texto(fila.get('FECHA DEL ACTA'))}")
    doc.add_paragraph(f"DESDE: {_fecha_texto(fila.get('DESDE'))}")
    doc.add_paragraph(f"HASTA: {_fecha_texto(fila.get('HASTA'))}")
    doc.add_paragraph(f"PERIODO DE SUSPENSIÓN: {_texto(fila.get('PERIODO DE SUSPENSIÓN'))} días")
    doc.add_paragraph(f"NUEVA FECHA DE FINALIZACIÓN: {_fecha_texto(fila.get('NUEVA FECHA DE FINALIZACIÓN'))}")

    doc.add_paragraph("")
    doc.add_paragraph(
        "Las partes dejan constancia de la suspensión o ampliación de suspensión del contrato, "
        "de acuerdo con la información registrada en el control contractual."
    )

    doc.add_paragraph("")
    tabla_firmas = doc.add_table(rows=2, cols=3)
    tabla_firmas.style = "Table Grid"
    tabla_firmas.cell(0, 0).text = "INTERVENTOR Y/O SUPERVISOR"
    tabla_firmas.cell(0, 1).text = "CONTRATISTA"
    tabla_firmas.cell(0, 2).text = "CONTRATANTE"
    tabla_firmas.cell(1, 0).text = _texto(datos_generales.get("interventor"))
    tabla_firmas.cell(1, 1).text = _texto(datos_generales.get("contratista"))
    tabla_firmas.cell(1, 2).text = _texto(datos_generales.get("contratante"))

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


acta_inicio = _leer_estado("acta_inicio_obra")
contrato_obra = _leer_estado("contrato_obra")
control_obra = _leer_estado("control_obra")

generales = _datos_generales(acta_inicio, contrato_obra)
suspensiones = _suspensiones(control_obra)

st.markdown("# ACTA DE SUSPENSION")

if not suspensiones:
    st.warning("No hay registros en la tabla de suspensiones de la hoja 24.")
    st.stop()

opciones = {_etiqueta_suspension(fila, idx): idx for idx, fila in enumerate(suspensiones)}
seleccion = st.selectbox("Seleccione el acta o ampliación", options=list(opciones.keys()))
fila = suspensiones[opciones[seleccion]]

st.markdown("### DATOS GENERALES")
col1, col2 = st.columns(2)
with col1:
    st.text_input("CONTRATO DE OBRA No.", value=generales["numero_contrato"], disabled=True)
with col2:
    st.text_input("CONTRATISTA", value=generales["contratista"], disabled=True)

st.text_area("OBJETO DEL CONTRATO", value=generales["objeto"], disabled=True, height=120)

col3, col4, col5 = st.columns(3)
with col3:
    st.number_input("VALOR DEL CONTRATO", value=generales["valor_contrato"], disabled=True, format="%.2f")
with col4:
    st.text_input("PLAZO DE EJECUCIÓN", value=generales["plazo"], disabled=True)
with col5:
    st.date_input("FECHA DE INICIO", value=generales["fecha_inicio"] or date.today(), disabled=True, format="DD/MM/YYYY")

st.markdown("### INFORMACIÓN DEL ACTA")
df_acta = pd.DataFrame(
    [
        {
            "TIPO": _tipo_acta(fila),
            "ACTA DE SUSPENSIÓN No.": _texto(fila.get("ACTA DE SUSPENSIÓN No.")),
            "ACTA DE AMPLIACIÓN SUSPENSIÓN No.": _texto(fila.get("ACTA DE AMPLIACIÓN SUSPENSIÓN No.")),
            "FECHA DEL ACTA": _parse_fecha(fila.get("FECHA DEL ACTA")),
            "DESDE": _parse_fecha(fila.get("DESDE")),
            "HASTA": _parse_fecha(fila.get("HASTA")),
            "PERIODO DE SUSPENSIÓN": _safe_float(fila.get("PERIODO DE SUSPENSIÓN"), 0.0),
            "NUEVA FECHA DE FINALIZACIÓN": _parse_fecha(fila.get("NUEVA FECHA DE FINALIZACIÓN")),
        }
    ]
)

st.dataframe(df_acta, hide_index=True, width="stretch")

word = _generar_word(generales, fila)
st.download_button(
    "📄 Descargar Word",
    data=word,
    file_name="acta_suspension.docx",
    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
)
