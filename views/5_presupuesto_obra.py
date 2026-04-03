import copy
import json
from datetime import datetime

import pandas as pd
import streamlit as st

from supabase_state import cargar_estado, guardar_estado, get_supabase_client, cargar_apus_generados_obra


# ==========================================================
# CONFIGURACIÓN BASE
# ==========================================================
st.markdown("## 💰 PRESUPUESTO DE OBRA")

cronograma_datos = st.session_state.get("cronograma_datos", {}) or {}
tipo_presupuesto_proyecto = str(cronograma_datos.get("tipo_presupuesto_proyecto", "Obra") or "Obra").strip()

if tipo_presupuesto_proyecto != "Obra":
    st.warning("Este proyecto está clasificado como Consultoría. Los ítems no se cargan en Presupuesto de Obra.")
    st.stop()

if "apus_generados_obra" not in st.session_state:
    st.session_state["apus_generados_obra"] = cargar_apus_generados_obra()

FUENTE_OPTIONS_DEFAULT = ["", "OPCION_1", "OPCION_2"]
DIST_OPTIONS_DEFAULT = ["", "SI", "NO"]
# ==========================================================
# HELPERS GENERALES
# ==========================================================
def _json_clone(obj):
    return json.loads(json.dumps(obj, default=str))


def _money(value):
    try:
        return f"$ {float(value):,.2f}"
    except Exception:
        return "$ 0.00"


def _safe_float(value, default=0.0):
    try:
        if value in ("", None):
            return default
        return float(value)
    except Exception:
        return default


def _safe_int_year(value):
    try:
        return int(value)
    except Exception:
        return datetime.now().year


def _normalize_text(text):
    return str(text or "").strip().upper()


def _get_fuente_options():
    opciones = st.session_state.get("presupuesto_obra_fuente_options")
    if isinstance(opciones, list) and opciones:
        opciones_limpias = [str(x) for x in opciones]
        if "" not in opciones_limpias:
            opciones_limpias = [""] + opciones_limpias
        return opciones_limpias
    return FUENTE_OPTIONS_DEFAULT


def _get_dist_options():
    opciones = st.session_state.get("presupuesto_obra_dist_options")
    if isinstance(opciones, list) and opciones:
        opciones_limpias = [str(x) for x in opciones]
        if "" not in opciones_limpias:
            opciones_limpias = [""] + opciones_limpias
        return opciones_limpias
    return DIST_OPTIONS_DEFAULT


def _cargar_tabla_factor_distancia():
    ruta = "data/Factor Distancia.xlsx"
    try:
        df = pd.read_excel(ruta)
    except Exception:
        return []

    columnas_requeridas = {"PROVINCIA", "MUNICIPIO", "F.I.D."}
    if not columnas_requeridas.issubset(set(df.columns)):
        return []

    df = df[["PROVINCIA", "MUNICIPIO", "F.I.D."]].copy()
    df["PROVINCIA"] = df["PROVINCIA"].astype(str).str.strip()
    df["MUNICIPIO"] = df["MUNICIPIO"].astype(str).str.strip()
    df["F.I.D."] = pd.to_numeric(df["F.I.D."], errors="coerce").fillna(0.0)
    registros = df.to_dict(orient="records")
    st.session_state["presupuesto_obra_factor_distancia_tabla"] = registros
    return registros


def _get_tabla_factor_distancia():
    tabla = st.session_state.get("presupuesto_obra_factor_distancia_tabla", [])
    if isinstance(tabla, list) and tabla:
        return tabla
    return _cargar_tabla_factor_distancia()


def _get_factor_proyecto():
    factor = st.session_state.get("presupuesto_obra_factor_valor", 0.0)
    try:
        factor = float(factor)
    except Exception:
        factor = 0.0
    return factor


def _get_aiu_pct_global():
    """
    Temporal.
    """
    datos = st.session_state.get("presupuesto_obra_datos", {})
    config = datos.get("configuracion", {})
    try:
        return float(config.get("aiu_pct_global", 0.0))
    except Exception:
        return 0.0


def _cargar_catalogo_precios():
    """
    Lee el catálogo interno desde Supabase y lo deja en session_state.
    Trae todos los registros por bloques para evitar el límite de 1000 filas.
    """
    rows = []
    try:
        supabase = get_supabase_client()

        page_size = 1000
        start = 0

        while True:
            resp = (
                supabase.table("catalogo_precios_gobernacion")
                .select('"CAPITULO","SUBCAPITULO","CÓDIGO","NOMBRE DE LA ACTIVIDAD","UNIDAD","COSTO DIRECTO"')
                .eq("activo", True)
                .order('"CÓDIGO"')
                .range(start, start + page_size - 1)
                .execute()
            )

            batch = resp.data or []
            if not batch:
                break

            rows.extend(batch)

            if len(batch) < page_size:
                break

            start += page_size
    except Exception:
        rows = []

    catalogo = []
    for row in rows:
        nombre = str(row.get("NOMBRE DE LA ACTIVIDAD", "") or "").strip()
        if not nombre:
            continue

        costo_raw = str(row.get("COSTO DIRECTO", "") or "").strip().replace(".", "").replace(",", ".")
        try:
            costo = float(costo_raw) if costo_raw else 0.0
        except Exception:
            costo = 0.0

        catalogo.append(
            {
                "capitulo": str(row.get("CAPITULO", "") or "").strip(),
                "subcapitulo": str(row.get("SUBCAPITULO", "") or "").strip(),
                "codigo": str(row.get("CÓDIGO", "") or "").strip(),
                "nombre": nombre,
                "unidad": str(row.get("UNIDAD", "") or "").strip(),
                "vr_unitario": costo,
                "label": nombre,
            }
        )

    st.session_state["presupuesto_obra_catalogo_items"] = catalogo
    return catalogo

def _get_catalogo_precios():
    items = st.session_state.get("presupuesto_obra_catalogo_items", [])
    if isinstance(items, list) and items:
        return items
    return _cargar_catalogo_precios()


def _buscar_item_catalogo_por_nombre(nombre_item, catalogo_items):
    nombre_norm = str(nombre_item or "").strip().upper()
    if not nombre_norm:
        return None

    for row in catalogo_items:
        if str(row.get("nombre", "") or "").strip().upper() == nombre_norm:
            return row

    return None


def _build_catalog_index():
    catalogo_items = _get_catalogo_precios()
    index = {}

    for row in catalogo_items:
        codigo = _normalize_text(row.get("codigo"))
        if not codigo:
            continue

        codigo_raw = str(row.get("codigo", "") or "").strip()
        nombre_raw = str(row.get("nombre", "") or "").strip()

        index[codigo] = {
            "codigo": codigo_raw,
            "nombre": nombre_raw,
            "label": f"{codigo_raw} | {nombre_raw}" if codigo_raw and nombre_raw else codigo_raw,
            "unidad": row.get("unidad", "") or "",
            "vr_unitario": _safe_float(row.get("vr_unitario", 0), 0.0),
        }

    return index


def _buscar_en_catalogo(codigo_item, fuente, catalog_index):
    codigo_norm = _normalize_text(codigo_item)

    if not codigo_norm:
        return {
            "found": False,
            "codigo": "",
            "unidad": "",
            "vr_unitario": 0.0,
            "mensaje": "SIN CÓDIGO",
        }

    exacto = catalog_index.get(codigo_norm)
    if exacto:
        return {
            "found": True,
            "codigo": exacto.get("codigo", "") or "",
            "unidad": exacto.get("unidad", "") or "",
            "vr_unitario": _safe_float(exacto.get("vr_unitario", 0), 0.0),
            "mensaje": "",
        }

    return {
        "found": False,
        "codigo": "",
        "unidad": "",
        "vr_unitario": 0.0,
        "mensaje": "ÍTEM NO ENCONTRADO EN CATÁLOGO",
    }
# ==========================================================
# EXTRACCIÓN EDT
# ==========================================================
def _extraer_grupos_desde_edt(alcance):
    """
    Regla:
    - usar siempre los dos últimos niveles reales de la EDT
    - penúltimo nivel = grupo
    - último nivel = filas presupuestables

    Casos:
    1) objetivo -> producto
       grupo = OBJETIVO
       filas = PRODUCTOS

    2) objetivo -> producto -> actividad
       grupo = PRODUCTO
       filas = ACTIVIDADES

    3) objetivo -> producto -> actividad -> paquete
       grupo = ACTIVIDAD
       filas = PAQUETES
    """
    grupos = []

    objetivos = alcance.get("objetivos", []) or []
    edt_data = alcance.get("edt_data", {}) or {}

    for i, obj in enumerate(objetivos):
        oid = obj.get("id")
        cod_obj = f"{i + 1}"
        nom_obj = obj.get("texto", "Objetivo")

        productos = edt_data.get(oid, []) or []
        rows_obj = []

        for j, prod in enumerate(productos):
            pid = prod.get("id")
            cod_prod = f"{cod_obj}.{j + 1}"
            nom_prod = prod.get("nombre", "Producto")
            actividades = prod.get("actividades", []) or []

            if not actividades:
                rows_obj.append(
                    {
                        "node_id": str(pid),
                        "item": cod_prod,
                        "descripcion": nom_prod,
                    }
                )
                continue

            rows_prod = []

            for k, act in enumerate(actividades):
                aid = act.get("id")
                cod_act = f"{cod_prod}.{k + 1}"
                nom_act = act.get("nombre", "Actividad")
                paquetes = act.get("paquetes", []) or []

                if not paquetes:
                    rows_prod.append(
                        {
                            "node_id": str(aid),
                            "item": cod_act,
                            "descripcion": nom_act,
                        }
                    )
                    continue

                grupo_act = {
                    "group_id": str(aid),
                    "group_code": cod_act,
                    "group_name": nom_act,
                    "rows": [],
                }

                for l, pq in enumerate(paquetes):
                    pqid = str(pq.get("id"))
                    cod_paq = f"{cod_act}.{l + 1}"
                    nom_paq = pq.get("nombre", "Paquete")

                    grupo_act["rows"].append(
                        {
                            "node_id": pqid,
                            "item": cod_paq,
                            "descripcion": nom_paq,
                        }
                    )

                grupos.append(grupo_act)

            if rows_prod:
                grupos.append(
                    {
                        "group_id": str(pid),
                        "group_code": cod_prod,
                        "group_name": nom_prod,
                        "rows": rows_prod,
                    }
                )

        if rows_obj:
            grupos.append(
                {
                    "group_id": str(oid),
                    "group_code": cod_obj,
                    "group_name": nom_obj,
                    "rows": rows_obj,
                }
            )

    return grupos

def _edt_signature(grupos):
    base = []
    for g in grupos:
        base.append(
            {
                "group_id": g["group_id"],
                "group_code": g["group_code"],
                "group_name": g["group_name"],
                "rows": [
                    {
                        "node_id": r["node_id"],
                        "item": r["item"],
                        "descripcion": r["descripcion"],
                    }
                    for r in g.get("rows", [])
                ],
            }
        )
    return json.dumps(base, ensure_ascii=False, sort_keys=True)


# ==========================================================
# ESTADO
# ==========================================================
def _init_presupuesto_obra_state():
    if "presupuesto_obra_datos" not in st.session_state:
        try:
            st.session_state["presupuesto_obra_datos"] = cargar_estado("presupuesto_obra") or {}
        except Exception:
            st.session_state["presupuesto_obra_datos"] = {}
            st.session_state["presupuesto_obra_load_warning"] = (
                "No se pudo cargar PRESUPUESTO DE OBRA desde la nube en este momento. "
                "Se abrió una versión local temporal."
            )

    datos = st.session_state["presupuesto_obra_datos"]

    if not isinstance(datos, dict):
        datos = {}

    if "anio" not in datos:
        datos["anio"] = datetime.now().year

    if "items" not in datos or not isinstance(datos["items"], dict):
        datos["items"] = {}

    if "configuracion" not in datos or not isinstance(datos["configuracion"], dict):
        datos["configuracion"] = {}

    if "aiu_pct_global" not in datos["configuracion"]:
        datos["configuracion"]["aiu_pct_global"] = 0.0

    if "aiu_administracion_pct" not in datos["configuracion"]:
        datos["configuracion"]["aiu_administracion_pct"] = 0.0

    if "aiu_imprevistos_pct" not in datos["configuracion"]:
        datos["configuracion"]["aiu_imprevistos_pct"] = 0.0

    if "aiu_utilidad_pct" not in datos["configuracion"]:
        datos["configuracion"]["aiu_utilidad_pct"] = 0.0

    if "otros_costos_indirectos" not in datos["configuracion"] or not isinstance(datos["configuracion"]["otros_costos_indirectos"], list):
        datos["configuracion"]["otros_costos_indirectos"] = [
            {
                "id": f"oci_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "nombre": "",
                "valor": 0.0
            }
        ]

    if "sincronizacion" not in datos or not isinstance(datos["sincronizacion"], dict):
        datos["sincronizacion"] = {}

    if "avisos" not in datos or not isinstance(datos["avisos"], dict):
        datos["avisos"] = {}

    st.session_state["presupuesto_obra_datos"] = datos
    return datos


def _sync_presupuesto_obra_con_edt(forzar=False):
    alcance = st.session_state.get("alcance_datos", {}) or {}
    datos = st.session_state["presupuesto_obra_datos"]

    grupos = _extraer_grupos_desde_edt(alcance)
    firma_actual = _edt_signature(grupos)
    firma_guardada = datos.get("sincronizacion", {}).get("edt_signature")

    if not forzar and firma_actual == firma_guardada:
        return grupos, False

    items_previos = copy.deepcopy(datos.get("items", {}))
    nuevos_items = {}

    for grupo in grupos:
        for row in grupo.get("rows", []):
            node_id = row["node_id"]
            previo = items_previos.get(node_id, {})

            nuevos_items[node_id] = {
                "fuente": previo.get("fuente", ""),
                "item_catalogo": previo.get("item_catalogo", ""),
                "dist": previo.get("dist", ""),
                "cant": _safe_float(previo.get("cant", 0), 0.0),
            }

    datos["items"] = nuevos_items
    datos["sincronizacion"]["edt_signature"] = firma_actual
    datos["sincronizacion"]["ultima_sync"] = datetime.now().isoformat(timespec="seconds")
    datos["avisos"]["sync_msg"] = "La hoja PRESUPUESTO DE OBRA se sincronizó con la EDT."
    datos["avisos"]["sync_flag"] = True

    st.session_state["presupuesto_obra_datos"] = datos
    return grupos, True


# ==========================================================
# CÁLCULO
# ==========================================================
def _construir_grupos_calculados():
    alcance = st.session_state.get("alcance_datos", {}) or {}
    datos = st.session_state["presupuesto_obra_datos"]
    grupos = _extraer_grupos_desde_edt(alcance)
    items_state = datos.get("items", {})

    catalog_index = _build_catalog_index()
    factor = _get_factor_proyecto()
    aiu_pct = _get_aiu_pct_global()

    grupos_out = []
    total_general_directo = 0.0

    for grupo in grupos:
        filas = []
        costo_directo_grupo = 0.0

        for row in grupo.get("rows", []):
            node_id = row["node_id"]
            descripcion = row["descripcion"]
            item_state = items_state.get(node_id, {})

            fuente = item_state.get("fuente", "") or ""
            item_catalogo = item_state.get("item_catalogo", "") or ""
            dist = item_state.get("dist", "") or ""
            cant = _safe_float(item_state.get("cant", 0), 0.0)
            
            item_catalogo_display = ""

            if fuente == "Precios Gobernación de Boyacá" and item_catalogo:
                catalogo = _buscar_en_catalogo(item_catalogo, "", catalog_index)

                if catalogo["found"]:
                    unidad_display = catalogo["unidad"] or ""
                    vr_unitario = _safe_float(catalogo["vr_unitario"], 0.0)

                    catalogo_info = catalog_index.get(_normalize_text(item_catalogo), {}) or {}
                    item_catalogo_display = str(catalogo_info.get("codigo", "") or "").strip() or str(item_catalogo or "").strip()
                else:
                    unidad_display = ""
                    vr_unitario = 0.0
                    item_catalogo_display = str(item_catalogo or "").strip()
            elif fuente == "APU generado":
                apu_generado = (st.session_state.get("apus_generados_obra", {}) or {}).get(str(node_id), {})
                unidad_display = str(apu_generado.get("unidad_apu", "") or "").strip() or "GLOBAL"
                vr_unitario = _safe_float(apu_generado.get("total_apu", 0.0), 0.0)
            else:
                unidad_display = ""
                vr_unitario = 0.0
                
            if dist == "SI":
                factor_fila = factor
                vr_afectado = vr_unitario * (1 + factor_fila) if vr_unitario > 0 else 0.0
                vr_total = vr_afectado * cant if (vr_afectado > 0 and cant > 0) else 0.0
            else:
                factor_fila = 0.0
                vr_afectado = vr_unitario
                vr_total = vr_unitario * cant if (vr_unitario > 0 and cant > 0) else 0.0

            costo_directo_grupo += vr_total
            total_general_directo += vr_total

            filas.append(
                {
                    "node_id": node_id,
                    "ITEM": row["item"],
                    "DESCRIPCIÓN": descripcion,
                    "FUENTE": fuente,
                    "ÍTEM CATÁLOGO": item_catalogo_display,
                    "UNIDAD": unidad_display,
                    "CANT": cant,
                    "VR UNITARIO": vr_unitario,
                    "DIST.": dist,
                    "FACTOR": factor_fila,
                    "VR AFECTADO POR FACTOR": vr_afectado,
                    "VR TOTAL": vr_total,
                    "%": 0.0,
                }
            )

        aiu_grupo = costo_directo_grupo * (aiu_pct / 100.0)

        grupos_out.append(
            {
                "group_id": grupo["group_id"],
                "group_code": grupo["group_code"],
                "group_name": grupo["group_name"],
                "rows": filas,
                "costo_directo_grupo": costo_directo_grupo,
                "aiu_grupo": aiu_grupo,
            }
        )

    for grupo in grupos_out:
        for fila in grupo["rows"]:
            vr_total = _safe_float(fila["VR TOTAL"], 0.0)
            fila["%"] = (vr_total / total_general_directo * 100.0) if total_general_directo > 0 else 0.0

    return grupos_out, total_general_directo


def _persistir_ediciones_desde_df(df_editado, rows_originales):
    datos = st.session_state["presupuesto_obra_datos"]
    items_state = datos.get("items", {})
    catalog_index = _build_catalog_index()

    for idx, row_original in enumerate(rows_originales):
        node_id = row_original["node_id"]
        if idx >= len(df_editado):
            continue

        fila = df_editado.iloc[idx].to_dict()

        item_state = items_state.get(node_id, {})
        fuente = str(fila.get("FUENTE", "") or "").strip()
        item_catalogo = str(item_state.get("item_catalogo", "") or "").strip()
        item_gober = str(fila.get("ITEM GOBER", "") or "").strip()
        item_gober_sel = str(fila.get("SELECCIONAR GOBER", "") or "").strip()
        dist = fila.get("DIST.", "")
        cantidad = _safe_float(fila.get("CANT", 0), 0.0)

        if fuente == "Precios Gobernación de Boyacá":
            if item_gober_sel:
                codigo_sel = item_gober_sel.split(" | ", 1)[0].strip()
                if catalog_index.get(_normalize_text(codigo_sel)):
                    item_catalogo = codigo_sel
                else:
                    item_catalogo = ""
            elif item_gober:
                codigo_sel = item_gober.split(" | ", 1)[0].strip()
                if catalog_index.get(_normalize_text(codigo_sel)):
                    item_catalogo = codigo_sel
                else:
                    item_catalogo = ""
            else:
                item_catalogo = ""
        else:
            item_catalogo = ""

        if cantidad < 0:
            cantidad = 0.0

        items_state[node_id] = {
            "fuente": fuente,
            "item_catalogo": item_catalogo,
            "dist": dist,
            "cant": cantidad,
        }

    datos["items"] = items_state
    st.session_state["presupuesto_obra_datos"] = datos


# ==========================================================
# INICIALIZACIÓN
# ==========================================================
_init_presupuesto_obra_state()

alcance = st.session_state.get("alcance_datos", {}) or {}
nombre_proyecto = alcance.get("nombre_proyecto", "") or "SIN NOMBRE DEFINIDO"

_sync_presupuesto_obra_con_edt(forzar=True)
grupos_calculados, total_general_directo = _construir_grupos_calculados()
st.session_state["presupuesto_obra_costo_directo_total"] = float(total_general_directo or 0.0)
st.session_state["presupuesto_obra_datos"]["resumen"] = {
    "costo_directo_total": float(total_general_directo or 0.0)
}

flujo_fondos_directos = []
for grupo in grupos_calculados:
    for fila in grupo.get("rows", []):
        valor_base = float(_safe_float(fila.get("VR TOTAL", 0.0), 0.0))
        if valor_base <= 0:
            continue

        flujo_fondos_directos.append(
            {
                "node_id": str(fila.get("node_id", "") or "").strip(),
                "ITEM": str(fila.get("ITEM", "") or "").strip(),
                "DESCRIPCIÓN": str(fila.get("DESCRIPCIÓN", "") or "").strip(),
                "VALOR BASE": valor_base,
            }
        )

st.session_state["presupuesto_obra_datos"]["flujo_fondos_directos"] = flujo_fondos_directos

# ==========================================================
# CABECERA
# ==========================================================
col1, col2 = st.columns([6, 2], vertical_alignment="center")

with col1:
    st.markdown(f"**Proyecto:** {nombre_proyecto}")

with col2:
    anio_actual = _safe_int_year(st.session_state["presupuesto_obra_datos"].get("anio"))
    nuevo_anio = st.number_input(
        "AÑO",
        min_value=2000,
        max_value=2100,
        value=anio_actual,
        step=1,
        key="presupuesto_obra_anio_input",
    )
    st.session_state["presupuesto_obra_datos"]["anio"] = int(nuevo_anio)

if st.session_state.get("presupuesto_obra_load_warning"):
    st.warning(st.session_state["presupuesto_obra_load_warning"])
    st.session_state.pop("presupuesto_obra_load_warning", None)

if st.session_state["presupuesto_obra_datos"].get("avisos", {}).get("sync_flag"):
    st.success(st.session_state["presupuesto_obra_datos"]["avisos"].get("sync_msg", "Sincronización realizada."))
    st.session_state["presupuesto_obra_datos"]["avisos"]["sync_flag"] = False

factor_temporal = _get_factor_proyecto()
if factor_temporal == 1:
    st.info("FACTOR temporal aplicado: 1.00. Este valor se reemplazará cuando se conecte la hoja del factor.")

aiu_pct_global = _get_aiu_pct_global()
if aiu_pct_global == 0:
    st.info("A.I.U. global temporal: 0.00%. El porcentaje definitivo se conectará después.")

st.divider()


tabla_factor_distancia = _get_tabla_factor_distancia()
municipios_factor = sorted({str(x.get("MUNICIPIO", "") or "").strip() for x in tabla_factor_distancia if str(x.get("MUNICIPIO", "") or "").strip()})

if not tabla_factor_distancia:
    st.error("No se pudo leer la tabla de factor de distancia desde data/Factor Distancia.xlsx")
else:
    st.caption(f"Tabla de factor de distancia cargada: {len(tabla_factor_distancia)} registros")

municipio_guardado = str(
    st.session_state["presupuesto_obra_datos"].get("configuracion", {}).get("municipio_factor_distancia", "")
    or ""
).strip()

factor_guardado = float(
    st.session_state["presupuesto_obra_datos"].get("configuracion", {}).get("factor_distancia_valor", 0.0)
    or 0.0
)

if "presupuesto_obra_municipio" not in st.session_state:
    st.session_state["presupuesto_obra_municipio"] = municipio_guardado
elif not str(st.session_state.get("presupuesto_obra_municipio", "") or "").strip() and municipio_guardado:
    st.session_state["presupuesto_obra_municipio"] = municipio_guardado

if "presupuesto_obra_factor_valor" not in st.session_state:
    st.session_state["presupuesto_obra_factor_valor"] = factor_guardado

def _on_change_municipio_factor_distancia():
    municipio_cb = str(st.session_state.get("presupuesto_obra_municipio", "") or "").strip()
    factor_cb = 0.0

    if municipio_cb:
        fila_factor_cb = next(
            (x for x in tabla_factor_distancia if str(x.get("MUNICIPIO", "") or "").strip() == municipio_cb),
            None
        )
        if fila_factor_cb:
            try:
                factor_cb = float(fila_factor_cb.get("F.I.D.", 0.0) or 0.0)
            except Exception:
                factor_cb = 0.0

    st.session_state["presupuesto_obra_factor_valor"] = factor_cb
    st.session_state["presupuesto_obra_datos"]["configuracion"]["municipio_factor_distancia"] = municipio_cb
    st.session_state["presupuesto_obra_datos"]["configuracion"]["factor_distancia_valor"] = factor_cb

municipio_sel = st.selectbox(
    "Municipio para factor de distancia",
    options=[""] + municipios_factor,
    key="presupuesto_obra_municipio",
    on_change=_on_change_municipio_factor_distancia,
)

factor_sel = float(st.session_state.get("presupuesto_obra_factor_valor", 0.0) or 0.0)

if municipio_sel:
    fila_factor = next(
        (x for x in tabla_factor_distancia if str(x.get("MUNICIPIO", "") or "").strip() == municipio_sel),
        None
    )
    if fila_factor:
        try:
            factor_sel = float(fila_factor.get("F.I.D.", 0.0) or 0.0)
        except Exception:
            factor_sel = 0.0

st.session_state["presupuesto_obra_factor_valor"] = factor_sel
st.session_state["presupuesto_obra_datos"]["configuracion"]["factor_distancia_valor"] = factor_sel

if municipio_sel:
    st.caption(f"Factor de incremento por distancia seleccionado: {factor_sel:.4f}")

grupos_calculados, total_general_directo = _construir_grupos_calculados()
st.session_state["presupuesto_obra_costo_directo_total"] = float(total_general_directo or 0.0)
st.session_state["presupuesto_obra_datos"]["resumen"] = {
    "costo_directo_total": float(total_general_directo or 0.0)
}

# ==========================================================
# BOTONERA
# ==========================================================
c1 = st.columns([1], vertical_alignment="bottom")[0]

with c1:
    if st.button("Guardar presupuesto", use_container_width=True):
        try:
            guardar_estado("presupuesto_obra", _json_clone(st.session_state["presupuesto_obra_datos"]))
            st.success("Presupuesto de obra guardado correctamente.")
        except Exception as e:
            st.error("No se pudo guardar en la nube en este momento. Verifica la sesión e inténtalo de nuevo.")
            st.code(str(e))

st.divider()


# ==========================================================
# VALIDACIÓN BASE
# ==========================================================
if not alcance.get("objetivos") or not alcance.get("edt_data"):
    st.warning("No existe una EDT disponible en ALCANCE para construir el presupuesto de obra.")
    st.stop()

if not grupos_calculados:
    st.warning("No se encontraron niveles presupuestables en la EDT.")
    st.stop()


# ==========================================================
# TABLAS POR GRUPO
# ==========================================================
fuente_options = ["Precios Gobernación de Boyacá", "APU generado"]
catalogo_items = _get_catalogo_precios()
catalogo_nombres = [x.get("nombre", "") for x in catalogo_items if str(x.get("nombre", "")).strip()]
dist_options = _get_dist_options()

st.markdown("### Selección de ítem de catálogo")

catalogo_items_global = sorted(
    _get_catalogo_precios(),
    key=lambda x: str(x.get("codigo", "") or "").strip()
)

row_map_item_to_node_global = {}
pendientes_presupuesto_global = []

for grupo_tmp in grupos_calculados:
    for fila_tmp in grupo_tmp["rows"]:
        item_codigo_tmp = str(fila_tmp.get("ITEM", "") or "").strip()
        node_id_tmp = fila_tmp.get("node_id")
        if item_codigo_tmp and node_id_tmp:
            row_map_item_to_node_global[item_codigo_tmp] = node_id_tmp

        if str(fila_tmp.get("FUENTE", "") or "").strip() != "Precios Gobernación de Boyacá":
            continue

        item_state_tmp = st.session_state["presupuesto_obra_datos"]["items"].get(node_id_tmp, {})
        actual_codigo_catalogo_tmp = str(item_state_tmp.get("item_catalogo", "") or "").strip()

        if not actual_codigo_catalogo_tmp:
            pendientes_presupuesto_global.append(
                {
                    "item": item_codigo_tmp,
                    "node_id": node_id_tmp,
                    "descripcion": str(fila_tmp.get("DESCRIPCIÓN", "") or "").strip(),
                }
            )

if pendientes_presupuesto_global:
    opciones_presupuesto_global = [
        f"{x['item']} | {x['descripcion']}"
        for x in pendientes_presupuesto_global
    ]

    key_item_pres_global = "pres_item_selector_global"
    key_cap_global = "catalogo_capitulo_global"
    key_sub_global = "catalogo_subcapitulo_global"
    key_item_cat_global = "catalogo_item_selector_global"

    st.session_state.setdefault(key_item_pres_global, "")
    st.session_state.setdefault(key_cap_global, "")
    st.session_state.setdefault(key_sub_global, "")
    st.session_state.setdefault(key_item_cat_global, "")

    # 1) Todos los capítulos del catálogo
    capitulos_global = sorted(
        list({
            str(x.get("capitulo", "") or "").strip()
            for x in catalogo_items_global
            if str(x.get("capitulo", "") or "").strip()
        })
    )

    # 2) Filtrar por capítulo (opcional)
    capitulo_sel = str(st.session_state.get(key_cap_global, "") or "").strip()
    if capitulo_sel:
        items_filtrados_cap_global = [
            x for x in catalogo_items_global
            if str(x.get("capitulo", "") or "").strip() == capitulo_sel
        ]
    else:
        items_filtrados_cap_global = list(catalogo_items_global)

    # 3) Subcapítulos válidos según el capítulo filtrado
    subcapitulos_global = sorted(
        list({
            str(x.get("subcapitulo", "") or "").strip()
            for x in items_filtrados_cap_global
            if str(x.get("subcapitulo", "") or "").strip()
        })
    )

    # Si el subcapítulo actual ya no existe dentro del capítulo elegido, lo limpia
    subcapitulo_sel = str(st.session_state.get(key_sub_global, "") or "").strip()
    if subcapitulo_sel and subcapitulo_sel not in subcapitulos_global:
        st.session_state[key_sub_global] = ""
        subcapitulo_sel = ""

    # 4) Filtrar por subcapítulo (opcional)
    if subcapitulo_sel:
        items_filtrados_global = [
            x for x in items_filtrados_cap_global
            if str(x.get("subcapitulo", "") or "").strip() == subcapitulo_sel
        ]
    else:
        items_filtrados_global = list(items_filtrados_cap_global)

    # 5) Construir opciones finales de ítems del catálogo
    catalogo_labels_global = sorted(
        [
            f"{str(x.get('codigo', '') or '').strip()} | {str(x.get('nombre', '') or '').strip()}"
            for x in items_filtrados_global
            if str(x.get("nombre", "")).strip()
        ]
    )

    catalogo_map_global = {
        f"{str(x.get('codigo', '') or '').strip()} | {str(x.get('nombre', '') or '').strip()}": x
        for x in items_filtrados_global
        if str(x.get("nombre", "")).strip()
    }

    #    # Si el ítem seleccionado ya no existe por cambio de filtros, lo limpia
    if st.session_state.get("presupuesto_obra_limpiar_selectores_catalogo_global", False):
        st.session_state[key_item_pres_global] = ""
        st.session_state[key_cap_global] = ""
        st.session_state[key_sub_global] = ""
        st.session_state[key_item_cat_global] = ""
        st.session_state["presupuesto_obra_limpiar_selectores_catalogo_global"] = False

    item_cat_sel = str(st.session_state.get(key_item_cat_global, "") or "").strip()
    if item_cat_sel and item_cat_sel not in catalogo_labels_global:
        st.session_state[key_item_cat_global] = ""

    with st.sidebar:
        st.markdown("### Asociación con catálogo")

        st.selectbox(
            "Ítem del presupuesto",
            options=[""] + opciones_presupuesto_global,
            key=key_item_pres_global,
        )

        st.selectbox(
            "Capítulo",
            options=[""] + capitulos_global,
            key=key_cap_global,
        )

        st.selectbox(
            "Subcapítulo",
            options=[""] + subcapitulos_global,
            key=key_sub_global,
        )

        st.selectbox(
            "Ítem del catálogo",
            options=[""] + catalogo_labels_global,
            key=key_item_cat_global,
        )

        asociar_global = st.button(
            "Asociar",
            key="asociar_catalogo_global",
            use_container_width=True,
        )

    if asociar_global and st.session_state[key_item_pres_global] and st.session_state[key_item_cat_global]:
        item_pres_global = st.session_state[key_item_pres_global].split(" | ", 1)[0].strip()
        node_id_global = row_map_item_to_node_global.get(item_pres_global)

        if node_id_global and st.session_state[key_item_cat_global] in catalogo_map_global:
            info_global = catalogo_map_global[st.session_state[key_item_cat_global]]
            st.session_state["presupuesto_obra_datos"]["items"].setdefault(node_id_global, {})
            st.session_state["presupuesto_obra_datos"]["items"][node_id_global]["item_catalogo"] = str(info_global.get("codigo", "") or "").strip()
            st.session_state["presupuesto_obra_limpiar_selectores_catalogo_global"] = True
            st.rerun()
else:
    st.info("No hay ítems pendientes por asociar en el presupuesto.")

catalogo_labels_tabla = [""] + sorted(
    [
        str(info.get("label", "") or "").strip()
        for info in (_build_catalog_index().values() or [])
        if str(info.get("label", "") or "").strip()
    ]
)

for grupo in grupos_calculados:
    st.markdown(f"### {grupo['group_code']} {grupo['group_name']}")

    if not grupo["rows"]:
        st.warning("Este grupo no tiene filas presupuestables hijas en la EDT.")
        st.markdown(f"**COSTO DIRECTO GRUPO:** {_money(0)}")
        st.markdown(f"**A.I.U.:** {_money(0)}")
        st.divider()
        continue

    df = pd.DataFrame(grupo["rows"])
    rows_originales = grupo["rows"]

    df_visible = df[
        [
            "ITEM",
            "ÍTEM CATÁLOGO",
            "DESCRIPCIÓN",
            "FUENTE",
            "UNIDAD",
            "CANT",
            "VR UNITARIO",
            "DIST.",
            "FACTOR",
            "VR AFECTADO POR FACTOR",
            "VR TOTAL",
            "%",
        ]
    ].copy()

    df_visible.insert(0, "SELECCIONAR GOBER", "")
    df_visible = df_visible.rename(columns={"ÍTEM CATÁLOGO": "ITEM GOBER"})

    filas_grupo = len(df_visible)
    alto_editor = max(220, 35 * (filas_grupo + 1) + 10)

    # Selector global de catálogo renderizado antes de todos los grupos

    editor_key = f"presupuesto_obra_editor_{grupo['group_id']}"

    def _on_change_editor_presupuesto_obra(grupo_id_cb, rows_originales_cb, df_base_cb):
        editor_key_cb = f"presupuesto_obra_editor_{grupo_id_cb}"
        widget_state_cb = st.session_state.get(editor_key_cb, {}) or {}
        edited_rows_cb = widget_state_cb.get("edited_rows", {}) or {}

        if not edited_rows_cb:
            return

        df_cb = df_base_cb.copy()

        for row_idx, cambios in edited_rows_cb.items():
            for col_name, valor in cambios.items():
                if row_idx < len(df_cb) and col_name in df_cb.columns:
                    df_cb.at[row_idx, col_name] = valor

        _persistir_ediciones_desde_df(df_cb, rows_originales_cb)

    edited_df = st.data_editor(
        df_visible,
        hide_index=True,
        use_container_width=True,
        height=alto_editor,
        key=editor_key,
        num_rows="fixed",
        on_change=_on_change_editor_presupuesto_obra,
        args=(grupo["group_id"], rows_originales, df_visible),
        column_config={
            "ITEM": st.column_config.TextColumn("ITEM", disabled=True),
            "SELECCIONAR GOBER": st.column_config.SelectboxColumn(
                "SELECCIONAR GOBER",
                options=catalogo_labels_tabla,
                required=False,
            ),
            "ITEM GOBER": st.column_config.TextColumn("ITEM GOBER", disabled=True),
            "DESCRIPCIÓN": st.column_config.TextColumn("DESCRIPCIÓN", disabled=True),
            "FUENTE": st.column_config.SelectboxColumn("FUENTE", options=fuente_options, required=False),
            "UNIDAD": st.column_config.TextColumn("UNIDAD", disabled=True),
            "CANT": st.column_config.NumberColumn("CANT", min_value=0.0001, step=0.0001, format="%.4f"),
            "VR UNITARIO": st.column_config.NumberColumn("VR UNITARIO", disabled=True, format="$ %.2f"),
            "DIST.": st.column_config.SelectboxColumn("DIST.", options=dist_options, required=False),
            "FACTOR": st.column_config.NumberColumn("FACTOR", disabled=True, format="%.2f"),
            "VR AFECTADO POR FACTOR": st.column_config.NumberColumn("VR AFECTADO POR FACTOR", disabled=True, format="$ %.2f"),
            "VR TOTAL": st.column_config.NumberColumn("VR TOTAL", disabled=True, format="$ %.2f"),
            "%": st.column_config.NumberColumn("%", disabled=True, format="%.2f %%"),
        },
        disabled=[
            "ITEM",
            "ITEM GOBER",
            "DESCRIPCIÓN",
            "UNIDAD",
            "VR UNITARIO",
            "FACTOR",
            "VR AFECTADO POR FACTOR",
            "VR TOTAL",
            "%",
        ],
    )
    
    # Recalcular después de persistir cambios para reflejar valores actuales
    grupos_recalc, _ = _construir_grupos_calculados()
    grupo_recalc = next((g for g in grupos_recalc if g["group_id"] == grupo["group_id"]), None)

    pendientes_catalogo = []
    pendientes_apu = []
    pendientes_asignacion = []

    if grupo_recalc:
        catalog_index = _build_catalog_index()
        for fila in grupo_recalc["rows"]:
            fuente_fila = str(fila.get("FUENTE", "") or "").strip()

            if not fuente_fila or fuente_fila == "None":
                pendientes_asignacion.append(f"{fila['ITEM']} - {fila['DESCRIPCIÓN']}")
            elif fuente_fila == "Precios Gobernación de Boyacá":
                item_state_fila = (st.session_state.get("presupuesto_obra_datos", {}) or {}).get("items", {}).get(str(fila.get("node_id", "")), {}) or {}
                codigo_catalogo_real = str(item_state_fila.get("item_catalogo", "") or "").strip()

                match = _buscar_en_catalogo(codigo_catalogo_real, fila["FUENTE"], catalog_index)
                if not match["found"]:
                    pendientes_catalogo.append(f"{fila['ITEM']} - {fila['DESCRIPCIÓN']}: {match['mensaje']}")
            elif fuente_fila == "APU generado":
                apu_generado = (st.session_state.get("apus_generados_obra", {}) or {}).get(str(fila.get("node_id", "")), {})
                if not apu_generado:
                    pendientes_apu.append(f"{fila['ITEM']} - {fila['DESCRIPCIÓN']}")
                    
    if pendientes_catalogo:
        st.warning("Pendientes de catálogo en este grupo:")
        for p in pendientes_catalogo:
            st.caption(f"- {p}")

    if pendientes_apu:
        st.warning("Pendientes de APU en este grupo:")
        for p in pendientes_apu:
            st.caption(f"- {p}")

    if pendientes_asignacion:
        st.warning("Pendientes de asignación en este grupo:")
        for p in pendientes_asignacion:
            st.caption(f"- {p}")

    costo_directo = grupo_recalc["costo_directo_grupo"] if grupo_recalc else 0.0
    aiu_grupo = grupo_recalc["aiu_grupo"] if grupo_recalc else 0.0

    st.markdown(f"**COSTO DIRECTO GRUPO:** {_money(costo_directo)}")
    st.markdown(f"**A.I.U.:** {_money(aiu_grupo)}")
    st.divider()

st.caption(f"Base actual de cálculo del porcentaje (%): {_money(total_general_directo)}")

st.divider()
st.markdown("## RESUMEN DEL PRESUPUESTO")

datos = st.session_state["presupuesto_obra_datos"]
config = datos.get("configuracion", {})

costo_directo_total = float(total_general_directo or 0.0)

try:
    aiu_datos = cargar_estado("aiu") or {}
except Exception:
    aiu_datos = {}

st.session_state["aiu_datos"] = aiu_datos

aiu_administracion_valor = _safe_float(aiu_datos.get("administracion_valor", 0.0), 0.0)
aiu_imprevistos_valor = _safe_float(aiu_datos.get("imprevistos_valor", 0.0), 0.0)
aiu_utilidad_valor = _safe_float(aiu_datos.get("utilidad_valor", 0.0), 0.0)

if costo_directo_total > 0:
    aiu_administracion_pct = (aiu_administracion_valor / costo_directo_total) * 100.0
    aiu_imprevistos_pct = (aiu_imprevistos_valor / costo_directo_total) * 100.0
    aiu_utilidad_pct = (aiu_utilidad_valor / costo_directo_total) * 100.0
else:
    aiu_administracion_pct = 0.0
    aiu_imprevistos_pct = 0.0
    aiu_utilidad_pct = 0.0

config["aiu_administracion_pct"] = aiu_administracion_pct
config["aiu_imprevistos_pct"] = aiu_imprevistos_pct
config["aiu_utilidad_pct"] = aiu_utilidad_pct
config["aiu_pct_global"] = aiu_administracion_pct + aiu_imprevistos_pct + aiu_utilidad_pct
st.session_state["presupuesto_obra_datos"]["configuracion"] = config

aiu_total = aiu_administracion_valor + aiu_imprevistos_valor + aiu_utilidad_valor
subtotal_presupuesto = costo_directo_total + aiu_total

alcance_costos_indirectos = alcance.get("otros_costos_indirectos_proyecto", []) or []
otros_costos_indirectos = []

for ci in alcance_costos_indirectos:
    ci_id = str(ci.get("id", "") or "").strip()
    ci_nombre = str(ci.get("nombre", "") or "").strip()
    if not ci_id or not ci_nombre:
        continue
    otros_costos_indirectos.append(
        {
            "id": ci_id,
            "nombre": ci_nombre,
            "valor": 0.0,
        }
    )

try:
    costos_indirectos_datos = cargar_estado("costos_indirectos") or {}
except Exception:
    costos_indirectos_datos = {}

registros_por_oci = costos_indirectos_datos.get("registros_por_oci", {}) or {}

for item in otros_costos_indirectos:
    item_id = str(item.get("id", "") or "").strip()
    if not item_id:
        continue

    registro_oci = registros_por_oci.get(item_id, {}) or {}
    item["valor"] = _safe_float(registro_oci.get("valor_total_final", 0.0), 0.0)

config["otros_costos_indirectos"] = otros_costos_indirectos
st.session_state["presupuesto_obra_datos"]["configuracion"] = config

total_otros_costos = sum(_safe_float(x.get("valor", 0.0), 0.0) for x in otros_costos_indirectos)
total_presupuesto = subtotal_presupuesto + total_otros_costos

def _pct_total_presupuesto(valor):
    if total_presupuesto <= 0:
        return 0.0
    return (float(valor) / float(total_presupuesto)) * 100.0

st.markdown(
    """
    <style>
    .pres-row{
        display:grid;
        grid-template-columns: 1.8fr 1fr 120px;
        gap:12px;
        align-items:center;
        padding:8px 0;
        border-bottom:1px solid #E5E7EB;
    }
    .pres-label{font-weight:600;}
    .pres-value{text-align:right; font-weight:700;}
    .pres-pct{text-align:right; color:#374151;}
    .pres-section{
        background:#F8FAFC;
        border:1px solid #E5E7EB;
        border-radius:12px;
        padding:14px 16px;
        margin-bottom:14px;
    }
    .pres-total{
        background:#ECFDF5;
        border:1px solid #A7F3D0;
        border-radius:12px;
        padding:14px 16px;
        margin-top:10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown("<div class='pres-section'>", unsafe_allow_html=True)
st.markdown(
    f"""
    <div class='pres-row'>
        <div class='pres-label'>COSTO DIRECTO</div>
        <div class='pres-value'>{_money(costo_directo_total)}</div>
        <div class='pres-pct'>{_pct_total_presupuesto(costo_directo_total):.2f}%</div>
    </div>

    <div class='pres-row'>
        <div class='pres-label'>A.I.U.</div>
        <div class='pres-value'>{_money(aiu_total)}</div>
        <div class='pres-pct'>{_pct_total_presupuesto(aiu_total):.2f}%</div>
    </div>

    <div class='pres-row'>
        <div class='pres-label' style='padding-left:20px;'>Administración</div>
        <div class='pres-value'>{_money(aiu_administracion_valor)}</div>
        <div class='pres-pct'>{_pct_total_presupuesto(aiu_administracion_valor):.2f}%</div>
    </div>

    <div class='pres-row'>
        <div class='pres-label' style='padding-left:20px;'>Imprevistos</div>
        <div class='pres-value'>{_money(aiu_imprevistos_valor)}</div>
        <div class='pres-pct'>{_pct_total_presupuesto(aiu_imprevistos_valor):.2f}%</div>
    </div>

    <div class='pres-row'>
        <div class='pres-label' style='padding-left:20px;'>Utilidad</div>
        <div class='pres-value'>{_money(aiu_utilidad_valor)}</div>
        <div class='pres-pct'>{_pct_total_presupuesto(aiu_utilidad_valor):.2f}%</div>
    </div>

    <div class='pres-row'>
        <div class='pres-label'>SUBTOTAL</div>
        <div class='pres-value'>{_money(subtotal_presupuesto)}</div>
        <div class='pres-pct'>{_pct_total_presupuesto(subtotal_presupuesto):.2f}%</div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("### Otros costos indirectos")

if not otros_costos_indirectos:
    st.info("No hay costos indirectos definidos en Alcance.")
else:
    for idx, item in enumerate(otros_costos_indirectos):
        c1, c2 = st.columns([5, 2], vertical_alignment="center")

        nombre_actual = str(item.get("nombre", "") or "")
        valor_actual = _safe_float(item.get("valor", 0.0), 0.0)

        c1.markdown(f"**{idx+1}. {nombre_actual}**")
        c2.markdown(
            f"<div style='text-align:right; padding-top:8px; font-weight:700;'>{_money(valor_actual)} &nbsp;&nbsp; {_pct_total_presupuesto(valor_actual):.2f}%</div>",
            unsafe_allow_html=True,
        )

st.markdown(
    f"""
    <div class='pres-section'>
        <div class='pres-row'>
            <div class='pres-label'>TOTAL OTROS COSTOS INDIRECTOS</div>
            <div class='pres-value'>{_money(total_otros_costos)}</div>
            <div class='pres-pct'>{_pct_total_presupuesto(total_otros_costos):.2f}%</div>
        </div>
    </div>

    <div class='pres-row' style='border-bottom:none;'>
        <div class='pres-label' style='font-size:18px;'>TOTAL PRESUPUESTO</div>
        <div class='pres-value' style='font-size:18px;'>{_money(total_presupuesto)}</div>
        <div class='pres-pct' style='font-size:18px;'>{_pct_total_presupuesto(total_presupuesto):.2f}%</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.session_state["presupuesto_obra_datos"] = _json_clone(st.session_state["presupuesto_obra_datos"])
