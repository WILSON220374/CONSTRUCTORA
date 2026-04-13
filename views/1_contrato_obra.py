import streamlit as st
import os
import json
from datetime import date
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


def inicializar_contrato():
    if "contrato_obra_datos" not in st.session_state:
        st.session_state["contrato_obra_datos"] = cargar_estado("contrato_obra") or {}

    d = st.session_state["contrato_obra_datos"]

    valores_defecto = {
        "numero_contrato": "",
        "nombre_proyecto": "",
        "fecha_contrato": "",
        "lugar_celebracion": "",

        "nombre_entidad": "",
        "nit_entidad": "",
        "mision_entidad": "",
        "justificacion_general": "",
        "necesidad_contratar": "",

        "rep_entidad_nombre": "",
        "rep_entidad_tipo_doc": "Cédula de ciudadanía",
        "rep_entidad_num_doc": "",
        "rep_entidad_municipio_expedicion": "",
        "rep_entidad_cargo": "",
        "rep_entidad_num_acto": "",
        "rep_entidad_fecha_acto": "",
        "rep_entidad_fecha_posesion": "",
        "rep_entidad_num_acta_posesion": "",
        "rep_entidad_fecha_acta_posesion": "",
        "rep_entidad_norma_competencia": "",
        "rep_entidad_fecha_norma_competencia": "",

        "tipo_contratista": "Persona jurídica",
        "nombre_contratista": "",
        "nit_contratista": "",
        "matricula_mercantil": "",
        "calidad_actua_contratista": "",

        "rep_contratista_nombre": "",
        "rep_contratista_tipo_doc": "Cédula de ciudadanía",
        "rep_contratista_num_doc": "",
        "rep_contratista_ciudad_expedicion": "",

        "estudios_documentos_previos": "",
        "nombre_pliego_invitacion": "",
        "proceso_secop": "",
        "modalidad_seleccion": "Licitación pública",
        "incluido_paa": "Sí",
        "acto_adjudicacion": "",
        "motivacion_adicional": "",

        "objeto_general": "",
        "objeto_especifico": "",

        "actividades_especificas": "",
        "especificaciones_tecnicas": "",

        "valor_total_numeros": "",
        "valor_total_letras": "",
        "modalidad_pago": "Precios unitarios",
        "datos_cdp": "",
        "usa_vigencias_futuras": "No",
        "vigencias_futuras_detalle": "",
        "periodicidad_pago": "",
        "requisitos_pago": "",
        "dias_pago": "",

        "plazo_ejecucion": "",
        "cronograma_obra": "",

        "condiciones_multa": "",
        "clausula_penal_numeros": "",
        "clausula_penal_letras": "",

        "plazo_garantias_dias": "",

        "mecanismo_controversias": "Jurisdicción Contenciosa Administrativa",
        "detalle_controversias": "",

        "not_entidad_nombre": "",
        "not_entidad_cargo": "",
        "not_entidad_direccion": "",
        "not_entidad_telefono": "",
        "not_entidad_correo": "",
        "not_contratista_nombre": "",
        "not_contratista_cargo": "",
        "not_contratista_direccion": "",
        "not_contratista_telefono": "",
        "not_contratista_correo": "",

        "tipo_seguimiento": "Ambas",
        "nombre_supervisor": "",
        "nombre_interventor": "",
        "observaciones_seguimiento": "",

        "anexos_estudios_previos": True,
        "anexos_pliego": True,
        "anexos_oferta": True,
        "anexos_actas_informes": True,
        "anexos_cdp": True,
        "anexos_otros": "",

        "lugar_ejecucion": "",
        "domicilio_contractual": "",
        "fecha_celebracion": "",
        "firmante_entidad_nombre": "",
        "firmante_entidad_identificacion": "",
        "firmante_contratista_nombre": "",
        "firmante_contratista_identificacion": "",
    }

    for k, v in valores_defecto.items():
        if k not in d:
            d[k] = v

    if "garantias" not in d or not isinstance(d["garantias"], list):
        d["garantias"] = [{"amparo": "", "suficiencia": "", "vigencia": ""}]


def guardar_y_refrescar():
    guardar_estado("contrato_obra", datos)
    st.success("Sección guardada correctamente.")


inicializar_contrato()
datos = st.session_state["contrato_obra_datos"]


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
    st.markdown('<div class="titulo-seccion">📄 Contrato de obra - captura</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subtitulo-gris">Diligencie los datos base para construir automáticamente el contrato de obra pública.</div>',
        unsafe_allow_html=True
    )

    campos_clave = [
        datos["numero_contrato"],
        datos["nombre_proyecto"],
        datos["nombre_entidad"],
        datos["nombre_contratista"],
        datos["objeto_general"],
        datos["valor_total_numeros"],
        datos["plazo_ejecucion"],
        datos["lugar_ejecucion"],
    ]
    completos = sum(1 for x in campos_clave if str(x).strip())
    st.progress(completos / 8, text=f"Progreso General: {int((completos / 8) * 100)}%")

with col_l:
    if os.path.exists("unnamed.jpg"):
        st.image("unnamed.jpg", use_container_width=True)

st.divider()

with st.sidebar:
    st.header("🧭 Acciones")
    if st.button("💾 Guardar todo", type="primary", key="guardar_todo_sidebar"):
        guardar_estado("contrato_obra", datos)
        st.success("Información del contrato guardada.")
    st.markdown("---")
    st.markdown("**Módulo actual:** Contrato de obra - captura")
    st.markdown("**Hoja siguiente:** Contrato armado")


with st.expander("1. Datos generales del contrato", expanded=True):
    c1, c2 = st.columns(2)
    with c1:
        datos["numero_contrato"] = st.text_input(
            "Número de contrato",
            value=datos["numero_contrato"],
            key="numero_contrato"
        )
        datos["nombre_proyecto"] = st.text_input(
            "Nombre del proyecto",
            value=datos["nombre_proyecto"],
            key="nombre_proyecto"
        )
    with c2:
        datos["fecha_contrato"] = st.text_input(
            "Fecha del contrato",
            value=datos["fecha_contrato"],
            key="fecha_contrato"
        )
        datos["lugar_celebracion"] = st.text_input(
            "Lugar de celebración del contrato",
            value=datos["lugar_celebracion"],
            key="lugar_celebracion"
        )

    if st.button("Guardar sección 1", key="guardar_1"):
        guardar_y_refrescar()


with st.expander("2. Datos del contratante", expanded=False):
    st.markdown("**Entidad contratante**")
    c1, c2 = st.columns(2)
    with c1:
        datos["nombre_entidad"] = st.text_input(
            "Nombre de la entidad estatal contratante",
            value=datos["nombre_entidad"],
            key="nombre_entidad"
        )
        datos["nit_entidad"] = st.text_input(
            "NIT de la entidad estatal contratante",
            value=datos["nit_entidad"],
            key="nit_entidad"
        )
    with c2:
        datos["mision_entidad"] = st.text_area(
            "Misión de la entidad estatal contratante",
            value=datos["mision_entidad"],
            height=calcular_altura(datos["mision_entidad"]),
            key="mision_entidad"
        )

    datos["justificacion_general"] = st.text_area(
        "Justificación general de la contratación",
        value=datos["justificacion_general"],
        height=calcular_altura(datos["justificacion_general"]),
        key="justificacion_general"
    )
    datos["necesidad_contratar"] = st.text_area(
        "Necesidad a satisfacer",
        value=datos["necesidad_contratar"],
        height=calcular_altura(datos["necesidad_contratar"]),
        key="necesidad_contratar"
    )

    st.markdown("**Representante del contratante**")
    c3, c4 = st.columns(2)
    with c3:
        datos["rep_entidad_nombre"] = st.text_input(
            "Nombre del representante del contratante",
            value=datos["rep_entidad_nombre"],
            key="rep_entidad_nombre"
        )
        datos["rep_entidad_tipo_doc"] = st.selectbox(
            "Tipo de documento del representante del contratante",
            options=["Cédula de ciudadanía", "Cédula de extranjería", "Pasaporte", "Otro"],
            index=["Cédula de ciudadanía", "Cédula de extranjería", "Pasaporte", "Otro"].index(datos["rep_entidad_tipo_doc"])
            if datos["rep_entidad_tipo_doc"] in ["Cédula de ciudadanía", "Cédula de extranjería", "Pasaporte", "Otro"] else 0,
            key="rep_entidad_tipo_doc"
        )
        datos["rep_entidad_num_doc"] = st.text_input(
            "Número de identificación del representante del contratante",
            value=datos["rep_entidad_num_doc"],
            key="rep_entidad_num_doc"
        )
        datos["rep_entidad_municipio_expedicion"] = st.text_input(
            "Municipio de expedición del representante del contratante",
            value=datos["rep_entidad_municipio_expedicion"],
            key="rep_entidad_municipio_expedicion"
        )
        datos["rep_entidad_cargo"] = st.text_input(
            "Cargo del representante del contratante",
            value=datos["rep_entidad_cargo"],
            key="rep_entidad_cargo"
        )
        datos["rep_entidad_num_acto"] = st.text_input(
            "Número del acto administrativo de nombramiento del contratante",
            value=datos["rep_entidad_num_acto"],
            key="rep_entidad_num_acto"
        )
    with c4:
        datos["rep_entidad_fecha_acto"] = st.text_input(
            "Fecha del acto administrativo de nombramiento del contratante",
            value=datos["rep_entidad_fecha_acto"],
            key="rep_entidad_fecha_acto"
        )
        datos["rep_entidad_fecha_posesion"] = st.text_input(
            "Fecha de posesión del representante del contratante",
            value=datos["rep_entidad_fecha_posesion"],
            key="rep_entidad_fecha_posesion"
        )
        datos["rep_entidad_num_acta_posesion"] = st.text_input(
            "Número del acta de posesión del representante del contratante",
            value=datos["rep_entidad_num_acta_posesion"],
            key="rep_entidad_num_acta_posesion"
        )
        datos["rep_entidad_fecha_acta_posesion"] = st.text_input(
            "Fecha del acta de posesión del representante del contratante",
            value=datos["rep_entidad_fecha_acta_posesion"],
            key="rep_entidad_fecha_acta_posesion"
        )
        datos["rep_entidad_norma_competencia"] = st.text_area(
            "Norma que concede competencia para firmar al representante del contratante",
            value=datos["rep_entidad_norma_competencia"],
            height=calcular_altura(datos["rep_entidad_norma_competencia"]),
            key="rep_entidad_norma_competencia"
        )
        datos["rep_entidad_fecha_norma_competencia"] = st.text_input(
            "Fecha de la norma de competencia del contratante",
            value=datos["rep_entidad_fecha_norma_competencia"],
            key="rep_entidad_fecha_norma_competencia"
        )

    if st.button("Guardar sección 2", key="guardar_2"):
        guardar_y_refrescar()


with st.expander("3. Datos del contratista", expanded=False):
    st.markdown("**Contratista**")
    c1, c2 = st.columns(2)
    with c1:
        datos["tipo_contratista"] = st.selectbox(
            "Tipo de contratista",
            options=["Persona natural", "Persona jurídica", "Estructura plural"],
            index=["Persona natural", "Persona jurídica", "Estructura plural"].index(datos["tipo_contratista"])
            if datos["tipo_contratista"] in ["Persona natural", "Persona jurídica", "Estructura plural"] else 1,
            key="tipo_contratista"
        )
        datos["nombre_contratista"] = st.text_input(
            "Nombre del contratista",
            value=datos["nombre_contratista"],
            key="nombre_contratista"
        )
        datos["nit_contratista"] = st.text_input(
            "NIT del contratista",
            value=datos["nit_contratista"],
            key="nit_contratista"
        )
    with c2:
        datos["matricula_mercantil"] = st.text_input(
            "Matrícula mercantil del contratista",
            value=datos["matricula_mercantil"],
            key="matricula_mercantil"
        )
        datos["calidad_actua_contratista"] = st.text_input(
            "Calidad en la que actúa el contratista",
            value=datos["calidad_actua_contratista"],
            key="calidad_actua_contratista"
        )

    st.markdown("**Representante del contratista**")
    c3, c4 = st.columns(2)
    with c3:
        datos["rep_contratista_nombre"] = st.text_input(
            "Nombre del representante del contratista",
            value=datos["rep_contratista_nombre"],
            key="rep_contratista_nombre"
        )
        datos["rep_contratista_tipo_doc"] = st.selectbox(
            "Tipo de documento del representante del contratista",
            options=["Cédula de ciudadanía", "Cédula de extranjería", "Pasaporte", "Otro"],
            index=["Cédula de ciudadanía", "Cédula de extranjería", "Pasaporte", "Otro"].index(datos["rep_contratista_tipo_doc"])
            if datos["rep_contratista_tipo_doc"] in ["Cédula de ciudadanía", "Cédula de extranjería", "Pasaporte", "Otro"] else 0,
            key="rep_contratista_tipo_doc"
        )
    with c4:
        datos["rep_contratista_num_doc"] = st.text_input(
            "Número de identificación del representante del contratista",
            value=datos["rep_contratista_num_doc"],
            key="rep_contratista_num_doc"
        )
        datos["rep_contratista_ciudad_expedicion"] = st.text_input(
            "Ciudad de expedición del representante del contratista",
            value=datos["rep_contratista_ciudad_expedicion"],
            key="rep_contratista_ciudad_expedicion"
        )

    if st.button("Guardar sección 3", key="guardar_3"):
        guardar_y_refrescar()


with st.expander("4. Antecedentes del proceso", expanded=False):
    datos["estudios_documentos_previos"] = st.text_area(
        "Referencia a estudios y documentos previos",
        value=datos["estudios_documentos_previos"],
        height=calcular_altura(datos["estudios_documentos_previos"]),
        key="estudios_documentos_previos"
    )

    c1, c2 = st.columns(2)
    with c1:
        datos["nombre_pliego_invitacion"] = st.text_input(
            "Nombre del pliego o invitación",
            value=datos["nombre_pliego_invitacion"],
            key="nombre_pliego_invitacion"
        )
        datos["proceso_secop"] = st.text_input(
            "Identificación del proceso en SECOP",
            value=datos["proceso_secop"],
            key="proceso_secop"
        )
    with c2:
        datos["modalidad_seleccion"] = st.selectbox(
            "Modalidad de selección",
            options=["Licitación pública", "Selección abreviada", "Mínima cuantía", "Otra"],
            index=["Licitación pública", "Selección abreviada", "Mínima cuantía", "Otra"].index(datos["modalidad_seleccion"])
            if datos["modalidad_seleccion"] in ["Licitación pública", "Selección abreviada", "Mínima cuantía", "Otra"] else 0,
            key="modalidad_seleccion"
        )
        datos["incluido_paa"] = st.selectbox(
            "¿Está incluido en el Plan Anual de Adquisiciones?",
            options=["Sí", "No"],
            index=0 if datos["incluido_paa"] == "Sí" else 1,
            key="incluido_paa"
        )

    datos["acto_adjudicacion"] = st.text_input(
        "Número y fecha del acto administrativo de adjudicación",
        value=datos["acto_adjudicacion"],
        key="acto_adjudicacion"
    )
    datos["motivacion_adicional"] = st.text_area(
        "Motivación adicional",
        value=datos["motivacion_adicional"],
        height=calcular_altura(datos["motivacion_adicional"]),
        key="motivacion_adicional"
    )

    if st.button("Guardar sección 4", key="guardar_4"):
        guardar_y_refrescar()


with st.expander("5. Objeto del contrato", expanded=False):
    datos["objeto_general"] = st.text_area(
        "Descripción general del objeto contractual",
        value=datos["objeto_general"],
        height=calcular_altura(datos["objeto_general"]),
        key="objeto_general"
    )
    datos["objeto_especifico"] = st.text_area(
        "Descripción específica del objeto contractual",
        value=datos["objeto_especifico"],
        height=calcular_altura(datos["objeto_especifico"]),
        key="objeto_especifico"
    )

    if st.button("Guardar sección 5", key="guardar_5"):
        guardar_y_refrescar()


with st.expander("6. Actividades y especificaciones", expanded=False):
    datos["actividades_especificas"] = st.text_area(
        "Actividades específicas del contrato",
        value=datos["actividades_especificas"],
        height=calcular_altura(datos["actividades_especificas"], min_h=180),
        key="actividades_especificas"
    )
    datos["especificaciones_tecnicas"] = st.text_area(
        "Especificaciones técnicas",
        value=datos["especificaciones_tecnicas"],
        height=calcular_altura(datos["especificaciones_tecnicas"], min_h=180),
        key="especificaciones_tecnicas"
    )

    if st.button("Guardar sección 6", key="guardar_6"):
        guardar_y_refrescar()


with st.expander("7. Valor y forma de pago", expanded=False):
    c1, c2 = st.columns(2)
    with c1:
        datos["valor_total_numeros"] = st.text_input(
            "Valor total en números",
            value=datos["valor_total_numeros"],
            key="valor_total_numeros"
        )
        datos["modalidad_pago"] = st.selectbox(
            "Modalidad de pago",
            options=["Precios unitarios", "Precio global fijo", "Administración delegada"],
            index=["Precios unitarios", "Precio global fijo", "Administración delegada"].index(datos["modalidad_pago"])
            if datos["modalidad_pago"] in ["Precios unitarios", "Precio global fijo", "Administración delegada"] else 0,
            key="modalidad_pago"
        )
        datos["dias_pago"] = st.text_input(
            "Días para pago",
            value=datos["dias_pago"],
            key="dias_pago"
        )
    with c2:
        datos["valor_total_letras"] = st.text_input(
            "Valor total en letras",
            value=datos["valor_total_letras"],
            key="valor_total_letras"
        )
        datos["periodicidad_pago"] = st.text_input(
            "Periodicidad o periodos de pago",
            value=datos["periodicidad_pago"],
            key="periodicidad_pago"
        )
        datos["usa_vigencias_futuras"] = st.selectbox(
            "¿Usa vigencias futuras?",
            options=["Sí", "No"],
            index=0 if datos["usa_vigencias_futuras"] == "Sí" else 1,
            key="usa_vigencias_futuras"
        )

    datos["datos_cdp"] = st.text_area(
        "Datos del certificado de disponibilidad presupuestal (CDP)",
        value=datos["datos_cdp"],
        height=calcular_altura(datos["datos_cdp"]),
        key="datos_cdp"
    )

    if datos["usa_vigencias_futuras"] == "Sí":
        datos["vigencias_futuras_detalle"] = st.text_area(
            "Detalle de vigencias futuras",
            value=datos["vigencias_futuras_detalle"],
            height=calcular_altura(datos["vigencias_futuras_detalle"]),
            key="vigencias_futuras_detalle"
        )

    datos["requisitos_pago"] = st.text_area(
        "Entregables o requisitos para pago",
        value=datos["requisitos_pago"],
        height=calcular_altura(datos["requisitos_pago"]),
        key="requisitos_pago"
    )

    if st.button("Guardar sección 7", key="guardar_7"):
        guardar_y_refrescar()


with st.expander("8. Plazo y cronograma", expanded=False):
    datos["plazo_ejecucion"] = st.text_input(
        "Plazo de ejecución del contrato",
        value=datos["plazo_ejecucion"],
        key="plazo_ejecucion"
    )
    datos["cronograma_obra"] = st.text_area(
        "Cronograma estimado de obra",
        value=datos["cronograma_obra"],
        height=calcular_altura(datos["cronograma_obra"]),
        key="cronograma_obra"
    )

    if st.button("Guardar sección 8", key="guardar_8"):
        guardar_y_refrescar()


with st.expander("9. Multas y cláusula penal", expanded=False):
    datos["condiciones_multa"] = st.text_area(
        "Condiciones de multas",
        value=datos["condiciones_multa"],
        height=calcular_altura(datos["condiciones_multa"]),
        key="condiciones_multa"
    )

    c1, c2 = st.columns(2)
    with c1:
        datos["clausula_penal_numeros"] = st.text_input(
            "Valor de la cláusula penal en números",
            value=datos["clausula_penal_numeros"],
            key="clausula_penal_numeros"
        )
    with c2:
        datos["clausula_penal_letras"] = st.text_input(
            "Valor de la cláusula penal en letras",
            value=datos["clausula_penal_letras"],
            key="clausula_penal_letras"
        )

    if st.button("Guardar sección 9", key="guardar_9"):
        guardar_y_refrescar()


with st.expander("10. Garantías", expanded=False):
    st.markdown("**Tabla de garantías**")
    datos["garantias"] = st.data_editor(
        datos["garantias"],
        num_rows="dynamic",
        use_container_width=True,
        key="editor_garantias"
    )

    datos["plazo_garantias_dias"] = st.text_input(
        "Plazo en días hábiles para presentar garantías",
        value=datos["plazo_garantias_dias"],
        key="plazo_garantias_dias"
    )

    if st.button("Guardar sección 10", key="guardar_10"):
        guardar_y_refrescar()


with st.expander("11. Solución de controversias", expanded=False):
    datos["mecanismo_controversias"] = st.selectbox(
        "Mecanismo de solución de controversias",
        options=[
            "Amigable composición",
            "Conciliación",
            "Tribunal de Arbitramento",
            "Jurisdicción Contenciosa Administrativa"
        ],
        index=[
            "Amigable composición",
            "Conciliación",
            "Tribunal de Arbitramento",
            "Jurisdicción Contenciosa Administrativa"
        ].index(datos["mecanismo_controversias"])
        if datos["mecanismo_controversias"] in [
            "Amigable composición",
            "Conciliación",
            "Tribunal de Arbitramento",
            "Jurisdicción Contenciosa Administrativa"
        ] else 3,
        key="mecanismo_controversias"
    )

    datos["detalle_controversias"] = st.text_area(
        "Detalle del mecanismo seleccionado",
        value=datos["detalle_controversias"],
        height=calcular_altura(datos["detalle_controversias"]),
        key="detalle_controversias"
    )

    if st.button("Guardar sección 11", key="guardar_11"):
        guardar_y_refrescar()


with st.expander("12. Notificaciones", expanded=False):
    st.markdown("**Notificaciones del contratante**")
    c1, c2 = st.columns(2)
    with c1:
        datos["not_entidad_nombre"] = st.text_input(
            "Nombre de contacto del contratante",
            value=datos["not_entidad_nombre"],
            key="not_entidad_nombre"
        )
        datos["not_entidad_cargo"] = st.text_input(
            "Cargo del contacto del contratante",
            value=datos["not_entidad_cargo"],
            key="not_entidad_cargo"
        )
        datos["not_entidad_direccion"] = st.text_input(
            "Dirección del contratante",
            value=datos["not_entidad_direccion"],
            key="not_entidad_direccion"
        )
    with c2:
        datos["not_entidad_telefono"] = st.text_input(
            "Teléfono del contratante",
            value=datos["not_entidad_telefono"],
            key="not_entidad_telefono"
        )
        datos["not_entidad_correo"] = st.text_input(
            "Correo electrónico del contratante",
            value=datos["not_entidad_correo"],
            key="not_entidad_correo"
        )

    st.markdown("**Notificaciones del contratista**")
    c3, c4 = st.columns(2)
    with c3:
        datos["not_contratista_nombre"] = st.text_input(
            "Nombre de contacto del contratista",
            value=datos["not_contratista_nombre"],
            key="not_contratista_nombre"
        )
        datos["not_contratista_cargo"] = st.text_input(
            "Cargo del contacto del contratista",
            value=datos["not_contratista_cargo"],
            key="not_contratista_cargo"
        )
        datos["not_contratista_direccion"] = st.text_input(
            "Dirección del contratista",
            value=datos["not_contratista_direccion"],
            key="not_contratista_direccion"
        )
    with c4:
        datos["not_contratista_telefono"] = st.text_input(
            "Teléfono del contratista",
            value=datos["not_contratista_telefono"],
            key="not_contratista_telefono"
        )
        datos["not_contratista_correo"] = st.text_input(
            "Correo electrónico del contratista",
            value=datos["not_contratista_correo"],
            key="not_contratista_correo"
        )

    if st.button("Guardar sección 12", key="guardar_12"):
        guardar_y_refrescar()


with st.expander("13. Supervisión e interventoría", expanded=False):
    datos["tipo_seguimiento"] = st.selectbox(
        "Tipo de seguimiento",
        options=["Solo supervisión", "Solo interventoría", "Ambas"],
        index=["Solo supervisión", "Solo interventoría", "Ambas"].index(datos["tipo_seguimiento"])
        if datos["tipo_seguimiento"] in ["Solo supervisión", "Solo interventoría", "Ambas"] else 2,
        key="tipo_seguimiento"
    )

    c1, c2 = st.columns(2)
    with c1:
        if datos["tipo_seguimiento"] in ["Solo supervisión", "Ambas"]:
            datos["nombre_supervisor"] = st.text_input(
                "Nombre del supervisor",
                value=datos["nombre_supervisor"],
                key="nombre_supervisor"
            )
    with c2:
        if datos["tipo_seguimiento"] in ["Solo interventoría", "Ambas"]:
            datos["nombre_interventor"] = st.text_input(
                "Nombre del interventor",
                value=datos["nombre_interventor"],
                key="nombre_interventor"
            )

    datos["observaciones_seguimiento"] = st.text_area(
        "Observaciones sobre supervisión e interventoría",
        value=datos["observaciones_seguimiento"],
        height=calcular_altura(datos["observaciones_seguimiento"]),
        key="observaciones_seguimiento"
    )

    if st.button("Guardar sección 13", key="guardar_13"):
        guardar_y_refrescar()


with st.expander("14. Anexos", expanded=False):
    c1, c2 = st.columns(2)
    with c1:
        datos["anexos_estudios_previos"] = st.checkbox(
            "Estudios previos",
            value=datos["anexos_estudios_previos"],
            key="anexos_estudios_previos"
        )
        datos["anexos_pliego"] = st.checkbox(
            "Pliego de condiciones",
            value=datos["anexos_pliego"],
            key="anexos_pliego"
        )
        datos["anexos_oferta"] = st.checkbox(
            "Oferta presentada por el contratista",
            value=datos["anexos_oferta"],
            key="anexos_oferta"
        )
    with c2:
        datos["anexos_actas_informes"] = st.checkbox(
            "Actas, acuerdos, informes y documentos precontractuales",
            value=datos["anexos_actas_informes"],
            key="anexos_actas_informes"
        )
        datos["anexos_cdp"] = st.checkbox(
            "Certificado de Disponibilidad Presupuestal",
            value=datos["anexos_cdp"],
            key="anexos_cdp"
        )

    datos["anexos_otros"] = st.text_area(
        "Otros anexos",
        value=datos["anexos_otros"],
        height=calcular_altura(datos["anexos_otros"]),
        key="anexos_otros"
    )

    if st.button("Guardar sección 14", key="guardar_14"):
        guardar_y_refrescar()


with st.expander("15. Cierre y firmas", expanded=False):
    c1, c2 = st.columns(2)
    with c1:
        datos["lugar_ejecucion"] = st.text_input(
            "Lugar de ejecución",
            value=datos["lugar_ejecucion"],
            key="lugar_ejecucion"
        )
        datos["domicilio_contractual"] = st.text_input(
            "Domicilio contractual",
            value=datos["domicilio_contractual"],
            key="domicilio_contractual"
        )
        datos["fecha_celebracion"] = st.text_input(
            "Fecha de celebración del contrato",
            value=datos["fecha_celebracion"],
            key="fecha_celebracion"
        )
    with c2:
        datos["firmante_entidad_nombre"] = st.text_input(
            "Nombre del firmante del contratante",
            value=datos["firmante_entidad_nombre"],
            key="firmante_entidad_nombre"
        )
        datos["firmante_entidad_identificacion"] = st.text_input(
            "Identificación del firmante del contratante",
            value=datos["firmante_entidad_identificacion"],
            key="firmante_entidad_identificacion"
        )
        datos["firmante_contratista_nombre"] = st.text_input(
            "Nombre del firmante del contratista",
            value=datos["firmante_contratista_nombre"],
            key="firmante_contratista_nombre"
        )
        datos["firmante_contratista_identificacion"] = st.text_input(
            "Identificación del firmante del contratista",
            value=datos["firmante_contratista_identificacion"],
            key="firmante_contratista_identificacion"
        )

    if st.button("Guardar sección 15", key="guardar_15"):
        guardar_y_refrescar()


st.divider()

col_a, col_b = st.columns([1, 1])
with col_a:
    if st.button("💾 Guardar formulario completo", type="primary", key="guardar_formulario_completo"):
        guardar_estado("contrato_obra", datos)
        st.success("Formulario completo guardado.")
with col_b:
    st.info("La hoja siguiente deberá usar estos datos para construir el contrato armado.")
