import pandas as pd
import streamlit as st
from pathlib import Path
from supabase_state import cargar_estado, guardar_estado

st.title("APU CONSULTORIA")

cronograma_datos = st.session_state.get("cronograma_datos", {}) or {}
tipo_presupuesto_proyecto = str(cronograma_datos.get("tipo_presupuesto_proyecto", "Obra") or "Obra").strip()

if tipo_presupuesto_proyecto != "Consultoría":
    st.warning("Este proyecto está clasificado como Obra. La hoja APU Consultoría aplica solo para proyectos de Consultoría.")
    st.stop()

alcance = st.session_state.get("alcance_datos", {}) or {}
nombre_proyecto = alcance.get("nombre_proyecto", "") or "SIN NOMBRE DEFINIDO"

st.markdown(f"## {nombre_proyecto}")


# -----------------------------
# Estado guardado
# -----------------------------
try:
    apus_consultoria_datos = cargar_estado("apus_consultoria") or {}
except Exception:
    apus_consultoria_datos = {}

try:
    presupuesto_consultoria_datos = st.session_state.get("pc_items_data") or {}
except Exception:
    presupuesto_consultoria_datos = {}

try:
    estudio_mercado_consultoria_datos = cargar_estado("estudio_mercado_consultoria") or {}
except Exception:
    estudio_mercado_consultoria_datos = {}

grupos_consultoria_origen = st.session_state.get("pc_grupos_origen", []) or []

if not grupos_consultoria_origen:
    try:
        presupuesto_consultoria_guardado = cargar_estado("presupuesto_consultoria") or {}
    except Exception:
        presupuesto_consultoria_guardado = {}

    grupos_consultoria_origen = presupuesto_consultoria_guardado.get("pc_grupos_origen", []) or []


def _id_origen(costo_indirecto_origen_id: str, tipo: str, subtipo: str, nombre: str) -> str:
    return (
        f"{str(costo_indirecto_origen_id).strip().upper()}|"
        f"{str(tipo).strip().upper()}|"
        f"{str(subtipo).strip().upper()}|"
        f"{str(nombre).strip().upper()}"
    )


def _extraer_items_desde_registros(datos: dict, ids_vigentes: set[str]) -> list[dict]:
    items = []
    registros_por_oci = datos.get("registros_por_oci", {}) or {}

    for oci_id, registro in registros_por_oci.items():
        oci_id_txt = str(oci_id or "").strip()
        if not oci_id_txt or oci_id_txt not in ids_vigentes:
            continue

        oci_nombre = str(registro.get("costo_indirecto_origen_nombre", "") or "").strip()

        personales = [
            ("PERSONAL", "1 Personal profesional y especializado", registro.get("personal_profesional", []), "PERFIL / ACTIVIDAD"),
            ("PERSONAL", "2 Personal técnico", registro.get("personal_tecnico", []), "PERFIL / ACTIVIDAD"),
            ("PERSONAL", "3 Otro personal", registro.get("otro_personal", []), "PERFIL / ACTIVIDAD"),
        ]

        for tipo, subtipo, filas, campo_nombre in personales:
            for fila in filas or []:
                fuente = str(fila.get("FUENTE", "") or "").strip()
                nombre = str(fila.get(campo_nombre, "") or "").strip()
                if fuente != "Cotización" or not nombre:
                    continue
                items.append(
                    {
                        "ID": _id_origen(oci_id_txt, tipo, subtipo, nombre),
                        "TIPO": tipo,
                        "SUBTIPO": subtipo,
                        "NOMBRE": nombre,
                        "UNIDAD": str(fila.get("UNIDAD", "") or "").strip(),
                        "COSTO_INDIRECTO_ORIGEN_ID": oci_id_txt,
                        "COSTO_INDIRECTO_ORIGEN_NOMBRE": oci_nombre,
                    }
                )

        bloques_bs = [
            ("BIENES", "4. BIENES", registro.get("bienes", []), "BIEN / ACTIVIDAD"),
            ("SERVICIOS", "5. SERVICIOS", registro.get("servicios", []), "BIEN / ACTIVIDAD"),
        ]

        for tipo, subtipo, filas, campo_nombre in bloques_bs:
            for fila in filas or []:
                fuente = str(fila.get("FUENTE", "") or "").strip()
                nombre = str(fila.get(campo_nombre, "") or "").strip()
                if fuente != "Cotización" or not nombre:
                    continue
                items.append(
                    {
                        "ID": _id_origen(oci_id_txt, tipo, subtipo, nombre),
                        "TIPO": tipo,
                        "SUBTIPO": subtipo,
                        "NOMBRE": nombre,
                        "UNIDAD": str(fila.get("UNIDAD", "") or "").strip(),
                        "COSTO_INDIRECTO_ORIGEN_ID": oci_id_txt,
                        "COSTO_INDIRECTO_ORIGEN_NOMBRE": oci_nombre,
                    }
                )

    items_unicos = []
    ids_vistos = set()

    for item in items:
        item_id = str(item.get("ID", "") or "").strip()
        if not item_id or item_id in ids_vistos:
            continue
        ids_vistos.add(item_id)
        items_unicos.append(item)

    return items_unicos


def _limpiar_estudio_mercado_contra_costos(costos_payload: dict, estudio_payload: dict, ids_vigentes: set[str]) -> tuple[dict, bool]:
    estudio_base = estudio_payload.copy() if isinstance(estudio_payload, dict) else {}

    items_validos = _extraer_items_desde_registros(costos_payload or {}, ids_vigentes)
    ids_items_validos = {str(item.get("ID", "") or "").strip() for item in items_validos if str(item.get("ID", "") or "").strip()}
    ids_oci_validos = {str(item.get("COSTO_INDIRECTO_ORIGEN_ID", "") or "").strip() for item in items_validos if str(item.get("COSTO_INDIRECTO_ORIGEN_ID", "") or "").strip()}

    items_guardados = estudio_base.get("items", []) or []
    items_limpios = []

    for item in items_guardados:
        item_id = str(item.get("ID", "") or "").strip()
        oci_id = str(item.get("COSTO_INDIRECTO_ORIGEN_ID", "") or "").strip()
        if item_id and item_id in ids_items_validos and (not oci_id or oci_id in ids_oci_validos):
            items_limpios.append(item)

    cot_guardadas = estudio_base.get("cotizaciones", []) or []
    cot_limpias = []

    for cot in cot_guardadas:
        item_id = str(cot.get("ITEM_ID", "") or "").strip()
        if item_id and item_id in ids_items_validos:
            cot_limpias.append(cot)

    nuevo_payload = {
        "items": items_limpios,
        "cotizaciones": cot_limpias,
    }

    cambio = (
        nuevo_payload.get("items", []) != estudio_base.get("items", [])
        or nuevo_payload.get("cotizaciones", []) != estudio_base.get("cotizaciones", [])
    )

    return nuevo_payload, cambio


opciones_oci = []
map_oci = {}

conteo_nombres_oci = {}
for item in grupos_consultoria_origen:
    nombre = str(item.get("titulo", "") or "").strip()
    if nombre:
        conteo_nombres_oci[nombre] = conteo_nombres_oci.get(nombre, 0) + 1

for item in grupos_consultoria_origen:
    item_id = str(item.get("group_id", "") or "").strip()
    nombre = str(item.get("titulo", "") or "").strip()
    if not item_id or not nombre:
        continue

    if conteo_nombres_oci.get(nombre, 0) > 1:
        etiqueta = f"{nombre} | {item_id}"
    else:
        etiqueta = nombre

    opciones_oci.append(etiqueta)
    map_oci[etiqueta] = {
        "id": item_id,
        "nombre": nombre,
        "valor": 0.0,
    }
costo_indirecto_origen = st.selectbox(
    "Seleccione el grupo origen del presupuesto de consultoría",
    options=opciones_oci,
    index=None,
    placeholder="Seleccione un grupo origen",
    key="ci_costo_indirecto_origen",
)

if not costo_indirecto_origen:
    st.info("Seleccione un grupo origen del presupuesto de consultoría para cargar la información.")
    st.stop()

costo_indirecto_origen_data = map_oci.get(costo_indirecto_origen, {})
costo_indirecto_origen_id = str(costo_indirecto_origen_data.get("id", "") or "").strip()
registros_por_oci_original = apus_consultoria_datos.get("registros_por_oci", {}) or {}

ids_oci_vigentes = {
    str(item.get("group_id", "") or "").strip()
    for item in grupos_consultoria_origen
    if str(item.get("group_id", "") or "").strip()
}

registros_por_oci = {
    str(oci_id): registro
    for oci_id, registro in registros_por_oci_original.items()
    if str(oci_id).strip() in ids_oci_vigentes
}

cambio_costos = registros_por_oci != registros_por_oci_original
apus_consultoria_datos["registros_por_oci"] = registros_por_oci
st.session_state["apus_consultoria_datos"] = apus_consultoria_datos

estudio_mercado_limpio, cambio_estudio = _limpiar_estudio_mercado_contra_costos(
    apus_consultoria_datos,
    estudio_mercado_consultoria_datos,
    ids_oci_vigentes,
)

if cambio_estudio:
    estudio_mercado_consultoria_datos = estudio_mercado_limpio
    for key_tmp in [
        "em_items_data",
        "em_cotizaciones_data",
        "em_pending_items_PERSONAL",
        "em_pending_items_BIENES",
        "em_pending_items_SERVICIOS",
        "em_pending_cot_PERSONAL",
        "em_pending_cot_BIENES",
        "em_pending_cot_SERVICIOS",
    ]:
        st.session_state.pop(key_tmp, None)

if cambio_costos or cambio_estudio:
    try:
        if cambio_costos:
            guardar_estado("apus_consultoria", apus_consultoria_datos)
        if cambio_estudio:
            guardar_estado("estudio_mercado_consultoria", estudio_mercado_consultoria_datos)
    except RuntimeError as e:
        if "No se pudo refrescar la sesión" in str(e):
            st.warning("La sesión expiró. Inicia sesión de nuevo para guardar cambios en APUS consultoría.")
        else:
            raise
registro_actual_oci = registros_por_oci.get(costo_indirecto_origen_id, {}) or {}

aplica_factor_default = "Sí" if bool(registro_actual_oci.get("aplica_factor_multiplicador", True)) else "No"

if st.session_state.get("ci_aplica_factor_oci_id") != costo_indirecto_origen_id:
    st.session_state["ci_aplica_factor_oci_id"] = costo_indirecto_origen_id
    st.session_state["ci_aplica_factor_multiplicador"] = aplica_factor_default

aplica_factor_multiplicador = st.selectbox(
    "¿Aplica factor multiplicador?",
    options=["Sí", "No"],
    index=0 if st.session_state.get("ci_aplica_factor_multiplicador", "Sí") == "Sí" else 1,
    key="ci_aplica_factor_multiplicador",
)

try:
    factor_multiplicador_datos = cargar_estado("factor_multiplicador") or {}
except Exception:
    factor_multiplicador_datos = {}

factor_multiplicador_hoja_11 = float(
    factor_multiplicador_datos.get("factor_multiplicador_final", 0.0) or 0.0
)

registro_actual_oci_hash = repr(registro_actual_oci)

if (
    st.session_state.get("ci_oci_cargado_id") != costo_indirecto_origen_id
    or st.session_state.get("ci_oci_cargado_hash") != registro_actual_oci_hash
):
    st.session_state["ci_oci_cargado_id"] = costo_indirecto_origen_id
    st.session_state["ci_oci_cargado_hash"] = registro_actual_oci_hash

    st.session_state["costos_indirectos_iva_pct"] = float(
        registro_actual_oci.get("iva_bienes_pct", registro_actual_oci.get("iva_servicios_pct", 19.0)) or 19.0
    )
    st.session_state["ci_resumen_final_data"] = registro_actual_oci.get("resumen_final", []) or []
    st.session_state["ci_personal_profesional_data"] = registro_actual_oci.get(
        "personal_profesional",
        [{
            "ITEM": "",
            "ITEM GOBERNACION": "",
            "DESCRIPION GOBERNACION": "",
            "DESCRIPCION GOBERNACION": "",
            "PERFIL / ACTIVIDAD": "",
            "FUENTE": "Cotización",
            "UNIDAD": "",
            "CANT": 0.0,
            "REND": 0.0,
            "VR UNITARIO": 0.0,
            "VR TOTAL": 0.0,
        }],
    )
    st.session_state["ci_personal_tecnico_data"] = registro_actual_oci.get(
        "personal_tecnico",
        [{
            "ITEM": "",
            "ITEM GOBERNACION": "",
            "DESCRIPION GOBERNACION": "",
            "DESCRIPCION GOBERNACION": "",
            "PERFIL / ACTIVIDAD": "",
            "FUENTE": "Cotización",
            "UNIDAD": "",
            "CANT": 0.0,
            "REND": 0.0,
            "VR UNITARIO": 0.0,
            "VR TOTAL": 0.0,
        }],
    )
    st.session_state["ci_otro_personal_data"] = registro_actual_oci.get(
        "otro_personal",
        [{
            "ITEM": "",
            "ITEM GOBERNACION": "",
            "DESCRIPION GOBERNACION": "",
            "DESCRIPCION GOBERNACION": "",
            "PERFIL / ACTIVIDAD": "",
            "FUENTE": "Cotización",
            "UNIDAD": "",
            "CANT": 0.0,
            "REND": 0.0,
            "VR UNITARIO": 0.0,
            "VR TOTAL": 0.0,
        }],
    )
    st.session_state["ci_bienes_data"] = registro_actual_oci.get(
        "bienes",
        [{
            "ITEM": "",
            "BIEN / ACTIVIDAD": "",
            "FUENTE": "Cotización",
            "UNIDAD": "",
            "CANT": 0.0,
            "VR UNITARIO SIN IVA": 0.0,
            "VR TOTAL": 0.0,
        }],
    )
    st.session_state["ci_servicios_data"] = registro_actual_oci.get(
        "servicios",
        [{
            "ITEM": "",
            "BIEN / ACTIVIDAD": "",
            "FUENTE": "Cotización",
            "UNIDAD": "",
            "CANT": 0.0,
            "VR UNITARIO SIN IVA": 0.0,
            "VR TOTAL": 0.0,
        }],
    )
if aplica_factor_multiplicador == "Sí":
    if factor_multiplicador_hoja_11 > 0:
        st.session_state["costos_indirectos_factor_multiplicador"] = factor_multiplicador_hoja_11
    else:
        st.session_state["costos_indirectos_factor_multiplicador"] = float(
            registro_actual_oci.get("factor_multiplicador_personal", 1.0) or 1.0
        )
else:
    st.session_state["costos_indirectos_factor_multiplicador"] = 1.0

df_em_items = pd.DataFrame(estudio_mercado_consultoria_datos.get("items", [])).copy()
df_em_cot = pd.DataFrame(estudio_mercado_consultoria_datos.get("cotizaciones", [])).copy()

if df_em_items.empty:
    df_em_items = pd.DataFrame(columns=["ID", "TIPO", "SUBTIPO", "NOMBRE", "UNIDAD", "COSTO_INDIRECTO_ORIGEN_ID"])
if df_em_cot.empty:
    df_em_cot = pd.DataFrame(columns=["ITEM_ID", "VALOR_SIN_IVA"])

for col in ["ID", "TIPO", "SUBTIPO", "NOMBRE", "UNIDAD", "COSTO_INDIRECTO_ORIGEN_ID"]:
    if col not in df_em_items.columns:
        df_em_items[col] = ""
    df_em_items[col] = df_em_items[col].fillna("").astype(str)

if "ITEM_ID" not in df_em_cot.columns:
    df_em_cot["ITEM_ID"] = ""
if "VALOR_SIN_IVA" not in df_em_cot.columns:
    df_em_cot["VALOR_SIN_IVA"] = 0.0

df_em_items = df_em_items[
    df_em_items["COSTO_INDIRECTO_ORIGEN_ID"].astype(str).str.strip().eq(costo_indirecto_origen_id)
].copy()

ids_items_oci_actual = set(df_em_items["ID"].astype(str).str.strip().tolist())

df_em_cot["ITEM_ID"] = df_em_cot["ITEM_ID"].fillna("").astype(str)
df_em_cot["VALOR_SIN_IVA"] = pd.to_numeric(df_em_cot["VALOR_SIN_IVA"], errors="coerce")
df_em_cot = df_em_cot[df_em_cot["ITEM_ID"].str.strip() != ""].copy()
df_em_cot = df_em_cot[df_em_cot["VALOR_SIN_IVA"].notna()].copy()
df_em_cot = df_em_cot[df_em_cot["VALOR_SIN_IVA"] > 0].copy()
df_em_cot = df_em_cot[df_em_cot["ITEM_ID"].isin(ids_items_oci_actual)].copy()

if df_em_cot.empty:
    df_em_prom = pd.DataFrame(columns=["ITEM_ID", "PROMEDIO"])
else:
    df_em_prom = (
        df_em_cot.groupby("ITEM_ID", dropna=False)["VALOR_SIN_IVA"]
        .mean()
        .reset_index()
        .rename(columns={"VALOR_SIN_IVA": "PROMEDIO"})
    )

df_em_ref = df_em_items.merge(df_em_prom, how="left", left_on="ID", right_on="ITEM_ID")
df_em_ref["PROMEDIO"] = pd.to_numeric(df_em_ref.get("PROMEDIO", 0.0), errors="coerce").fillna(0.0)

map_em_personal = {
    (str(row["SUBTIPO"]).strip(), str(row["NOMBRE"]).strip()): {
        "unidad": str(row["UNIDAD"]).strip(),
        "vr_unitario": float(row["PROMEDIO"]),
    }
    for _, row in df_em_ref.iterrows()
    if str(row["TIPO"]).strip().upper() == "PERSONAL" and str(row["NOMBRE"]).strip()
}

map_em_bs = {
    (str(row["TIPO"]).strip().upper(), str(row["SUBTIPO"]).strip(), str(row["NOMBRE"]).strip()): {
        "unidad": str(row["UNIDAD"]).strip(),
        "vr_unitario": float(row["PROMEDIO"]),
    }
    for _, row in df_em_ref.iterrows()
    if str(row["TIPO"]).strip().upper() in ["BIENES", "SERVICIOS"] and str(row["NOMBRE"]).strip()
}

# -----------------------------
# Catálogo salarios gobernación
# -----------------------------
ruta_salarios = Path("data") / "sueldos.xlsx"

try:
    df_salarios_raw = pd.read_excel(ruta_salarios)
except Exception:
    df_salarios_raw = pd.DataFrame(columns=["ITEM", "DESCIPCION", "UNIDAD", "VALOR"])

df_salarios_raw.columns = [str(c).strip() for c in df_salarios_raw.columns]

renombres = {}
for c in df_salarios_raw.columns:
    cu = str(c).strip().upper()
    if cu == "ITEM":
        renombres[c] = "ITEM"
    elif cu == "DESCIPCION":
        renombres[c] = "DESCIPCION"
    elif cu == "UNIDAD":
        renombres[c] = "UNIDAD"
    elif cu == "VALOR":
        renombres[c] = "VALOR"

if renombres:
    df_salarios_raw = df_salarios_raw.rename(columns=renombres)

for col in ["ITEM", "DESCIPCION", "UNIDAD", "VALOR"]:
    if col not in df_salarios_raw.columns:
        df_salarios_raw[col] = ""

df_salarios = df_salarios_raw[["ITEM", "DESCIPCION", "UNIDAD", "VALOR"]].copy()
df_salarios["ITEM"] = df_salarios["ITEM"].fillna("").astype(str).str.strip()
df_salarios["DESCIPCION"] = df_salarios["DESCIPCION"].fillna("").astype(str).str.strip()
df_salarios["UNIDAD"] = df_salarios["UNIDAD"].fillna("").astype(str).str.strip()
df_salarios["VALOR"] = pd.to_numeric(df_salarios["VALOR"], errors="coerce").fillna(0.0)

map_item_gober = {
    row["ITEM"]: {
        "descripcion_gober": row["DESCIPCION"],
        "unidad": row["UNIDAD"],
        "vr_unitario": float(row["VALOR"]),
    }
    for _, row in df_salarios.iterrows()
    if row["ITEM"]
}

map_desc_gober = {
    row["DESCIPCION"]: {
        "item_gober": row["ITEM"],
        "unidad": row["UNIDAD"],
        "vr_unitario": float(row["VALOR"]),
    }
    for _, row in df_salarios.iterrows()
    if row["DESCIPCION"]
}

opciones_item_gober = sorted([x for x in df_salarios["ITEM"].tolist() if x])
opciones_desc_gober = sorted([x for x in df_salarios["DESCIPCION"].tolist() if x])
opciones_item_gober_detalle = [""] + [f"{k} | {v['descripcion_gober']}" for k, v in map_item_gober.items()]

# -----------------------------
# Utilidades de guardado
# -----------------------------
if "costos_indirectos_factor_multiplicador" not in st.session_state:
    st.session_state["costos_indirectos_factor_multiplicador"] = 1.0

if "costos_indirectos_iva_pct" not in st.session_state:
    st.session_state["costos_indirectos_iva_pct"] = float(
        registro_actual_oci.get("iva_bienes_pct", registro_actual_oci.get("iva_servicios_pct", 19.0)) or 19.0
    )

if "ci_resumen_final_data" not in st.session_state:
    st.session_state["ci_resumen_final_data"] = registro_actual_oci.get("resumen_final", []) or []


def _guardar_costos_indirectos():
    try:
        payload_actual = apus_consultoria_datos.copy() if isinstance(apus_consultoria_datos, dict) else {}
        registros_actuales = payload_actual.get("registros_por_oci", {}) or {}

        oci_id = str(costo_indirecto_origen_id or "").strip()
        oci_nombre = str(costo_indirecto_origen_data.get("nombre", "") or "").strip()

        def _amarrar_filas_a_oci(filas, tipo, subtipo, campo_nombre):
            filas_resultado = []
            for fila in (filas or []):
                fila_nueva = dict(fila)
                nombre = str(fila_nueva.get(campo_nombre, "") or "").strip()
                fila_nueva["ID"] = _id_origen(oci_id, tipo, subtipo, nombre) if nombre else ""
                fila_nueva["costo_indirecto_origen_id"] = oci_id
                fila_nueva["costo_indirecto_origen_nombre"] = oci_nombre
                filas_resultado.append(fila_nueva)
            return filas_resultado

        personal_profesional_data = _amarrar_filas_a_oci(
            st.session_state.get("ci_personal_profesional_data", []),
            "PERSONAL",
            "1 Personal profesional y especializado",
            "PERFIL / ACTIVIDAD",
        )
        personal_tecnico_data = _amarrar_filas_a_oci(
            st.session_state.get("ci_personal_tecnico_data", []),
            "PERSONAL",
            "2 Personal técnico",
            "PERFIL / ACTIVIDAD",
        )
        otro_personal_data = _amarrar_filas_a_oci(
            st.session_state.get("ci_otro_personal_data", []),
            "PERSONAL",
            "3 Otro personal",
            "PERFIL / ACTIVIDAD",
        )
        bienes_data = _amarrar_filas_a_oci(
            st.session_state.get("ci_bienes_data", []),
            "BIENES",
            "4. BIENES",
            "BIEN / ACTIVIDAD",
        )
        servicios_data = _amarrar_filas_a_oci(
            st.session_state.get("ci_servicios_data", []),
            "SERVICIOS",
            "5. SERVICIOS",
            "BIEN / ACTIVIDAD",
        )

        subtotal_personal = sum(
            float(pd.to_numeric(fila.get("VR TOTAL", 0.0), errors="coerce") or 0.0)
            for fila in (personal_profesional_data or [])
        ) + sum(
            float(pd.to_numeric(fila.get("VR TOTAL", 0.0), errors="coerce") or 0.0)
            for fila in (personal_tecnico_data or [])
        ) + sum(
            float(pd.to_numeric(fila.get("VR TOTAL", 0.0), errors="coerce") or 0.0)
            for fila in (otro_personal_data or [])
        )

        factor_multiplicador_personal = float(
            st.session_state.get("costos_indirectos_factor_multiplicador", 1.0) or 1.0
        )
        total_personal = subtotal_personal * factor_multiplicador_personal

        subtotal_bienes = sum(
            float(pd.to_numeric(fila.get("VR TOTAL", 0.0), errors="coerce") or 0.0)
            for fila in (bienes_data or [])
        )
        subtotal_servicios = sum(
            float(pd.to_numeric(fila.get("VR TOTAL", 0.0), errors="coerce") or 0.0)
            for fila in (servicios_data or [])
        )

        iva_pct_guardado = float(st.session_state.get("costos_indirectos_iva_pct", 19.0) or 19.0)

        resumen_guardado = st.session_state.get("ci_resumen_final_data", []) or []
        resumen_guardado_map = {
            str(row.get("Concepto", "") or "").strip(): str(row.get("IVA", "Sí") or "Sí").strip()
            for row in resumen_guardado
            if str(row.get("Concepto", "") or "").strip()
        }

        resumen_base_df = pd.DataFrame(
            [
                {"Concepto": "Costo personal", "Valor": total_personal, "IVA": resumen_guardado_map.get("Costo personal", "Sí")},
                {"Concepto": "Bienes", "Valor": subtotal_bienes, "IVA": resumen_guardado_map.get("Bienes", "Sí")},
                {"Concepto": "Servicios", "Valor": subtotal_servicios, "IVA": resumen_guardado_map.get("Servicios", "Sí")},
            ]
        )

        resumen_base_df["VALOR TOTAL"] = resumen_base_df.apply(
            lambda r: float(pd.to_numeric(r["Valor"], errors="coerce") or 0.0) * (1 + iva_pct_guardado / 100.0)
            if str(r["IVA"] or "").strip() == "Sí"
            else float(pd.to_numeric(r["Valor"], errors="coerce") or 0.0),
            axis=1,
        )

        st.session_state["ci_resumen_final_data"] = resumen_base_df.to_dict(orient="records")

        costo_directo_total = float(pd.to_numeric(resumen_base_df["Valor"], errors="coerce").fillna(0.0).sum())
        iva_total = float(pd.to_numeric(resumen_base_df["VALOR TOTAL"], errors="coerce").fillna(0.0).sum()) - costo_directo_total
        valor_total_final = float(pd.to_numeric(resumen_base_df["VALOR TOTAL"], errors="coerce").fillna(0.0).sum())

        if oci_id:
            registros_actuales[oci_id] = {
                "costo_indirecto_origen_id": oci_id,
                "costo_indirecto_origen_nombre": oci_nombre,
                "aplica_factor_multiplicador": True if st.session_state.get("ci_aplica_factor_multiplicador", "Sí") == "Sí" else False,
                "personal_profesional": personal_profesional_data,
                "personal_tecnico": personal_tecnico_data,
                "otro_personal": otro_personal_data,
                "factor_multiplicador_personal": factor_multiplicador_personal,
                "bienes": bienes_data,
                "iva_bienes_pct": iva_pct_guardado,
                "servicios": servicios_data,
                "iva_servicios_pct": iva_pct_guardado,
                "resumen_final": resumen_base_df.to_dict(orient="records"),
                "costo_directo_total": float(costo_directo_total or 0.0),
                "valor_total_final": float(valor_total_final or 0.0),
            }

        payload_actual["registros_por_oci"] = {
            str(oci_id_k): registro
            for oci_id_k, registro in registros_actuales.items()
            if str(oci_id_k).strip() in ids_oci_vigentes
        }

        guardar_estado("apus_consultoria", payload_actual)
        st.session_state["apus_consultoria_datos"] = payload_actual
        return True
    except RuntimeError as e:
        if "No se pudo refrescar la sesión" in str(e):
            st.warning("Sesión expirada. Inicia sesión de nuevo para guardar cambios en APUS consultoría.")
            return False
        raise


if st.button("Guardar APUS consultoría", width="stretch"):
    ok_guardado = _guardar_costos_indirectos()
    if ok_guardado:
        st.success("Costos indirectos guardados correctamente.")

# -----------------------------
# PERSONAL
# -----------------------------
PERSONAL_COLUMNS = [
    "ITEM GOBERNACION",
    "ITEM",
    "ITEM GOBER",
    "DESCRIPCION GOBERNACION",
    "PERFIL / ACTIVIDAD",
    "FUENTE",
    "UNIDAD",
    "CANT",
    "REND",
    "VR UNITARIO",
    "VR TOTAL",
]

PERSONAL_TEXT_COLS = [
    "ITEM GOBERNACION",
    "ITEM GOBER",
    "DESCRIPCION GOBERNACION",
    "PERFIL / ACTIVIDAD",
    "FUENTE",
    "UNIDAD",
]

PERSONAL_NUM_COLS = ["CANT", "REND", "VR UNITARIO"]


def _fila_vacia_personal():
    return {
        "ITEM GOBERNACION": "",
        "ITEM": "",
        "ITEM GOBER": "",
        "DESCRIPCION GOBERNACION": "",
        "PERFIL / ACTIVIDAD": "",
        "FUENTE": "Cotización",
        "UNIDAD": "",
        "CANT": 0.0,
        "REND": 0.0,
        "VR UNITARIO": 0.0,
        "VR TOTAL": 0.0,
    }

def _normalizar_df_personal(df: pd.DataFrame, prefijo_item: str) -> pd.DataFrame:
    df = df.copy()

    for col in PERSONAL_COLUMNS:
        if col not in df.columns:
            df[col] = "" if col in PERSONAL_TEXT_COLS else 0.0

    df = df[PERSONAL_COLUMNS].copy()

    for col in PERSONAL_TEXT_COLS:
        df[col] = df[col].fillna("").astype(str)

    for col in PERSONAL_NUM_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df["FUENTE"] = df["FUENTE"].replace("", "Cotización")
    df["FUENTE"] = df["FUENTE"].replace("Otra", "Cotización")
    df["FUENTE"] = df["FUENTE"].replace("Salarios gobernación", "Precios gobernación")
    df["ITEM"] = [f"{prefijo_item}.{i:02d}" for i in range(1, len(df) + 1)]

    for idx in df.index:
        fuente = str(df.at[idx, "FUENTE"]).strip()
        item_gobernacion = str(df.at[idx, "ITEM GOBERNACION"]).strip()
        item_gober = str(df.at[idx, "ITEM GOBER"]).strip()
        desc_gober = str(df.at[idx, "DESCRIPCION GOBERNACION"]).strip()

        if fuente == "Precios gobernación":
            if item_gobernacion and " | " in item_gobernacion:
                codigo_sel = item_gobernacion.split(" | ", 1)[0].strip()
                if codigo_sel in map_item_gober:
                    ref = map_item_gober[codigo_sel]
                    df.at[idx, "ITEM GOBER"] = codigo_sel
                    df.at[idx, "ITEM GOBERNACION"] = ""
                    df.at[idx, "DESCRIPCION GOBERNACION"] = ref["descripcion_gober"]
                    df.at[idx, "UNIDAD"] = ref["unidad"]
                    df.at[idx, "VR UNITARIO"] = ref["vr_unitario"]
            elif item_gober and item_gober in map_item_gober:
                ref = map_item_gober[item_gober]
                df.at[idx, "ITEM GOBERNACION"] = ""
                df.at[idx, "DESCRIPCION GOBERNACION"] = ref["descripcion_gober"]
                df.at[idx, "UNIDAD"] = ref["unidad"]
                df.at[idx, "VR UNITARIO"] = ref["vr_unitario"]
            elif desc_gober and desc_gober in map_desc_gober:
                ref = map_desc_gober[desc_gober]
                df.at[idx, "ITEM GOBER"] = ref["item_gober"]
                df.at[idx, "ITEM GOBERNACION"] = ""
                df.at[idx, "UNIDAD"] = ref["unidad"]
                df.at[idx, "VR UNITARIO"] = ref["vr_unitario"]

        elif fuente == "Cotización":
            perfil = str(df.at[idx, "PERFIL / ACTIVIDAD"]).strip()

            subtipo_em = ""
            pref = str(prefijo_item).strip()

            if pref.startswith("1"):
                subtipo_em = "1 Personal profesional y especializado"
            elif pref.startswith("2"):
                subtipo_em = "2 Personal técnico"
            elif pref.startswith("3"):
                subtipo_em = "3 Otro personal"

            ref_em = map_em_personal.get((subtipo_em, perfil))

            if ref_em:
                df.at[idx, "ITEM GOBER"] = ""
                df.at[idx, "ITEM GOBERNACION"] = ""
                df.at[idx, "DESCRIPCION GOBERNACION"] = ""
                df.at[idx, "UNIDAD"] = ref_em["unidad"]
                df.at[idx, "VR UNITARIO"] = ref_em["vr_unitario"]

        else:
            df.at[idx, "ITEM GOBER"] = ""
            df.at[idx, "ITEM GOBERNACION"] = ""
            df.at[idx, "DESCRIPCION GOBERNACION"] = ""

    df["VR TOTAL"] = df["CANT"] * df["REND"] * df["VR UNITARIO"]
    return df


def _render_tabla_personal(titulo: str, key_data: str, key_widget: str, prefijo_item: str):
    if key_data not in st.session_state:
        mapa_guardado = {
            "ci_personal_profesional_data": "personal_profesional",
            "ci_personal_tecnico_data": "personal_tecnico",
            "ci_otro_personal_data": "otro_personal",
        }
        st.session_state[key_data] = registro_actual_oci.get(
            mapa_guardado.get(key_data, ""), [_fila_vacia_personal()]
        )

    def _on_change_local():
        widget_state = st.session_state.get(key_widget, {}) or {}
        edited_rows = widget_state.get("edited_rows", {}) or {}
        added_rows = widget_state.get("added_rows", []) or []
        deleted_rows = widget_state.get("deleted_rows", []) or []

        data_actual = st.session_state.get(key_data, [])
        df_actual = pd.DataFrame(data_actual).copy()
        df_actual = (
            _normalizar_df_personal(df_actual, prefijo_item)
            if not df_actual.empty
            else pd.DataFrame(columns=PERSONAL_COLUMNS)
        )

        for row_idx, cambios in edited_rows.items():
            if row_idx >= len(df_actual):
                continue
            for col_name, valor in cambios.items():
                if col_name in df_actual.columns:
                    df_actual.at[row_idx, col_name] = valor

        if deleted_rows:
            df_actual = df_actual.drop(index=deleted_rows, errors="ignore").reset_index(drop=True)

        for nueva_fila in added_rows:
            fila_limpia = {
                "ITEM": "",
                "ITEM GOBERNACION": nueva_fila.get("ITEM GOBERNACION", "") if isinstance(nueva_fila, dict) else "",
                "DESCRIPCION GOBERNACION": nueva_fila.get("DESCRIPCION GOBERNACION", "") if isinstance(nueva_fila, dict) else "",
                "PERFIL / ACTIVIDAD": nueva_fila.get("PERFIL / ACTIVIDAD", "") if isinstance(nueva_fila, dict) else "",
                "FUENTE": nueva_fila.get("FUENTE", "Cotización") if isinstance(nueva_fila, dict) else "Cotización",
                "UNIDAD": nueva_fila.get("UNIDAD", "") if isinstance(nueva_fila, dict) else "",
                "CANT": nueva_fila.get("CANT", 0.0) if isinstance(nueva_fila, dict) else 0.0,
                "REND": nueva_fila.get("REND", 0.0) if isinstance(nueva_fila, dict) else 0.0,
                "VR UNITARIO": nueva_fila.get("VR UNITARIO", 0.0) if isinstance(nueva_fila, dict) else 0.0,
                "VR TOTAL": 0.0,
            }
            df_actual = pd.concat([df_actual, pd.DataFrame([fila_limpia])], ignore_index=True)

        if df_actual.empty:
            df_actual = pd.DataFrame([_fila_vacia_personal()])

        df_actual = _normalizar_df_personal(df_actual, prefijo_item)
        st.session_state[key_data] = df_actual.to_dict(orient="records")

    df_base = pd.DataFrame(st.session_state.get(key_data, [])).copy()
    if df_base.empty:
        df_base = pd.DataFrame([_fila_vacia_personal()])

    df_base = _normalizar_df_personal(df_base, prefijo_item)

    st.markdown(f"### {titulo}")

    st.data_editor(
        df_base,
        hide_index=True,
        width="stretch",
        num_rows="dynamic",
        key=key_widget,
        on_change=_on_change_local,
        column_order=[
            "ITEM GOBERNACION",
            "ITEM",
            "ITEM GOBER",
            "PERFIL / ACTIVIDAD",
            "FUENTE",
            "UNIDAD",
            "CANT",
            "REND",
            "VR UNITARIO",
            "VR TOTAL",
        ],
        column_config={
            "ITEM GOBERNACION": st.column_config.SelectboxColumn(
                "ITEM GOBERNACION",
                options=opciones_item_gober_detalle,
            ),
            "ITEM": st.column_config.TextColumn("ITEM", disabled=True),
            "ITEM GOBER": st.column_config.TextColumn("ITEM GOBER", disabled=True),
            "PERFIL / ACTIVIDAD": st.column_config.TextColumn("PERFIL / ACTIVIDAD"),
            "FUENTE": st.column_config.SelectboxColumn(
                "FUENTE",
                options=["Cotización", "Precios gobernación"],
            ),
            "UNIDAD": st.column_config.TextColumn("UNIDAD", disabled=True),
            "CANT": st.column_config.NumberColumn("CANT", min_value=0.0, step=0.01, format="%.2f"),
            "REND": st.column_config.NumberColumn("REND", min_value=0.0, step=0.01, format="%.2f"),
            "VR UNITARIO": st.column_config.NumberColumn("VR UNITARIO", min_value=0.0, step=0.01, format="$ %.2f", disabled=True),
            "VR TOTAL": st.column_config.NumberColumn("VR TOTAL", disabled=True, format="$ %.2f"),
        },
        disabled=["ITEM", "ITEM GOBER", "UNIDAD", "VR UNITARIO", "VR TOTAL"],
    )

    df_final = _normalizar_df_personal(pd.DataFrame(st.session_state.get(key_data, [])), prefijo_item)
    total = float(pd.to_numeric(df_final["VR TOTAL"], errors="coerce").fillna(0.0).sum())

    c1, c2 = st.columns([5, 1])
    with c1:
        st.markdown(f"**TOTAL {titulo.upper()}**")
    with c2:
        st.markdown(f"**$ {total:,.2f}**")

    return total


st.markdown("## 1. PERSONAL")

total_personal_profesional = _render_tabla_personal(
    "1 Personal profesional y especializado",
    "ci_personal_profesional_data",
    "ci_personal_profesional_widget",
    "1.1",
)

st.divider()

total_personal_tecnico = _render_tabla_personal(
    "2 Personal técnico",
    "ci_personal_tecnico_data",
    "ci_personal_tecnico_widget",
    "1.2",
)

st.divider()

total_otro_personal = _render_tabla_personal(
    "3 Otro personal",
    "ci_otro_personal_data",
    "ci_otro_personal_widget",
    "1.3",
)

subtotal_personal = total_personal_profesional + total_personal_tecnico + total_otro_personal

st.divider()
st.markdown("### SUBTOTAL PERSONAL")

csub1, csub2 = st.columns([5, 1])
with csub1:
    st.markdown("**SUBTOTAL PERSONAL**")
with csub2:
    st.markdown(f"**$ {subtotal_personal:,.2f}**")

st.markdown("### FACTOR MULTIPLICADOR")

factor_multiplicador = float(
    st.session_state.get("costos_indirectos_factor_multiplicador", 1.0) or 1.0
)

cf1, cf2 = st.columns([5, 1])
with cf1:
    st.markdown("**Factor multiplicador**")
with cf2:
    st.markdown(f"**{factor_multiplicador:,.2f}**")

total_personal = subtotal_personal * factor_multiplicador

ct1, ct2 = st.columns([5, 1])
with ct1:
    st.markdown("## TOTAL PERSONAL")
with ct2:
    st.markdown(f"## $ {total_personal:,.2f}")

# -----------------------------
# BIENES / SERVICIOS
# -----------------------------
BS_COLUMNS = [
    "ITEM",
    "BIEN / ACTIVIDAD",
    "FUENTE",
    "UNIDAD",
    "CANT",
    "VR UNITARIO SIN IVA",
    "VR TOTAL",
]

BS_TEXT_COLS = ["BIEN / ACTIVIDAD", "FUENTE", "UNIDAD"]
BS_NUM_COLS = ["CANT", "VR UNITARIO SIN IVA"]


def _fila_vacia_bs():
    return {
        "ITEM": "",
        "BIEN / ACTIVIDAD": "",
        "FUENTE": "Cotización",
        "UNIDAD": "",
        "CANT": 0.0,
        "VR UNITARIO SIN IVA": 0.0,
        "VR TOTAL": 0.0,
    }


def _normalizar_df_bs(df: pd.DataFrame, prefijo_item: str) -> pd.DataFrame:
    df = df.copy()

    for col in BS_COLUMNS:
        if col not in df.columns:
            df[col] = "" if col in BS_TEXT_COLS else 0.0

    df = df[BS_COLUMNS].copy()

    for col in BS_TEXT_COLS:
        df[col] = df[col].fillna("").astype(str)

    for col in BS_NUM_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df["FUENTE"] = df["FUENTE"].replace("", "Cotización")
    df["ITEM"] = [f"{prefijo_item}.{i:02d}" for i in range(1, len(df) + 1)]

    for idx in df.index:
        fuente = str(df.at[idx, "FUENTE"]).strip()
        nombre = str(df.at[idx, "BIEN / ACTIVIDAD"]).strip()

        if fuente == "Cotización":
            subtipo_em = ""
            pref = str(prefijo_item).strip()

            if pref.startswith("4"):
                subtipo_em = "4. BIENES"
                tipo_em = "BIENES"
            elif pref.startswith("5"):
                subtipo_em = "5. SERVICIOS"
                tipo_em = "SERVICIOS"
            else:
                subtipo_em = ""
                tipo_em = ""

            ref_em = map_em_bs.get((tipo_em, subtipo_em, nombre))

            if ref_em:
                df.at[idx, "UNIDAD"] = ref_em["unidad"]
                df.at[idx, "VR UNITARIO SIN IVA"] = ref_em["vr_unitario"]

    df["VR TOTAL"] = df["CANT"] * df["VR UNITARIO SIN IVA"]
    return df


def _render_tabla_bs(titulo: str, key_data: str, key_widget: str, prefijo_item: str, key_guardado: str):
    if key_data not in st.session_state:
        st.session_state[key_data] = registro_actual_oci.get(key_guardado, [_fila_vacia_bs()])

    def _on_change_local():
        widget_state = st.session_state.get(key_widget, {}) or {}
        edited_rows = widget_state.get("edited_rows", {}) or {}
        added_rows = widget_state.get("added_rows", []) or []
        deleted_rows = widget_state.get("deleted_rows", []) or []

        data_actual = st.session_state.get(key_data, [])
        df_actual = pd.DataFrame(data_actual).copy()
        df_actual = _normalizar_df_bs(df_actual, prefijo_item) if not df_actual.empty else pd.DataFrame(columns=BS_COLUMNS)

        for row_idx, cambios in edited_rows.items():
            if row_idx >= len(df_actual):
                continue
            for col_name, valor in cambios.items():
                if col_name in df_actual.columns:
                    df_actual.at[row_idx, col_name] = valor

        if deleted_rows:
            df_actual = df_actual.drop(index=deleted_rows, errors="ignore").reset_index(drop=True)

        for nueva_fila in added_rows:
            fila_limpia = {
                "ITEM": "",
                "BIEN / ACTIVIDAD": nueva_fila.get("BIEN / ACTIVIDAD", "") if isinstance(nueva_fila, dict) else "",
                "FUENTE": nueva_fila.get("FUENTE", "Cotización") if isinstance(nueva_fila, dict) else "Cotización",
                "UNIDAD": nueva_fila.get("UNIDAD", "") if isinstance(nueva_fila, dict) else "",
                "CANT": nueva_fila.get("CANT", 0.0) if isinstance(nueva_fila, dict) else 0.0,
                "VR UNITARIO SIN IVA": nueva_fila.get("VR UNITARIO SIN IVA", 0.0) if isinstance(nueva_fila, dict) else 0.0,
                "VR TOTAL": 0.0,
            }
            df_actual = pd.concat([df_actual, pd.DataFrame([fila_limpia])], ignore_index=True)

        if df_actual.empty:
            df_actual = pd.DataFrame([_fila_vacia_bs()])

        df_actual = _normalizar_df_bs(df_actual, prefijo_item)
        st.session_state[key_data] = df_actual.to_dict(orient="records")

    df_base = pd.DataFrame(st.session_state.get(key_data, [])).copy()
    if df_base.empty:
        df_base = pd.DataFrame([_fila_vacia_bs()])

    df_base = _normalizar_df_bs(df_base, prefijo_item)

    st.markdown(f"## {titulo}")

    st.data_editor(
        df_base,
        hide_index=True,
        width="stretch",
        num_rows="dynamic",
        key=key_widget,
        on_change=_on_change_local,
        column_config={
            "ITEM": st.column_config.TextColumn("ITEM", disabled=True),
            "BIEN / ACTIVIDAD": st.column_config.TextColumn("BIEN / ACTIVIDAD"),
            "FUENTE": st.column_config.SelectboxColumn(
                "FUENTE",
                options=["Cotización", "Otra"],
            ),
            "UNIDAD": st.column_config.TextColumn("UNIDAD", disabled=True),
            "CANT": st.column_config.NumberColumn("CANT", min_value=0.0, step=0.01, format="%.2f"),
            "VR UNITARIO SIN IVA": st.column_config.NumberColumn(
                "VR UNITARIO SIN IVA", min_value=0.0, step=0.01, format="$ %.2f", disabled=True
            ),
            "VR TOTAL": st.column_config.NumberColumn("VR TOTAL", disabled=True, format="$ %.2f"),
        },
        disabled=["ITEM", "UNIDAD", "VR UNITARIO SIN IVA", "VR TOTAL"],
    )

    df_final = _normalizar_df_bs(pd.DataFrame(st.session_state.get(key_data, [])), prefijo_item)
    subtotal = float(pd.to_numeric(df_final["VR TOTAL"], errors="coerce").fillna(0.0).sum())

    c1, c2 = st.columns([5, 1])
    with c1:
        st.markdown(f"**SUBTOTAL {titulo.upper()}**")
    with c2:
        st.markdown(f"**$ {subtotal:,.2f}**")

    return subtotal


st.divider()
subtotal_bienes = _render_tabla_bs(
    "4. BIENES",
    "ci_bienes_data",
    "ci_bienes_widget",
    "4",
    "bienes",
)

cb3, cb4 = st.columns([5, 1])
with cb3:
    st.markdown("## TOTAL BIENES")
with cb4:
    st.markdown(f"## $ {subtotal_bienes:,.2f}")

st.divider()
subtotal_servicios = _render_tabla_bs(
    "5. SERVICIOS",
    "ci_servicios_data",
    "ci_servicios_widget",
    "5",
    "servicios",
)

cs3, cs4 = st.columns([5, 1])
with cs3:
    st.markdown("## TOTAL SERVICIOS")
with cs4:
    st.markdown(f"## $ {subtotal_servicios:,.2f}")

st.markdown("### IVA")
st.number_input(
    "Porcentaje IVA",
    min_value=0.0,
    step=0.01,
    format="%.2f",
    key="costos_indirectos_iva_pct",
)

# -----------------------------
# RESUMEN FINAL
# -----------------------------
st.divider()
st.markdown("## RESUMEN FINAL")

resumen_base_default = [
    {"Concepto": "Costo personal", "Valor": total_personal, "IVA": "Sí"},
    {"Concepto": "Bienes", "Valor": subtotal_bienes, "IVA": "Sí"},
    {"Concepto": "Servicios", "Valor": subtotal_servicios, "IVA": "Sí"},
]

resumen_base_prev = st.session_state.get("ci_resumen_final_data", []) or []
resumen_base_prev_map = {
    str(row.get("Concepto", "") or "").strip(): str(row.get("IVA", "Sí") or "Sí").strip()
    for row in resumen_base_prev
    if str(row.get("Concepto", "") or "").strip()
}

resumen_base_df = pd.DataFrame(
    [
        {
            "Concepto": row["Concepto"],
            "Valor": row["Valor"],
            "IVA": resumen_base_prev_map.get(row["Concepto"], row["IVA"]),
        }
        for row in resumen_base_default
    ]
)

iva_pct_resumen = float(st.session_state.get("costos_indirectos_iva_pct", 19.0) or 0.0)

resumen_base_df["VALOR TOTAL"] = resumen_base_df.apply(
    lambda r: float(pd.to_numeric(r["Valor"], errors="coerce") or 0.0) * (1 + iva_pct_resumen / 100.0)
    if str(r["IVA"] or "").strip() == "Sí"
    else float(pd.to_numeric(r["Valor"], errors="coerce") or 0.0),
    axis=1,
)

resumen_editado = st.data_editor(
    resumen_base_df,
    hide_index=True,
    width="stretch",
    num_rows="fixed",
    key="ci_resumen_final_widget",
    column_config={
        "Concepto": st.column_config.TextColumn("Concepto", disabled=True),
        "Valor": st.column_config.NumberColumn("Valor", format="$ %.2f", disabled=True),
        "IVA": st.column_config.SelectboxColumn("IVA", options=["Sí", "No"]),
        "VALOR TOTAL": st.column_config.NumberColumn("VALOR TOTAL", format="$ %.2f", disabled=True),
    },
    disabled=["Concepto", "Valor", "VALOR TOTAL"],
)

if isinstance(resumen_editado, pd.DataFrame) and not resumen_editado.empty:
    resumen_base_df = resumen_editado.copy()

resumen_base_df["VALOR TOTAL"] = resumen_base_df.apply(
    lambda r: float(pd.to_numeric(r["Valor"], errors="coerce") or 0.0) * (1 + iva_pct_resumen / 100.0)
    if str(r["IVA"] or "").strip() == "Sí"
    else float(pd.to_numeric(r["Valor"], errors="coerce") or 0.0),
    axis=1,
)

st.session_state["ci_resumen_final_data"] = resumen_base_df.to_dict(orient="records")

costo_directo_total = float(pd.to_numeric(resumen_base_df["Valor"], errors="coerce").fillna(0.0).sum())
iva_total = float(pd.to_numeric(resumen_base_df["VALOR TOTAL"], errors="coerce").fillna(0.0).sum()) - costo_directo_total
total_general = float(pd.to_numeric(resumen_base_df["VALOR TOTAL"], errors="coerce").fillna(0.0).sum())

resumen_totales = pd.DataFrame(
    [
        {"Concepto": "Total costo directo", "Valor": costo_directo_total},
        {"Concepto": "IVA total", "Valor": iva_total},
        {"Concepto": "TOTAL", "Valor": total_general},
    ]
)

st.dataframe(
    resumen_totales,
    hide_index=True,
    width="stretch",
    column_config={
        "Concepto": st.column_config.TextColumn("Concepto"),
        "Valor": st.column_config.NumberColumn("Valor", format="$ %.2f"),
    },
)
