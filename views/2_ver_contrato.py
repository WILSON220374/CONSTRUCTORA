import streamlit as st
import os
from supabase_state import cargar_estado


def obtener_datos_contrato():
    datos = st.session_state.get("contrato_obra_datos")
    if not datos:
        datos = cargar_estado("contrato_obra") or {}
        st.session_state["contrato_obra_datos"] = datos
    return datos


def texto_si_vacio(valor, pendiente="PENDIENTE"):
    if valor is None:
        return pendiente
    if isinstance(valor, str):
        return valor.strip() if valor.strip() else pendiente
    return str(valor)


def construir_bloque_garantias(garantias):
    if not garantias or not isinstance(garantias, list):
        return "Amparo | Suficiencia | Vigencia\n[PENDIENTE] | [PENDIENTE] | [PENDIENTE]"

    filas_validas = []
    for fila in garantias:
        if not isinstance(fila, dict):
            continue
        amparo = texto_si_vacio(fila.get("amparo", ""))
        suficiencia = texto_si_vacio(fila.get("suficiencia", ""))
        vigencia = texto_si_vacio(fila.get("vigencia", ""))
        if amparo == "PENDIENTE" and suficiencia == "PENDIENTE" and vigencia == "PENDIENTE":
            continue
        filas_validas.append(f"{amparo} | {suficiencia} | {vigencia}")

    if not filas_validas:
        return "Amparo | Suficiencia | Vigencia\n[PENDIENTE] | [PENDIENTE] | [PENDIENTE]"

    encabezado = "Amparo | Suficiencia | Vigencia"
    cuerpo = "\n".join(filas_validas)
    return f"{encabezado}\n{cuerpo}"


def construir_bloque_anexos(datos):
    anexos = []

    if datos.get("anexos_estudios_previos"):
        anexos.append("27.1. Los estudios previos.")
    if datos.get("anexos_pliego"):
        anexos.append("27.2. El Pliego de Condiciones del proceso de selección, sus anexos, adendas o cualquier otro Documento del Proceso.")
    if datos.get("anexos_oferta"):
        anexos.append("27.3. La oferta presentada por el Contratista.")
    if datos.get("anexos_actas_informes"):
        anexos.append("27.4. Las actas, acuerdos, informes y documentos precontractuales.")
    if datos.get("anexos_cdp"):
        anexos.append("27.5. Certificado de Disponibilidad Presupuestal.")

    if not anexos:
        anexos.append("27.1. [PENDIENTE]")

    return "\n".join(anexos)


def construir_contrato(datos):
    numero_contrato = texto_si_vacio(datos.get("numero_contrato"))
    nombre_proyecto = texto_si_vacio(datos.get("nombre_proyecto"))
    fecha_contrato = texto_si_vacio(datos.get("fecha_contrato"))
    lugar_celebracion = texto_si_vacio(datos.get("lugar_celebracion"))

    nombre_entidad = texto_si_vacio(datos.get("nombre_entidad"))
    nit_entidad = texto_si_vacio(datos.get("nit_entidad"))
    mision_entidad = texto_si_vacio(datos.get("mision_entidad"))
    justificacion_general = texto_si_vacio(datos.get("justificacion_general"))
    necesidad_contratar = texto_si_vacio(datos.get("necesidad_contratar"))

    rep_entidad_nombre = texto_si_vacio(datos.get("rep_entidad_nombre"))
    rep_entidad_tipo_doc = texto_si_vacio(datos.get("rep_entidad_tipo_doc"))
    rep_entidad_num_doc = texto_si_vacio(datos.get("rep_entidad_num_doc"))
    rep_entidad_municipio_expedicion = texto_si_vacio(datos.get("rep_entidad_municipio_expedicion"))
    rep_entidad_cargo = texto_si_vacio(datos.get("rep_entidad_cargo"))

    tipo_contratista = texto_si_vacio(datos.get("tipo_contratista"))
    nombre_contratista = texto_si_vacio(datos.get("nombre_contratista"))
    nit_contratista = texto_si_vacio(datos.get("nit_contratista"))

    rep_contratista_nombre = texto_si_vacio(datos.get("rep_contratista_nombre"))
    rep_contratista_tipo_doc = texto_si_vacio(datos.get("rep_contratista_tipo_doc"))
    rep_contratista_num_doc = texto_si_vacio(datos.get("rep_contratista_num_doc"))
    rep_contratista_ciudad_expedicion = texto_si_vacio(datos.get("rep_contratista_ciudad_expedicion"))

    modalidad_seleccion = texto_si_vacio(datos.get("modalidad_seleccion"))
    objeto_general = texto_si_vacio(datos.get("objeto_general"))
    objeto_especifico = texto_si_vacio(datos.get("objeto_especifico"))

    valor_total_numeros = texto_si_vacio(datos.get("valor_total_numeros"))
    valor_total_letras = texto_si_vacio(datos.get("valor_total_letras"))
    periodicidad_pago = texto_si_vacio(datos.get("periodicidad_pago"))
    dias_pago = texto_si_vacio(datos.get("dias_pago"))

    plazo_ejecucion = texto_si_vacio(datos.get("plazo_ejecucion"))

    clausula_penal_numeros = texto_si_vacio(datos.get("clausula_penal_numeros"))
    clausula_penal_letras = texto_si_vacio(datos.get("clausula_penal_letras"))

    garantias_txt = construir_bloque_garantias(datos.get("garantias", []))
    plazo_garantias_dias = texto_si_vacio(datos.get("plazo_garantias_dias"))

    not_entidad_direccion = texto_si_vacio(datos.get("not_entidad_direccion"))
    not_entidad_telefono = texto_si_vacio(datos.get("not_entidad_telefono"))
    not_entidad_correo = texto_si_vacio(datos.get("not_entidad_correo"))

    not_contratista_direccion = texto_si_vacio(datos.get("not_contratista_direccion"))
    not_contratista_telefono = texto_si_vacio(datos.get("not_contratista_telefono"))
    not_contratista_correo = texto_si_vacio(datos.get("not_contratista_correo"))

    tipo_seguimiento = texto_si_vacio(datos.get("tipo_seguimiento"))
    nombre_supervisor = texto_si_vacio(datos.get("nombre_supervisor"))
    nombre_interventor = texto_si_vacio(datos.get("nombre_interventor"))

    lugar_ejecucion = texto_si_vacio(datos.get("lugar_ejecucion"))

    anexos_txt = construir_bloque_anexos(datos)

    bloque_supervision = f"La supervisión de la ejecución y cumplimiento de las obligaciones contraídas por el Contratista a favor de la Entidad Estatal Contratante, estará a cargo de {nombre_supervisor}."
    bloque_interventoria = f"La interventoría de la ejecución y cumplimiento de las obligaciones contraídas por el Contratista a favor de la Entidad Estatal Contratante, estará a cargo de {nombre_interventor}."

    if tipo_seguimiento == "Solo supervisión":
        bloque_interventoria = "La interventoría no aplica para el presente contrato."
    elif tipo_seguimiento == "Solo interventoría":
        bloque_supervision = "La supervisión no aplica para el presente contrato."

    contrato = f"""# Contrato de obra pública {numero_contrato} para la ejecución del proyecto {nombre_proyecto} del {fecha_contrato}, celebrado entre {nombre_entidad} y {nombre_contratista}.

## Comparecencia

Entre los suscritos: {rep_entidad_nombre}, identificado con {rep_entidad_tipo_doc} No. {rep_entidad_num_doc}, expedida en {rep_entidad_municipio_expedicion}, en su calidad de {rep_entidad_cargo}, actuando en nombre y representación de {nombre_entidad}, con NIT {nit_entidad}, quien para los efectos del presente contrato se denomina la Entidad Estatal contratante; y por la otra, {rep_contratista_nombre}, identificado con {rep_contratista_tipo_doc} No. {rep_contratista_num_doc}, expedida en {rep_contratista_ciudad_expedicion}, en representación de {nombre_contratista}, identificado con NIT {nit_contratista}, quien para los efectos del presente contrato se denominará el Contratista, hemos convenido en celebrar el presente Contrato de obra pública, teniendo en cuenta las siguientes consideraciones:

I. Que la misión de {nombre_entidad} es {mision_entidad} y el contrato a celebrarse se relaciona con esta misión porque {justificacion_general}.

II. Que la necesidad a satisfacer por parte de la Entidad Estatal contratante es {necesidad_contratar}.

III. Que la modalidad de selección corresponde a {modalidad_seleccion}.

Por lo anterior, las partes celebran el presente contrato, el cual se regirá por las siguientes cláusulas:

## Cláusula 1 – Definiciones

Las expresiones utilizadas en el presente Contrato con mayúscula inicial deben ser entendidas con el significado que se asigna en el documento tipo de contrato de obra pública.

## Cláusula 2 – Objeto del contrato

El objeto del contrato es {objeto_general} que incluye {objeto_especifico}.

Los Documentos del Proceso forman parte del presente Contrato y definen igualmente las actividades, alcance y obligaciones del Contrato.

## Cláusula 3 – Actividades específicas del Contrato

Las actividades específicas del contrato se entienden conforme al documento tipo y a los documentos del proceso de contratación.

## Cláusula 4 – Valor del Contrato y Forma de pago

El valor del presente Contrato corresponde a la suma de {valor_total_numeros} ({valor_total_letras}).

La Entidad Estatal Contratante pagará al Contratista el valor del contrato en los siguientes periodos: {periodicidad_pago}.

Los pagos se realizarán dentro de los {dias_pago} siguientes a la fecha de presentación del certificado de cumplimiento firmado por el supervisor del Contrato.

## Cláusula 5 – Declaraciones del contratista

El Contratista hace las declaraciones previstas en el documento tipo de contrato de obra pública, las cuales se entienden incorporadas al presente contrato.

## Cláusula 6 – Plazo y Cronograma de Obra

El plazo de ejecución del Contrato es {plazo_ejecucion}.

El Cronograma Estimado de Obra del presente Contrato resulta del análisis conjunto del Contratista y de la Entidad Estatal contratante y forma parte del presente Contrato como anexo cuando aplique.

## Cláusula 7 – Derechos del Contratista

El Contratista tendrá los derechos previstos en el documento tipo de contrato de obra pública.

## Cláusula 8 – Obligaciones particulares del Contratista

El Contratista deberá cumplir las obligaciones previstas en el documento tipo de contrato de obra pública.

## Cláusula 9 – Derechos particulares de la Entidad Estatal contratante

La Entidad Estatal contratante tendrá los derechos previstos en el documento tipo de contrato de obra pública.

## Cláusula 10 – Obligaciones Generales de la Entidad Estatal contratante

La Entidad Estatal contratante tendrá las obligaciones previstas en el documento tipo de contrato de obra pública.

## Cláusula 11 – Responsabilidad

{nombre_contratista} es responsable por el cumplimiento del objeto establecido en la cláusula 2 del presente Contrato. {nombre_contratista} será responsable por los daños que ocasionen sus empleados y/o consultores, los empleados y/o consultores de sus subcontratistas, a {nombre_entidad} en la ejecución del objeto del presente Contrato.

## Cláusula 12 – Confidencialidad

En caso de que exista información sujeta a reserva legal, las partes deben mantener la confidencialidad de esta información, conforme al documento tipo.

## Cláusula 13 – Terminación, modificación e interpretación unilaterales del Contrato

{nombre_entidad} puede terminar, modificar y/o interpretar unilateralmente el Contrato, de acuerdo con la normatividad aplicable, cuando lo considere necesario para que el Contratista cumpla con el objeto del presente contrato.

## Cláusula 14 – Caducidad

{nombre_entidad} estará facultada para declarar la caducidad cuando exista un incumplimiento del contrato por parte del Contratista en la forma y de acuerdo con el procedimiento previsto por la ley.

## Cláusula 15 – Multas

Se aplicará el texto no editable del documento tipo de contrato de obra pública.

## Cláusula 16 – Cláusula Penal

En caso de declaratoria de caducidad o de incumplimiento total o parcial de las obligaciones del presente Contrato, {nombre_contratista} debe pagar a {nombre_entidad}, a título de indemnización, una suma equivalente a {clausula_penal_numeros} ({clausula_penal_letras}).

## Cláusula 17 – Garantías y Mecanismos de cobertura del riesgo

El Contratista se obliga a garantizar el cumplimiento de las obligaciones surgidas a favor de la Entidad Estatal contratante, con ocasión de la ejecución del contrato, de acuerdo con la siguiente tabla:

{garantias_txt}

El Contratista debe presentar dentro de los {plazo_garantias_dias} días hábiles siguientes a la firma del presente contrato las garantías a favor de {nombre_entidad}.

## Cláusula 18 – Independencia del Contratista

El Contratista es una entidad independiente de {nombre_entidad}, y en consecuencia, el Contratista no es su representante, agente o mandatario.

## Cláusula 19 – Cesión

El Contratista no puede ceder parcial ni totalmente sus obligaciones o derechos derivados del presente Contrato sin la autorización previa y por escrito de {nombre_entidad}.

## Cláusula 20 – Subcontratación

{nombre_contratista} puede subcontratar con cualquier tercero la ejecución de las actividades relacionadas con el objeto del presente contrato, conforme al documento tipo.

## Cláusula 21 – Indemnidad

El Contratista se obliga a indemnizar a {nombre_entidad} con ocasión de la violación o el incumplimiento de las obligaciones previstas en el presente Contrato.

## Cláusula 22 – Caso Fortuito y Fuerza Mayor

Las partes quedan exoneradas de responsabilidad por el incumplimiento de cualquiera de sus obligaciones o por la demora en la satisfacción de cualquiera de las prestaciones a su cargo derivadas del presente Contrato cuando el incumplimiento sea resultado o consecuencia de la ocurrencia de un evento de fuerza mayor y caso fortuito.

## Cláusula 23 – Solución de Controversias

Las controversias o diferencias que surjan entre el Contratista y la Entidad Estatal Contratante se resolverán conforme al texto no editable del documento tipo de contrato de obra pública.

## Cláusula 24 – Notificaciones

Los avisos, solicitudes, comunicaciones y notificaciones que las Partes deban hacer en desarrollo del presente Contrato deben constar por escrito y se entenderán debidamente efectuadas solo si son entregadas personalmente o por correo electrónico a las siguientes direcciones:

**{nombre_entidad}**
- Dirección: {not_entidad_direccion}
- Teléfono: {not_entidad_telefono}
- Correo electrónico: {not_entidad_correo}

**{nombre_contratista}**
- Dirección: {not_contratista_direccion}
- Teléfono: {not_contratista_telefono}
- Correo electrónico: {not_contratista_correo}

## Cláusula 25 – Supervisión

{bloque_supervision}

## Cláusula 26 – Interventoría

{bloque_interventoria}

## Cláusula 27 – Anexos del Contrato

{anexos_txt}

## Cláusula 28 – Perfeccionamiento y ejecución

El presente contrato requiere para su perfeccionamiento de la firma de las partes. Para su ejecución requiere el registro presupuestal y la acreditación de encontrarse el Contratista a paz y salvo por concepto de aportes al sistema de seguridad social integral.

## Cláusula 29 – Lugar de ejecución y domicilio contractual

Las actividades previstas en el presente Contrato se desarrollarán en {lugar_ejecucion}.

Para constancia, se firma en {lugar_celebracion} el {fecha_contrato}.

**{rep_entidad_nombre}**  
{rep_entidad_cargo}  
{rep_entidad_tipo_doc} No. {rep_entidad_num_doc}

**{rep_contratista_nombre}**  
Representante del contratista {tipo_contratista}  
{rep_contratista_tipo_doc} No. {rep_contratista_num_doc}
"""
    return contrato


datos = obtener_datos_contrato()

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
    st.markdown('<div class="titulo-seccion">📄 Contrato armado</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="subtitulo-gris">Vista de lectura del contrato construido automáticamente con la información diligenciada.</div>',
        unsafe_allow_html=True
    )
with col_l:
    if os.path.exists("unnamed.jpg"):
        st.image("unnamed.jpg", use_container_width=True)

st.divider()

with st.sidebar:
    st.header("🧭 Resumen")
    st.markdown(f"**Contrato:** {texto_si_vacio(datos.get('numero_contrato'))}")
    st.markdown(f"**Proyecto:** {texto_si_vacio(datos.get('nombre_proyecto'))}")
    st.markdown(f"**Entidad:** {texto_si_vacio(datos.get('nombre_entidad'))}")
    st.markdown(f"**Contratista:** {texto_si_vacio(datos.get('nombre_contratista'))}")
    st.markdown(f"**Valor:** {texto_si_vacio(datos.get('valor_total_numeros'))}")
    st.markdown(f"**Plazo:** {texto_si_vacio(datos.get('plazo_ejecucion'))}")

contrato_armado = construir_contrato(datos)

st.subheader("Vista del contrato")
st.markdown(contrato_armado)

st.divider()
st.text_area(
    "Contrato en texto continuo",
    value=contrato_armado,
    height=700,
    key="contrato_armado_texto_continuo"
)
