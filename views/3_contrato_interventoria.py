import streamlit as st
import os
import json
import pandas as pd
from supabase_state import cargar_estado
from supabase_state import guardar_estado as guardar_estado_bd


def guardar_estado(clave, datos):
    try:
        datos_puros = json.loads(json.dumps(datos))
    except Exception:
        def limpiar(obj):
            if isinstance(obj, dict) or hasattr(obj, "items"):
                return {k: limpiar(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [limpiar(x) for x in obj]
            return obj

        datos_puros = limpiar(datos)

    guardar_estado_bd(clave, datos_puros)


def calcular_altura(texto, min_h=110):
    if not texto:
        return min_h
    texto_str = str(texto)
    lineas_reales = texto_str.count("\n") + 1
    lineas_por_ancho = len(texto_str) // 140
    lineas_totales = lineas_reales + lineas_por_ancho
    altura_calculada = (lineas_totales + 2) * 26
    return max(min_h, altura_calculada)


def inicializar_contrato_interventoria():
    st.session_state["contrato_interventoria_datos"] = cargar_estado("contrato_interventoria") or {}

    d = st.session_state["contrato_interventoria_datos"]

    valores_defecto = {
        "nombre_entidad": "",
        "nombre_representante_entidad": "",
        "nombre_empresa_interventora": "",
        "nombre_interventor": "",
        "numero_proceso_contratacion": "",

        "objeto_general": "",
        "alcance_objeto": "",

        "plazo_contrato": "",

        "valor_contrato_numeros": "",
        "valor_contrato_letras": "",
        "numero_smmlv": "",
        "anio_suscripcion": "",
        "dias_habiles_pago": "",

        "obligaciones_especificas_interventor": "",

        "clausula_penal_porcentaje_valor": "",

        "dias_presentacion_garantia": "",

        "termino_liquidacion": "",

        "lugar_ejecucion": "",
        "lugar_perfeccionamiento": "",
        "fecha_suscripcion": "",

        "firmante_entidad": "",
        "firmante_interventor": "",
    }

    for k, v in valores_defecto.items():
        if k not in d:
            d[k] = v

    if "multas_interventoria" not in d or not isinstance(d["multas_interventoria"], list) or len(d["multas_interventoria"]) == 0:
        d["multas_interventoria"] = [
            {"causal": "Atraso o incumplimiento del Cronograma", "porcentaje": ""},
            {"causal": "No mantener en vigor las Garantías", "porcentaje": ""},
            {"causal": "No entrega la información completa que le solicite el supervisor", "porcentaje": ""},
            {"causal": "Atraso imputable al Interventor", "porcentaje": ""},
            {"causal": "Por incumplir, sin justa causa, las órdenes que el supervisor dé", "porcentaje": ""},
            {"causal": "Por cambiar el equipo de trabajo presentado en la oferta, sin la aprobación previa del supervisor", "porcentaje": ""},
        ]

    if "garantias_interventoria" not in d or not isinstance(d["garantias_interventoria"], list) or len(d["garantias_interventoria"]) == 0:
        d["garantias_interventoria"] = [
            {"amparo": "", "vigencia": "", "valor_asegurado": ""}
        ]


def guardar_y_refrescar():
    guardar_estado("contrato_interventoria", datos)
    st.success("Sección guardada correctamente.")


inicializar_contrato_interventoria()
datos = st.session_state["contrato_interventoria_datos"]

st.markdown("""
    <style>
    .titulo-seccion { font-size: 32px !important; font-weight: 800 !important; color: #7A0019; }
    .subtitulo-gris { font-size: 16px !important; color: #666; margin-bottom: 15px; }
    div[data-testid="stProgress"] > div > div > div > div { background-color: #C62828 !important; }
    section[data-testid="stSidebar"] { background-color: #f4f4f4; }
    .stButton > button { width: 100%; border-radius: 6px; height: 3em; font-weight: bold; }
    button[kind="primary"] {
        background-color: #7A0019 !important;
        border-color: #7A0019 !important;
        color: white !important;
    }
    button[kind="primary"]:hover {
        background-color: #5C0013 !important;
        border-color: #5C0013 !important;
        color: white !important;
    }
    </style>
""", unsafe_allow_html=True)

col_t, col_l = st.columns([4, 1], vertical_alignment="center")
with col_t:
    st.markdown('<div class="titulo-seccion">📄 Contrato de interventoría</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subtitulo-gris">Diligencie los datos base para construir automáticamente el contrato de interventoría.</div>',
        unsafe_allow_html=True
    )

    campos_clave = [
        datos["nombre_entidad"],
        datos["nombre_interventor"],
        datos["objeto_general"],
        datos["plazo_contrato"],
        datos["valor_contrato_numeros"],
        datos["lugar_ejecucion"],
        datos["fecha_suscripcion"],
    ]
    completos = sum(1 for x in campos_clave if str(x).strip())
    st.progress(completos / 7, text=f"Progreso General: {int((completos / 7) * 100)}%")

with col_l:
    if os.path.exists("unnamed.jpg"):
        st.image("unnamed.jpg", use_container_width=True)

st.divider()

with st.sidebar:
    st.header("🧭 Acciones")
    if st.button("💾 Guardar todo", type="primary", key="guardar_todo_sidebar_interventoria"):
        guardar_estado("contrato_interventoria", datos)
        st.success("Información del contrato guardada.")
    st.markdown("---")
    st.markdown("**Módulo actual:** Contrato de interventoría - captura")


with st.expander("1. Datos generales", expanded=True):
    c1, c2 = st.columns(2)

    with c1:
        datos["nombre_entidad"] = st.text_input(
            "Nombre de la Entidad",
            value=datos["nombre_entidad"],
            key="int_nombre_entidad"
        )
        datos["nombre_representante_entidad"] = st.text_input(
            "Nombre del representante de la Entidad",
            value=datos["nombre_representante_entidad"],
            key="int_nombre_representante_entidad"
        )
        datos["nombre_interventor"] = st.text_input(
            "Nombre del Interventor",
            value=datos["nombre_interventor"],
            key="int_nombre_interventor"
        )

    with c2:
        datos["nombre_empresa_interventora"] = st.text_input(
            "Nombre de la empresa interventora",
            value=datos["nombre_empresa_interventora"],
            key="int_nombre_empresa_interventora"
        )
        datos["numero_proceso_contratacion"] = st.text_input(
            "Número del Proceso de Contratación",
            value=datos["numero_proceso_contratacion"],
            key="int_numero_proceso_contratacion"
        )
    if st.button("Guardar sección 1", key="guardar_int_1"):
        guardar_y_refrescar()


with st.expander("2. Objeto y alcance", expanded=False):
    datos["objeto_general"] = st.text_area(
        "Descripción general del objeto contractual",
        value=datos["objeto_general"],
        height=calcular_altura(datos["objeto_general"]),
        key="int_objeto_general"
    )

    datos["alcance_objeto"] = st.text_area(
        "Alcance del objeto",
        value=datos["alcance_objeto"],
        height=calcular_altura(datos["alcance_objeto"], min_h=180),
        key="int_alcance_objeto"
    )

    if st.button("Guardar sección 2", key="guardar_int_2"):
        guardar_y_refrescar()


with st.expander("3. Plazo", expanded=False):
    datos["plazo_contrato"] = st.text_input(
        "Plazo del contrato",
        value=datos["plazo_contrato"],
        key="int_plazo_contrato"
    )

    if st.button("Guardar sección 3", key="guardar_int_3"):
        guardar_y_refrescar()


with st.expander("4. Valor y forma de pago", expanded=False):
    c1, c2 = st.columns(2)

    with c1:
        datos["valor_contrato_numeros"] = st.text_input(
            "Valor del contrato en números",
            value=datos["valor_contrato_numeros"],
            key="int_valor_contrato_numeros"
        )
        datos["numero_smmlv"] = st.text_input(
            "Número de SMMLV",
            value=datos["numero_smmlv"],
            key="int_numero_smmlv"
        )
        datos["dias_habiles_pago"] = st.text_input(
            "Días hábiles para pago",
            value=datos["dias_habiles_pago"],
            key="int_dias_habiles_pago"
        )

    with c2:
        datos["valor_contrato_letras"] = st.text_input(
            "Valor del contrato en letras",
            value=datos["valor_contrato_letras"],
            key="int_valor_contrato_letras"
        )
        datos["anio_suscripcion"] = st.text_input(
            "Año de suscripción",
            value=datos["anio_suscripcion"],
            key="int_anio_suscripcion"
        )

    if st.button("Guardar sección 4", key="guardar_int_4"):
        guardar_y_refrescar()


with st.expander("5. Obligaciones específicas del interventor", expanded=False):
    datos["obligaciones_especificas_interventor"] = st.text_area(
        "Obligaciones específicas del interventor",
        value=datos["obligaciones_especificas_interventor"],
        height=calcular_altura(datos["obligaciones_especificas_interventor"], min_h=220),
        key="int_obligaciones_especificas_interventor"
    )

    if st.button("Guardar sección 5", key="guardar_int_5"):
        guardar_y_refrescar()


with st.expander("6. Cláusula penal", expanded=False):
    datos["clausula_penal_porcentaje_valor"] = st.text_input(
        "Porcentaje o valor aplicable de la cláusula penal",
        value=datos["clausula_penal_porcentaje_valor"],
        key="int_clausula_penal_porcentaje_valor"
    )

    if st.button("Guardar sección 6", key="guardar_int_6"):
        guardar_y_refrescar()

with st.expander("7. Multas", expanded=False):
    st.markdown("**Tabla de multas**")

    st.session_state["df_multas_interventoria"] = pd.DataFrame(datos["multas_interventoria"])

    df_multas = st.data_editor(
        st.session_state["df_multas_interventoria"],
        num_rows="fixed",
        use_container_width=True,
        key="editor_multas_interventoria",
        disabled=["causal"]
    )

    datos["multas_interventoria"] = df_multas.fillna("").to_dict(orient="records")

    if st.button("Guardar sección 7", key="guardar_int_7_multas"):
        st.session_state["df_multas_interventoria"] = df_multas.copy()
        datos["multas_interventoria"] = df_multas.fillna("").to_dict(orient="records")
        guardar_y_refrescar()


with st.expander("8. Garantías", expanded=False):
    datos["dias_presentacion_garantia"] = st.text_input(
        "Días para presentar la garantía",
        value=datos["dias_presentacion_garantia"],
        key="int_dias_presentacion_garantia"
    )

    st.text_input(
        "Asegurado / beneficiario",
        value=datos["nombre_entidad"],
        key="int_asegurado_beneficiario_visual",
        disabled=True
    )

    st.session_state["df_garantias_interventoria"] = pd.DataFrame(datos["garantias_interventoria"])

    df_editado = st.data_editor(
        st.session_state["df_garantias_interventoria"],
        num_rows="dynamic",
        use_container_width=True,
        key="editor_garantias_interventoria"
    )

    datos["garantias_interventoria"] = df_editado.fillna("").to_dict(orient="records")

    if st.button("Guardar sección 8", key="guardar_int_8"):
        st.session_state["df_garantias_interventoria"] = df_editado.copy()
        datos["garantias_interventoria"] = df_editado.fillna("").to_dict(orient="records")
        guardar_y_refrescar()


with st.expander("9. Liquidación", expanded=False):
    datos["termino_liquidacion"] = st.text_input(
        "Término para la liquidación",
        value=datos["termino_liquidacion"],
        key="int_termino_liquidacion"
    )

    if st.button("Guardar sección 9", key="guardar_int_9"):
        guardar_y_refrescar()


with st.expander("10. Lugar y domicilio", expanded=False):
    c1, c2 = st.columns(2)

    with c1:
        datos["lugar_ejecucion"] = st.text_input(
            "Lugar de ejecución",
            value=datos["lugar_ejecucion"],
            key="int_lugar_ejecucion"
        )

    with c2:
        datos["lugar_perfeccionamiento"] = st.text_input(
            "Lugar de perfeccionamiento del contrato",
            value=datos["lugar_perfeccionamiento"],
            key="int_lugar_perfeccionamiento"
        )
        datos["fecha_suscripcion"] = st.text_input(
            "Fecha de suscripción",
            value=datos["fecha_suscripcion"],
            key="int_fecha_suscripcion"
        )
    if st.button("Guardar sección 10", key="guardar_int_10"):
        guardar_y_refrescar()


with st.expander("11. Firmas", expanded=False):
    c1, c2 = st.columns(2)

    with c1:
        datos["firmante_entidad"] = st.text_input(
            "Firmante por la Entidad",
            value=datos["firmante_entidad"],
            key="int_firmante_entidad"
        )

    with c2:
        datos["firmante_interventor"] = st.text_input(
            "Firmante por el Interventor",
            value=datos["firmante_interventor"],
            key="int_firmante_interventor"
        )

    if st.button("Guardar sección 11", key="guardar_int_11"):
        guardar_y_refrescar()


st.divider()

col_a, col_b = st.columns([1, 1])
with col_a:
    if st.button("💾 Guardar formulario completo", type="primary", key="guardar_formulario_completo_interventoria"):
        datos["garantias_interventoria"] = st.session_state["df_garantias_interventoria"].fillna("").to_dict(orient="records")
        guardar_estado("contrato_interventoria", datos)
        st.success("Formulario completo guardado.")
with col_b:
    st.info("La hoja siguiente podrá usar estos datos para construir el contrato de interventoría.")
