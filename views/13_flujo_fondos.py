import math
from typing import Dict, List, Set

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_echarts import st_echarts

from supabase_state import cargar_estado, guardar_estado


# ==========================================================
# Helpers generales
# ==========================================================
def _safe_float(value, default=0.0) -> float:
    try:
        if value is None or value == "":
            return float(default)
        return float(value)
    except Exception:
        return float(default)



def _safe_str(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _key_codigo_natural(value: str):
    partes = []
    for chunk in _safe_str(value).split("."):
        try:
            partes.append(int(chunk))
        except Exception:
            partes.append(chunk)
    return tuple(partes)


# ==========================================================
# Lectura de estados
# ==========================================================
def _get_state_dict(session_key: str, storage_key: str) -> dict:
    data = st.session_state.get(session_key)
    if isinstance(data, dict) and data:
        return data
    try:
        loaded = cargar_estado(storage_key) or {}
        if isinstance(loaded, dict):
            st.session_state[session_key] = loaded
            return loaded
    except Exception:
        pass
    return {}


alcance_datos = _get_state_dict("alcance_datos", "alcance")
cronograma_datos = _get_state_dict("cronograma_datos", "cronograma")
presupuesto_obra_datos = _get_state_dict("presupuesto_obra_datos", "presupuesto_obra")

try:
    costos_indirectos_datos = cargar_estado("costos_indirectos") or {}
except Exception:
    costos_indirectos_datos = {}


# ==========================================================
# Lógica alineada con la hoja 4
# ==========================================================
def edge_key(origen, destino):
    return f"{origen}::{destino}"



def ensure_edge_meta(aristas: dict, origen, destino):
    clave = edge_key(origen, destino)
    meta = aristas.get(clave)
    if not isinstance(meta, dict):
        meta = {"tipo": "FC", "lag": 0}
        aristas[clave] = meta

    if meta.get("tipo") not in ("FC", "CC", "FF", "CF"):
        meta["tipo"] = "FC"

    try:
        meta["lag"] = int(meta.get("lag", 0))
    except Exception:
        meta["lag"] = 0

    return meta



def detectar_bucle(red: dict, terminales_ids: set):
    grafo = {}
    for origen, destinos in (red or {}).items():
        if origen not in terminales_ids:
            continue
        grafo[origen] = [d for d in (destinos or []) if d in terminales_ids]

    visitados, pila = set(), set()

    def dfs(nodo):
        visitados.add(nodo)
        pila.add(nodo)
        for vecino in grafo.get(nodo, []):
            if vecino not in visitados:
                if dfs(vecino):
                    return True
            elif vecino in pila:
                return True
        pila.remove(nodo)
        return False

    for nodo in grafo.keys():
        if nodo not in visitados and dfs(nodo):
            return True
    return False



def extraer_nodos_desde_edt(alcance: dict):
    lista_nodos = []
    terminales_ids = set()

    objetivos = alcance.get("objetivos") or []
    edt_data = alcance.get("edt_data") or {}

    for i, obj in enumerate(objetivos):
        oid = obj.get("id")
        cod_obj = f"{i + 1}"
        lista_nodos.append(
            {
                "id": oid,
                "codigo": cod_obj,
                "nombre": obj.get("texto", "Objetivo"),
                "nivel": 1,
                "padre_id": None,
                "es_terminal": False,
                "tipo_txt": "OBJETIVO",
            }
        )

        productos = edt_data.get(oid, []) if oid else []
        for j, prod in enumerate(productos):
            pid = prod.get("id")
            cod_prod = f"{cod_obj}.{j + 1}"
            nom_prod = prod.get("nombre", "Producto")
            actividades = prod.get("actividades", []) or []

            es_terminal_prod = len(actividades) == 0
            lista_nodos.append(
                {
                    "id": pid,
                    "codigo": cod_prod,
                    "nombre": nom_prod,
                    "nivel": 2,
                    "padre_id": oid,
                    "es_terminal": es_terminal_prod,
                    "tipo_txt": "PRODUCTO",
                }
            )
            if es_terminal_prod and pid:
                terminales_ids.add(pid)

            for k, act in enumerate(actividades):
                aid = act.get("id")
                cod_act = f"{cod_prod}.{k + 1}"
                nom_act = act.get("nombre", "Actividad")
                paquetes = act.get("paquetes", []) or []

                es_terminal_act = len(paquetes) == 0
                lista_nodos.append(
                    {
                        "id": aid,
                        "codigo": cod_act,
                        "nombre": nom_act,
                        "nivel": 3,
                        "padre_id": pid,
                        "es_terminal": es_terminal_act,
                        "tipo_txt": "ACTIVIDAD",
                    }
                )
                if es_terminal_act and aid:
                    terminales_ids.add(aid)

                for l, paquete in enumerate(paquetes):
                    pqid = paquete.get("id")
                    cod_paq = f"{cod_act}.{l + 1}"
                    lista_nodos.append(
                        {
                            "id": pqid,
                            "codigo": cod_paq,
                            "nombre": paquete.get("nombre", "Paquete"),
                            "nivel": 4,
                            "padre_id": aid,
                            "es_terminal": True,
                            "tipo_txt": "PAQUETE",
                        }
                    )
                    if pqid:
                        terminales_ids.add(pqid)

    if alcance.get("requiere_costos_indirectos", "No") == "Sí":
        costos_indirectos = alcance.get("otros_costos_indirectos_proyecto", []) or []
        if costos_indirectos:
            ci_group_id = "costos_indirectos_proyecto"
            ci_group_code = f"{len(objetivos) + 1}"
            ci_group_name = "COSTOS INDIRECTOS DEL PROYECTO"

            lista_nodos.append(
                {
                    "id": ci_group_id,
                    "codigo": ci_group_code,
                    "nombre": ci_group_name,
                    "nivel": 1,
                    "padre_id": None,
                    "es_terminal": False,
                    "tipo_txt": "OBJETIVO",
                }
            )

            for j, ci in enumerate(costos_indirectos):
                ci_id = ci.get("id")
                ci_nombre = ci.get("nombre", "Costo indirecto")
                ci_code = f"{ci_group_code}.{j + 1}"

                lista_nodos.append(
                    {
                        "id": ci_id,
                        "codigo": ci_code,
                        "nombre": ci_nombre,
                        "nivel": 2,
                        "padre_id": ci_group_id,
                        "es_terminal": True,
                        "tipo_txt": "PRODUCTO",
                    }
                )
                if ci_id:
                    terminales_ids.add(ci_id)

    dict_id = {n["id"]: n for n in lista_nodos if n.get("id") is not None}
    return lista_nodos, terminales_ids, dict_id



def calc_es_con_tipos(red: dict, aristas: dict, dur_func, terminales_ids: set):
    edges = []
    for origen, destinos in (red or {}).items():
        if origen not in terminales_ids:
            continue
        for destino in destinos or []:
            if destino not in terminales_ids:
                continue
            meta = ensure_edge_meta(aristas, origen, destino)
            tipo = meta.get("tipo", "FC")
            lag = int(meta.get("lag", 0))
            do = dur_func(origen)
            dd = dur_func(destino)

            if tipo == "FC":
                peso = do + lag
            elif tipo == "CC":
                peso = lag
            elif tipo == "FF":
                peso = do + lag - dd
            elif tipo == "CF":
                peso = lag - dd
            else:
                peso = do + lag

            edges.append((origen, destino, peso))

    indeg = {nid: 0 for nid in terminales_ids}
    adj = {nid: [] for nid in terminales_ids}
    for o, d, p in edges:
        adj[o].append((d, p))
        indeg[d] += 1

    cola = [nid for nid in terminales_ids if indeg[nid] == 0]
    topo = []
    while cola:
        cola.sort(key=lambda x: str(x))
        u = cola.pop(0)
        topo.append(u)
        for v, _ in adj.get(u, []):
            indeg[v] -= 1
            if indeg[v] == 0:
                cola.append(v)

    es = {nid: 0 for nid in terminales_ids}
    for nodo in topo:
        for destino, peso in adj.get(nodo, []):
            es[destino] = max(es.get(destino, 0), es.get(nodo, 0) + peso)

    return es



def _dur_pert(nid) -> int:
    rec = (cronograma_datos.get("pert", {}) or {}).get(str(nid), {}) or {}
    O = rec.get("O", None)
    M = rec.get("M", None)
    P = rec.get("P", None)
    if O is None or M is None or P is None:
        return 1
    try:
        val = (float(O) + 4.0 * float(M) + float(P)) / 6.0
        return max(1, int(math.ceil(val)))
    except Exception:
        return 1



def _periodos_activos_directos() -> Dict[str, Set[int]]:
    _lista_nodos, terminales_ids, _dict_id = extraer_nodos_desde_edt(alcance_datos)
    red = cronograma_datos.get("red_dependencias") or st.session_state.get("red_dependencias") or {}
    aristas = cronograma_datos.get("aristas", {}) or {}

    red_limpia = {}
    for origen, destinos in (red or {}).items():
        if origen not in terminales_ids:
            continue
        red_limpia[origen] = [d for d in (destinos or []) if d in terminales_ids]
    red = red_limpia

    if detectar_bucle(red, terminales_ids):
        return {}

    es = calc_es_con_tipos(red, aristas, _dur_pert, terminales_ids)
    ef = {nid: int(es.get(nid, 0) + _dur_pert(nid)) for nid in terminales_ids}

    salida: Dict[str, Set[int]] = {}
    for nid in terminales_ids:
        inicio = int(es.get(nid, 0)) + 1
        fin = int(ef.get(nid, 0))
        if fin < inicio:
            fin = inicio
        salida[str(nid)] = set(range(inicio, fin + 1))
    return salida


# ==========================================================
# Base de actividades
# ==========================================================
def _get_aiu_pct_global() -> float:
    config = presupuesto_obra_datos.get("configuracion") or {}
    return _safe_float(config.get("aiu_pct_global", 0.0), 0.0)


def _cargar_directos() -> pd.DataFrame:
    aiu_pct = _get_aiu_pct_global()
    directos_guardados = presupuesto_obra_datos.get("flujo_fondos_directos", []) or []
    items_presupuesto = presupuesto_obra_datos.get("items", {}) or {}

    cantidades_por_item = {}
    cantidades_por_node = {}

    for node_key, it in items_presupuesto.items():
        if not isinstance(it, dict):
            continue

        node_key = _safe_str(node_key)
        item_key = _safe_str(it.get("item_catalogo", it.get("ITEM", "")))
        cantidad = _safe_float(
            it.get("cant", it.get("CANT", it.get("CANT.", it.get("CANTIDAD", it.get("cantidad", 0.0))))),
            0.0,
        )

        if item_key:
            cantidades_por_item[item_key] = cantidad
        if node_key:
            cantidades_por_node[node_key] = cantidad

    rows: List[dict] = []
    for rec in directos_guardados:
        node_id = _safe_str(rec.get("node_id", ""))
        descripcion = _safe_str(rec.get("DESCRIPCIÓN", rec.get("DESCRIPCION", "")))
        item = _safe_str(rec.get("ITEM", ""))
        valor_base = _safe_float(rec.get("VALOR BASE", 0.0), 0.0)

        cantidad_total = 0.0
        if item in cantidades_por_item:
            cantidad_total = cantidades_por_item[item]
        elif node_id in cantidades_por_node:
            cantidad_total = cantidades_por_node[node_id]
        else:
            cantidad_total = _safe_float(
                rec.get("cant", rec.get("CANT", rec.get("CANT.", rec.get("CANTIDAD", rec.get("cantidad", 0.0))))),
                0.0,
            )

        if valor_base <= 0 or not descripcion:
            continue

        rows.append(
            {
                "ROW_ID": f"DIR|{node_id or item or descripcion}",
                "NODE_ID": node_id,
                "ITEM": item,
                "TIPO": "DIRECTO",
                "DESCRIPCIÓN": descripcion,
                "CANTIDAD TOTAL": round(cantidad_total, 4),
                "VALOR BASE": round(valor_base, 2),
                "AIU %": round(aiu_pct, 2),
                "VALOR CON AIU": round(valor_base * (1 + aiu_pct / 100.0), 2),
            }
        )

    return pd.DataFrame(rows)


def _cargar_indirectos(max_periodo_directos: int) -> pd.DataFrame:
    config = presupuesto_obra_datos.get("configuracion") or {}
    indirectos = (
        config.get("otros_costos_indirectos", [])
        or alcance_datos.get("otros_costos_indirectos_proyecto", [])
        or []
    )
    registros = costos_indirectos_datos.get("registros_por_oci") or {}

    rows: List[dict] = []
    for item in indirectos:
        oci_id = _safe_str(item.get("id", ""))
        if not oci_id:
            continue
        nombre = _safe_str(item.get("nombre", "Costo indirecto"))
        reg = registros.get(oci_id, {}) or {}
        valor_base = _safe_float(reg.get("valor_total_final", item.get("valor", 0.0)), 0.0)

        rows.append(
            {
                "ROW_ID": f"OCI|{oci_id}",
                "NODE_ID": oci_id,
                "ITEM": "",
                "TIPO": "INDIRECTO",
                "DESCRIPCIÓN": nombre,
                "CANTIDAD TOTAL": 1.0,
                "VALOR BASE": round(valor_base, 2),
                "AIU %": 0.0,
                "VALOR CON AIU": round(valor_base, 2),
                "MAX_PERIODO": max_periodo_directos,
            }
        )
    return pd.DataFrame(rows)


def _max_periodo_directos() -> int:
    activos_directos = _periodos_activos_directos()
    max_periodo = 0
    for periodos in activos_directos.values():
        if periodos:
            max_periodo = max(max_periodo, max(periodos))
    return max(max_periodo, 1)


def _cargar_base_actividades() -> pd.DataFrame:
    max_periodo = _max_periodo_directos()
    directos = _cargar_directos()
    indirectos = _cargar_indirectos(max_periodo)
    frames = [df for df in [directos, indirectos] if not df.empty]
    if not frames:
        return pd.DataFrame(columns=["ROW_ID", "NODE_ID", "ITEM", "TIPO", "DESCRIPCIÓN", "CANTIDAD TOTAL", "VALOR BASE", "AIU %", "VALOR CON AIU"])

    base = pd.concat(frames, ignore_index=True).reset_index(drop=True)
    base["_orden_item"] = base["ITEM"].apply(_key_codigo_natural)
    base["_orden_tipo"] = base["TIPO"].apply(lambda x: 0 if _safe_str(x) == "DIRECTO" else 1)
    base = base.sort_values(by=["_orden_tipo", "_orden_item", "DESCRIPCIÓN"], ascending=[True, True, True]).reset_index(drop=True)
    return base.drop(columns=["_orden_item", "_orden_tipo"], errors="ignore")


def _periodos_cronograma() -> List[str]:
    max_periodo = _max_periodo_directos()
    return [f"Periodo {i}" for i in range(1, max_periodo + 1)]


def _mapa_periodos_activos(base_df: pd.DataFrame, periodos: List[str]) -> Dict[str, Set[int]]:
    directos = _periodos_activos_directos()
    max_p = len(periodos)
    out: Dict[str, Set[int]] = {}
    for _, row in base_df.iterrows():
        row_id = _safe_str(row["ROW_ID"])
        if _safe_str(row["TIPO"]) == "DIRECTO":
            out[row_id] = set(directos.get(_safe_str(row["NODE_ID"]), set()))
        else:
            out[row_id] = set(range(1, max_p + 1))
    return out
# ==========================================================
# Programación y cálculos
# ==========================================================
def _estado_key() -> str:
    return "flujo_fondos"



def _cargar_programacion() -> dict:
    try:
        return cargar_estado(_estado_key()) or {}
    except Exception:
        return {}



def _guardar_programacion(data: dict):
    guardar_estado(_estado_key(), data)



def _normalizar_pct(v) -> float:
    x = _safe_float(v, 0.0)
    if x < 0:
        return 0.0
    if x > 100:
        return 100.0
    return x



def _armar_tabla_porcentajes(base_df: pd.DataFrame, periodos: List[str], mapa_activos: Dict[str, Set[int]], guardado: dict) -> pd.DataFrame:
    rows = []
    for _, row in base_df.iterrows():
        row_id = _safe_str(row["ROW_ID"])
        activos = mapa_activos.get(row_id, set())
        guardado_row = guardado.get(row_id, {}) if isinstance(guardado, dict) else {}
        rec = {
            "ROW_ID": row_id,
            "ITEM": _safe_str(row["ITEM"]),
            "TIPO": _safe_str(row["TIPO"]),
            "DESCRIPCIÓN": _safe_str(row["DESCRIPCIÓN"]),
            "VALOR BASE": round(_safe_float(row["VALOR BASE"]), 2),
            "AIU %": round(_safe_float(row["AIU %"]), 2),
            "VALOR CON AIU": round(_safe_float(row["VALOR CON AIU"]), 2),
        }

        total = 0.0
        for i, periodo in enumerate(periodos, start=1):
            col = f"{periodo} %"
            val = _normalizar_pct(guardado_row.get(col, 0.0))
            if i not in activos:
                val = 0.0
            rec[col] = val
            total += val

        rec["TOTAL %"] = round(total, 2)
        rows.append(rec)

    return pd.DataFrame(rows)



def _tabla_visual_habilitacion(df_pct: pd.DataFrame, periodos: List[str], mapa_activos: Dict[str, Set[int]]):
    visual = df_pct[["ITEM", "TIPO", "DESCRIPCIÓN"] + [f"{p} %" for p in periodos]].copy()
    visual = visual.rename(columns={f"{p} %": p for p in periodos})

    def _style_row(row):
        row_id = _safe_str(df_pct.loc[row.name, "ROW_ID"])
        activos = mapa_activos.get(row_id, set())
        estilos = []
        for col in visual.columns:
            if col in ("ITEM", "TIPO", "DESCRIPCIÓN"):
                estilos.append("")
            else:
                idx = periodos.index(col) + 1
                if idx in activos:
                    estilos.append("background-color: #e8f5e9; color: #1b5e20;")
                else:
                    estilos.append("background-color: #f1f3f4; color: #9aa0a6;")
        return estilos

    return visual.style.apply(_style_row, axis=1)



def _recalcular_bloqueos(df_pct: pd.DataFrame, periodos: List[str], mapa_activos: Dict[str, Set[int]]) -> pd.DataFrame:
    df = df_pct.copy()
    for idx in df.index:
        row_id = _safe_str(df.at[idx, "ROW_ID"])
        activos = mapa_activos.get(row_id, set())
        total = 0.0
        for i, periodo in enumerate(periodos, start=1):
            col = f"{periodo} %"
            val = _normalizar_pct(df.at[idx, col])
            if i not in activos:
                val = 0.0
            df.at[idx, col] = val
            total += val
        df.at[idx, "TOTAL %"] = round(total, 2)
    return df



def _guardar_desde_df(df_pct: pd.DataFrame, periodos: List[str], df_obra: pd.DataFrame | None = None, df_val: pd.DataFrame | None = None, df_resumen: pd.DataFrame | None = None):
    payload = {}
    for _, row in df_pct.iterrows():
        row_id = _safe_str(row["ROW_ID"])
        payload[row_id] = {f"{p} %": _safe_float(row[f"{p} %"]) for p in periodos}

    payload["__tablas__"] = {
        "df_programa_obra": [] if df_obra is None else df_obra.to_dict(orient="records"),
        "df_calculado": [] if df_val is None else df_val.to_dict(orient="records"),
        "df_resumen": [] if df_resumen is None else df_resumen.to_dict(orient="records"),
    }

    _guardar_programacion(payload)



def _aplicar_editor_a_tabla(df_pct: pd.DataFrame, row_id: str, payload_pct: dict, periodos: List[str], mapa_activos: Dict[str, Set[int]]) -> pd.DataFrame:
    df = df_pct.copy()
    if df.empty:
        return df

    mask = df["ROW_ID"].astype(str).eq(str(row_id))
    if not mask.any():
        return df

    idx = df.index[mask][0]
    activos = mapa_activos.get(str(row_id), set())

    for i, periodo in enumerate(periodos, start=1):
        col = f"{periodo} %"
        val = _normalizar_pct(payload_pct.get(col, 0.0))
        if i not in activos:
            val = 0.0
        df.at[idx, col] = val

    df = _recalcular_bloqueos(df, periodos, mapa_activos)
    return df



def _tabla_valores(df_pct: pd.DataFrame, periodos: List[str]) -> pd.DataFrame:
    out = []
    for _, row in df_pct.iterrows():
        valor_con_aiu = _safe_float(row["VALOR CON AIU"])
        rec = {
            "ITEM": _safe_str(row["ITEM"]),
            "TIPO": _safe_str(row["TIPO"]),
            "DESCRIPCIÓN": _safe_str(row["DESCRIPCIÓN"]),
            "VALOR CON AIU": round(valor_con_aiu, 2),
        }
        total_prog = 0.0
        for periodo in periodos:
            pct = _safe_float(row[f"{periodo} %"]) / 100.0
            val = valor_con_aiu * pct
            rec[f"{periodo} $"] = round(val, 2)
            total_prog += val
        rec["TOTAL PROGRAMADO"] = round(total_prog, 2)
        out.append(rec)
    return pd.DataFrame(out)



def _resumen(df_val: pd.DataFrame, periodos: List[str]):
    total_periodo = {}
    acumulado = {}
    pct_acum = {}
    total_general = _safe_float(df_val["VALOR CON AIU"].sum()) if not df_val.empty else 0.0
    running = 0.0
    for periodo in periodos:
        col = f"{periodo} $"
        total = _safe_float(df_val[col].sum()) if col in df_val.columns else 0.0
        running += total
        total_periodo[periodo] = round(total, 2)
        acumulado[periodo] = round(running, 2)
        pct_acum[periodo] = round((running / total_general) * 100.0, 2) if total_general > 0 else 0.0
    return total_periodo, acumulado, pct_acum


def _actividad_programada(row: pd.Series, periodos: List[str]) -> bool:
    total = 0.0
    for p in periodos:
        total += _safe_float(row.get(f"{p} %", 0.0))
    return round(total, 2) == 100.0


def _etiqueta_selector(row: pd.Series, periodos: List[str]) -> str:
    punto = "🟢" if _actividad_programada(row, periodos) else "🔴"
    item_txt = _safe_str(row["ITEM"])
    desc_txt = _safe_str(row["DESCRIPCIÓN"])
    tipo_txt = _safe_str(row["TIPO"])
    base = f"{item_txt} - {desc_txt} [{tipo_txt}]" if item_txt else f"{desc_txt} [{tipo_txt}]"
    return f"{punto} {base}"


# ==========================================================
# UI
# ==========================================================
st.set_page_config(page_title="FLUJO DE FONDOS", layout="wide")
st.title("FLUJO DE FONDOS")

tipo_presupuesto_proyecto = str(
    cronograma_datos.get("tipo_presupuesto_proyecto", "Obra") or "Obra"
).strip()

if tipo_presupuesto_proyecto != "Obra":
    st.warning("Este proyecto está clasificado como Consultoría. La hoja Flujo de Fondos aplica solo para proyectos de Obra.")
    st.stop()

base_df = _cargar_base_actividades()
if base_df.empty:
    st.warning("No hay actividades disponibles en el presupuesto.")
    st.stop()

periodos = _periodos_cronograma()
if not periodos:
    st.warning("No hay periodos disponibles en el cronograma.")
    st.stop()

mapa_activos = _mapa_periodos_activos(base_df, periodos)
guardado = _cargar_programacion()

df_pct_base = _armar_tabla_porcentajes(base_df, periodos, mapa_activos, guardado)

st.subheader("Programación de avance")
st.caption("Verde: periodo habilitado para la actividad. Gris: periodo fuera de programación; si se aplica un valor allí, vuelve a 0.")

st.dataframe(
    _tabla_visual_habilitacion(df_pct_base, periodos, mapa_activos),
    width="stretch",
    hide_index=True,
)

# Editor superior
st.markdown("### Editor de programación")

selector_df = df_pct_base.copy()
selector_df["_label_selector"] = selector_df.apply(lambda r: _etiqueta_selector(r, periodos), axis=1)
selector_df = selector_df.sort_values(by=["ITEM", "DESCRIPCIÓN"], ascending=[True, True]).reset_index(drop=True)

opciones_editor = selector_df["ROW_ID"].astype(str).tolist()
mapa_label_selector = {
    _safe_str(row["ROW_ID"]): _safe_str(row["_label_selector"])
    for _, row in selector_df.iterrows()
}

seleccion = st.selectbox(
    "Seleccione la actividad a programar",
    options=opciones_editor,
    index=0 if opciones_editor else None,
    format_func=lambda rid: mapa_label_selector.get(_safe_str(rid), _safe_str(rid)),
    key="flujo_fondos_editor_selector",
)

row_id_sel = _safe_str(seleccion)
row_sel_df = df_pct_base[df_pct_base["ROW_ID"].astype(str).eq(str(row_id_sel))].copy()

if not row_sel_df.empty:
    row_sel = row_sel_df.iloc[0]
    activos_sel = mapa_activos.get(str(row_id_sel), set())

    st.write(f"**Actividad:** {_safe_str(row_sel['DESCRIPCIÓN'])}")
    st.write(f"**Periodos habilitados:** {', '.join([str(i) for i in sorted(activos_sel)]) if activos_sel else 'Ninguno'}")

    editor_payload = {f"{p} %": [_safe_float(row_sel[f'{p} %'])] for p in periodos}
    editor_df = pd.DataFrame(editor_payload)

    editor_config = {}
    for i, p in enumerate(periodos, start=1):
        editor_config[f"{p} %"] = st.column_config.NumberColumn(
            f"{p} %",
            min_value=0.0,
            max_value=100.0,
            step=0.01,
            format="%.2f",
            disabled=(i not in activos_sel),
        )

    editor_df_edit = st.data_editor(
        editor_df,
        width="stretch",
        hide_index=True,
        num_rows="fixed",
        key="flujo_fondos_editor_superior",
        column_config=editor_config,
    )

    total_editor = 0.0
    if not editor_df_edit.empty:
        for p in periodos:
            total_editor += _safe_float(editor_df_edit.iloc[0].get(f"{p} %", 0.0))
    total_editor = round(total_editor, 2)
    st.write(f"**TOTAL % a cargar:** {total_editor:.2f}")

    if st.button("Aplicar a la tabla", width="stretch"):
        total_editor = round(float(total_editor), 2)

        if total_editor < 100.0:
            st.error("La suma de los porcentajes no puede ser menor a 100.00.")
        elif total_editor > 100.0:
            st.error("La suma de los porcentajes no puede ser mayor a 100.00.")
        else:
            payload_pct = editor_df_edit.iloc[0].to_dict() if not editor_df_edit.empty else {}
            df_pct_aplicado = _aplicar_editor_a_tabla(df_pct_base, str(row_id_sel), payload_pct, periodos, mapa_activos)
            df_obra_aplicado = df_pct_aplicado[["ITEM", "TIPO", "DESCRIPCIÓN"]].copy()

            cantidades_base_aplicado = {}
            for _, row_base in base_df.iterrows():
                cantidades_base_aplicado[_safe_str(row_base.get("ROW_ID", ""))] = _safe_float(row_base.get("CANTIDAD TOTAL", 0.0), 0.0)

            df_obra_aplicado["CANTIDAD TOTAL"] = df_pct_aplicado["ROW_ID"].apply(lambda rid: round(cantidades_base_aplicado.get(_safe_str(rid), 0.0), 4))

            for periodo in periodos:
                df_obra_aplicado[periodo] = (
                    df_obra_aplicado["CANTIDAD TOTAL"] * df_pct_aplicado[f"{periodo} %"].apply(lambda x: _safe_float(x, 0.0) / 100.0)
                ).round(4)

            df_val_aplicado = _tabla_valores(df_pct_aplicado, periodos)
            total_periodo_ap, acumulado_ap, pct_acum_ap = _resumen(df_val_aplicado, periodos)
            df_resumen_aplicado = pd.DataFrame(
                [
                    {"CONCEPTO": "TOTAL POR PERIODO", **{p: total_periodo_ap[p] for p in periodos}},
                    {"CONCEPTO": "ACUMULADO", **{p: acumulado_ap[p] for p in periodos}},
                    {"CONCEPTO": "% ACUMULADO", **{p: pct_acum_ap[p] for p in periodos}},
                ]
            )

            _guardar_desde_df(df_pct_aplicado, periodos, df_obra_aplicado, df_val_aplicado, df_resumen_aplicado)
            st.success("Actividad aplicada a la tabla correctamente.")
            st.rerun()

column_order_pct = [
    "ITEM",
    "TIPO",
    "DESCRIPCIÓN",
    "VALOR BASE",
    "AIU %",
    "VALOR CON AIU",
] + [f"{p} %" for p in periodos] + ["TOTAL %"]

column_config_pct = {
    "ITEM": st.column_config.TextColumn("ITEM", disabled=True),
    "TIPO": st.column_config.TextColumn("TIPO", disabled=True),
    "DESCRIPCIÓN": st.column_config.TextColumn("DESCRIPCIÓN", disabled=True),
    "VALOR BASE": st.column_config.NumberColumn("VALOR BASE", format="$ %.2f", disabled=True),
    "AIU %": st.column_config.NumberColumn("AIU %", format="%.2f", disabled=True),
    "VALOR CON AIU": st.column_config.NumberColumn("VALOR CON AIU", format="$ %.2f", disabled=True),
    "TOTAL %": st.column_config.NumberColumn("TOTAL %", format="%.2f", disabled=True),
}
for p in periodos:
    column_config_pct[f"{p} %"] = st.column_config.NumberColumn(
        f"{p} %", min_value=0.0, max_value=100.0, step=0.01, format="%.2f", disabled=True
    )

st.markdown("### Tabla general de programación")
st.data_editor(
    df_pct_base,
    width="stretch",
    hide_index=True,
    num_rows="fixed",
    key="flujo_fondos_pct_tabla_general",
    column_order=column_order_pct,
    column_config=column_config_pct,
    disabled=list(df_pct_base.columns),
)

df_pct = _recalcular_bloqueos(df_pct_base.copy(), periodos, mapa_activos)
invalidas = df_pct[~df_pct["TOTAL %"].round(2).eq(100.0)]

if invalidas.empty:
    st.success("Todas las actividades suman 100%.")
else:
    st.warning("Hay actividades cuya programación no suma 100%.")

if not invalidas.empty:
    st.warning("Los periodos no activos se fuerzan a 0. La suma por actividad debe ser 100%.")

st.subheader("Programa de obra")

df_obra = df_pct[["ITEM", "TIPO", "DESCRIPCIÓN"]].copy()

cantidades_base = {}
for _, row in base_df.iterrows():
    cantidades_base[_safe_str(row.get("ROW_ID", ""))] = _safe_float(row.get("CANTIDAD TOTAL", 0.0), 0.0)

df_obra["CANTIDAD TOTAL"] = df_pct["ROW_ID"].apply(lambda rid: round(cantidades_base.get(_safe_str(rid), 0.0), 4))

for periodo in periodos:
    df_obra[periodo] = (
        df_obra["CANTIDAD TOTAL"] * df_pct[f"{periodo} %"].apply(lambda x: _safe_float(x, 0.0) / 100.0)
    ).round(4)

column_order_obra = ["ITEM", "TIPO", "DESCRIPCIÓN", "CANTIDAD TOTAL"] + periodos
column_config_obra = {
    "ITEM": st.column_config.TextColumn("ITEM", disabled=True),
    "TIPO": st.column_config.TextColumn("TIPO", disabled=True),
    "DESCRIPCIÓN": st.column_config.TextColumn("DESCRIPCIÓN", disabled=True),
    "CANTIDAD TOTAL": st.column_config.NumberColumn("CANTIDAD TOTAL", format="%.4f", disabled=True),
}
for periodo in periodos:
    column_config_obra[periodo] = st.column_config.NumberColumn(periodo, format="%.4f", disabled=True)

st.data_editor(
    df_obra,
    width="stretch",
    hide_index=True,
    num_rows="fixed",
    key="flujo_fondos_programa_obra",
    column_order=column_order_obra,
    column_config=column_config_obra,
    disabled=list(df_obra.columns),
)

if st.button("Guardar y recalcular", width="stretch"):
    _guardar_desde_df(df_pct, periodos, df_obra, df_val, df_resumen)
    st.success("Programación guardada y recalculada correctamente.")
    st.rerun()

st.subheader("Programa de iversiones")
df_val = _tabla_valores(df_pct, periodos)
column_order_val = ["ITEM", "TIPO", "DESCRIPCIÓN", "VALOR CON AIU"] + [f"{p} $" for p in periodos] + ["TOTAL PROGRAMADO"]
column_config_val = {
    "ITEM": st.column_config.TextColumn("ITEM", disabled=True),
    "TIPO": st.column_config.TextColumn("TIPO", disabled=True),
    "DESCRIPCIÓN": st.column_config.TextColumn("DESCRIPCIÓN", disabled=True),
    "VALOR CON AIU": st.column_config.NumberColumn("VALOR CON AIU", format="$ %.2f", disabled=True),
    "TOTAL PROGRAMADO": st.column_config.NumberColumn("TOTAL PROGRAMADO", format="$ %.2f", disabled=True),
}
for p in periodos:
    column_config_val[f"{p} $"] = st.column_config.NumberColumn(f"{p} $", format="$ %.2f", disabled=True)

st.data_editor(
    df_val,
    width="stretch",
    hide_index=True,
    num_rows="fixed",
    key="flujo_fondos_valores",
    column_order=column_order_val,
    column_config=column_config_val,
    disabled=list(df_val.columns),
)

st.subheader("Flujo de fondos")
total_periodo, acumulado, pct_acum = _resumen(df_val, periodos)
df_resumen = pd.DataFrame(
    [
        {"CONCEPTO": "TOTAL POR PERIODO", **{p: total_periodo[p] for p in periodos}},
        {"CONCEPTO": "ACUMULADO", **{p: acumulado[p] for p in periodos}},
        {"CONCEPTO": "% ACUMULADO", **{p: pct_acum[p] for p in periodos}},
    ]
)
column_config_res = {"CONCEPTO": st.column_config.TextColumn("CONCEPTO", disabled=True)}
for p in periodos:
    column_config_res[p] = st.column_config.NumberColumn(p, format="%.2f", disabled=True)

st.data_editor(
    df_resumen,
    width="stretch",
    hide_index=True,
    num_rows="fixed",
    key="flujo_fondos_resumen",
    column_config=column_config_res,
    disabled=list(df_resumen.columns),
)

st.markdown("<div style='height: 112px;'></div>", unsafe_allow_html=True)

acumulado_previo = []
ejecutado_periodo = []

acumulado_corriente = 0
for p in periodos:
    acumulado_previo.append(acumulado_corriente)
    valor = total_periodo[p]
    ejecutado_periodo.append(valor)
    acumulado_corriente += valor

cantidad_periodos = len(periodos)

if cantidad_periodos <= 12:
    mostrar_texto_linea = True
    tam_texto_linea = 14
elif cantidad_periodos <= 24:
    mostrar_texto_linea = True
    tam_texto_linea = 10
else:
    mostrar_texto_linea = False
    tam_texto_linea = 10

datos_acumulado_previo = acumulado_previo

datos_ejecutado_periodo = [
    {
        "value": v,
        "label": {
            "show": v != 0,
            "formatter": f"{v:,.0f}",
            "position": "inside",
            "fontSize": 14,
            "fontWeight": "bold",
            "color": "#1f3b73",
        },
    }
    for v in ejecutado_periodo
]

if mostrar_texto_linea:
    datos_linea = [
        {
            "value": acumulado[p],
            "label": {
                "show": True,
                "formatter": f"{acumulado[p]:,.0f}",
                "position": "top",
                "distance": 14,
                "fontSize": tam_texto_linea,
                "fontWeight": "bold",
                "color": "#1f3b73",
            },
        }
        for p in periodos
    ]
else:
    datos_linea = [acumulado[p] for p in periodos]

opciones_flujo = {
    "animation": False,
    "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
    "legend": {"top": 0},
    "grid": {"left": 80, "right": 40, "top": 55, "bottom": 70},
    "xAxis": {
        "type": "category",
        "data": periodos,
        "name": "Periodo",
        "nameLocation": "middle",
        "nameGap": 45,
        "nameTextStyle": {"fontWeight": "bold", "fontSize": 14},
        "axisLabel": {"interval": 0},
    },
    "yAxis": {
        "type": "value",
        "name": "Valor",
        "nameLocation": "middle",
        "nameGap": 60,
        "nameTextStyle": {"fontWeight": "bold", "fontSize": 14},
    },
    "series": [
        {
            "name": "Acumulado previo",
            "type": "bar",
            "stack": "total",
            "data": datos_acumulado_previo,
            "barMaxWidth": 36,
            "barGap": "-100%",
            "itemStyle": {
                "color": {
                    "type": "linear",
                    "x": 0,
                    "y": 0,
                    "x2": 1,
                    "y2": 0,
                    "colorStops": [
                        {"offset": 0, "color": "#eef4fb"},
                        {"offset": 0.45, "color": "#d4e1f2"},
                        {"offset": 1, "color": "#aabed8"},
                    ],
                },
                "borderColor": "#8ea8c7",
                "borderWidth": 2,
                "shadowBlur": 18,
                "shadowColor": "rgba(0,0,0,0.22)",
                "shadowOffsetX": 6,
                "shadowOffsetY": 8,
                "opacity": 0.98,
            },
            "emphasis": {"disabled": True},
        },
        {
            "name": "Ejecutado en el periodo",
            "type": "bar",
            "stack": "total",
            "data": datos_ejecutado_periodo,
            "barMaxWidth": 36,
            "itemStyle": {
                "color": {
                    "type": "linear",
                    "x": 0,
                    "y": 0,
                    "x2": 1,
                    "y2": 0,
                    "colorStops": [
                        {"offset": 0, "color": "#7aa6d8"},
                        {"offset": 0.45, "color": "#4f81bd"},
                        {"offset": 1, "color": "#2f5f98"},
                    ],
                },
                "borderColor": "#244d80",
                "borderWidth": 2,
                "shadowBlur": 22,
                "shadowColor": "rgba(0,0,0,0.28)",
                "shadowOffsetX": 7,
                "shadowOffsetY": 9,
                "opacity": 0.99,
            },
            "emphasis": {"disabled": True},
        },
        {
            "name": "Acumulado",
            "type": "line",
            "data": datos_linea,
            "smooth": False,
            "symbol": "circle",
            "symbolSize": 11,
            "lineStyle": {"color": "#d62828", "width": 4},
            "itemStyle": {
                "color": "#d62828",
                "borderColor": "#ffffff",
                "borderWidth": 1.5,
            },
            "areaStyle": {"color": "rgba(214,40,40,0.12)"},
            "z": 10,
        },
    ],
}

st_echarts(
    options=opciones_flujo,
    height="460px",
    width="100%",
    key="flujo_fondos_echarts",
)
