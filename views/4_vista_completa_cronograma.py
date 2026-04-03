import calendar
import json
import math
from datetime import date, timedelta
from string import Template

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


def key_codigo_natural(codigo: str):
    partes = str(codigo).split(".")
    return tuple(int(p) if p.isdigit() else 0 for p in partes)


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
        for destino in (destinos or []):
            if destino not in terminales_ids:
                continue
            meta = ensure_edge_meta(aristas, origen, destino)
            tipo = meta["tipo"]
            lag = int(meta["lag"])
            dur_origen = dur_func(origen)
            dur_destino = dur_func(destino)

            if tipo == "FC":
                peso = dur_origen + lag
            elif tipo == "CC":
                peso = lag
            elif tipo == "FF":
                peso = dur_origen + lag - dur_destino
            else:
                peso = lag - dur_destino

            edges.append((origen, destino, peso))

    indeg = {t: 0 for t in terminales_ids}
    adj = {t: [] for t in terminales_ids}
    for origen, destino, peso in edges:
        adj[origen].append((destino, peso))
        indeg[destino] += 1

    cola = [n for n in terminales_ids if indeg.get(n, 0) == 0]
    topo = []
    while cola:
        nodo = cola.pop(0)
        topo.append(nodo)
        for destino, _peso in adj.get(nodo, []):
            indeg[destino] -= 1
            if indeg[destino] == 0:
                cola.append(destino)

    es = {t: 0 for t in terminales_ids}
    for nodo in topo:
        for destino, peso in adj.get(nodo, []):
            es[destino] = max(es.get(destino, 0), es.get(nodo, 0) + peso)

    return es


def escapar_html(texto):
    return (
        str(texto)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


alcance = st.session_state.get("alcance_datos", {}) or {}
cronograma_datos = st.session_state.get("cronograma_datos", {}) or {}

cronograma_datos.setdefault("pert", {})
cronograma_datos.setdefault("mostrar_hoy", False)
cronograma_datos.setdefault("hoy_offset", 0)
cronograma_datos.setdefault("hitos", [])

escala = cronograma_datos.get("escala_tiempo", "DÍAS")
aristas = cronograma_datos.get("aristas", {}) or {}
cronograma_datos["aristas"] = aristas

red = cronograma_datos.get("red_dependencias") or st.session_state.get("red_dependencias") or {}
lista_nodos, terminales_ids, dict_id = extraer_nodos_desde_edt(alcance)

if not lista_nodos or not terminales_ids:
    st.warning("⚠️ No hay EDT/terminales definidos. Primero completa '1. Alcance' y luego '2. Cronograma'.")
    st.stop()

red = {
    origen: [d for d in (destinos or []) if d in terminales_ids]
    for origen, destinos in (red or {}).items()
    if origen in terminales_ids
}

if detectar_bucle(red, terminales_ids):
    st.error("🚨 La red tiene un bucle (dependencia circular). Corrige en '2. Cronograma'.")
    st.stop()


def dur_pert(nid):
    rec = (cronograma_datos.get("pert", {}) or {}).get(str(nid), {}) or {}
    o = rec.get("O", None)
    m = rec.get("M", None)
    p = rec.get("P", None)

    if o is None or m is None or p is None:
        return 1

    try:
        val = (float(o) + 4.0 * float(m) + float(p)) / 6.0
        return max(1, int(math.ceil(val)))
    except Exception:
        return 1


mostrar_incertidumbre = False

preds_map = {}
for origen, destinos in red.items():
    for destino in destinos:
        preds_map.setdefault(destino, []).append(origen)


def _fmt2(valor):
    if valor is None:
        return ""
    if isinstance(valor, str) and valor.strip() == "":
        return ""
    try:
        return f"{float(valor):.2f}"
    except Exception:
        return str(valor)


audit_rows = []
for nodo in sorted(lista_nodos, key=lambda x: key_codigo_natural(x["codigo"])):
    nid = nodo.get("id")
    codigo = nodo.get("codigo", "")
    nombre = nodo.get("nombre", "")
    es_padre = not bool(nodo.get("es_terminal", False))

    if es_padre or nid is None:
        row = {
            "CÓDIGO": codigo,
            "NOMBRE": nombre,
            "O": "—",
            "M": "—",
            "P": "—",
            f"DURACIÓN PERT ({escala})": "—",
            "PREDECESORAS": "",
            "_parent": True,
        }
        if mostrar_incertidumbre:
            row["σ"] = "—"
            row["Varianza"] = "—"
        audit_rows.append(row)
        continue

    dur = dur_pert(nid)
    rec_pert = (cronograma_datos.get("pert", {}) or {}).get(str(nid), {}) or {}
    o = rec_pert.get("O", "")
    m = rec_pert.get("M", "")
    p = rec_pert.get("P", "")

    pred_ids = preds_map.get(nid, []) or []
    pred_ids = sorted(pred_ids, key=lambda x: key_codigo_natural(dict_id.get(x, {}).get("codigo", "0")))
    pred_str = ", ".join([dict_id.get(pid, {}).get("codigo", "") for pid in pred_ids if dict_id.get(pid)])

    row = {
        "CÓDIGO": codigo,
        "NOMBRE": nombre,
        "O": _fmt2(o),
        "M": _fmt2(m),
        "P": _fmt2(p),
        f"DURACIÓN PERT ({escala})": dur,
        "PREDECESORAS": pred_str,
        "_parent": False,
    }

    if mostrar_incertidumbre:
        sigma_fmt = ""
        var_fmt = ""
        try:
            if o not in [None, ""] and p not in [None, ""]:
                sigma = (float(p) - float(o)) / 6.0
                varianza = sigma * sigma
                sigma_fmt = f"{sigma:.2f}"
                var_fmt = f"{varianza:.2f}"
        except Exception:
            sigma_fmt = ""
            var_fmt = ""
        row["σ"] = sigma_fmt
        row["Varianza"] = var_fmt

    audit_rows.append(row)

df_master = pd.DataFrame(audit_rows)
_ = df_master.drop(columns=["_parent"])

fecha_inicio = cronograma_datos.get("fecha_inicio", date.today())
mostrar_hoy = bool(cronograma_datos.get("mostrar_hoy", False))
hoy_offset = int(cronograma_datos.get("hoy_offset", 0))
modo_calendario = bool(cronograma_datos.get("modo_calendario", False))

cronograma_datos["mostrar_hoy"] = bool(mostrar_hoy)
cronograma_datos["hoy_offset"] = int(hoy_offset)
cronograma_datos["modo_calendario"] = bool(modo_calendario)
cronograma_datos["fecha_inicio"] = fecha_inicio

st.markdown("## CRONOGRAMA DE ACTIVIDADES")
nombre_proyecto = st.session_state.get("alcance_datos", {}).get("nombre_proyecto", "").strip()
if nombre_proyecto:
    st.markdown(f"### {nombre_proyecto}")

vista_gantt = "Completo"
cronograma_datos["vista_gantt"] = vista_gantt
st.session_state["cronograma_datos"] = cronograma_datos

es_terminales = calc_es_con_tipos(red, aristas, dur_pert, terminales_ids)
ef_terminales = {nid: int(es_terminales.get(nid, 0) + dur_pert(nid)) for nid in terminales_ids}

hijos = {}
for nodo in lista_nodos:
    padre_id = nodo.get("padre_id")
    if padre_id is None or nodo.get("id") is None:
        continue
    hijos.setdefault(padre_id, []).append(nodo["id"])

cache_range = {}


def rango_nodo(nid):
    if nid in cache_range:
        return cache_range[nid]

    nodo = dict_id.get(nid)
    if not nodo:
        cache_range[nid] = None
        return None

    if nodo["es_terminal"]:
        inicio = int(es_terminales.get(nid, 0))
        fin = int(ef_terminales.get(nid, inicio + 1))
        cache_range[nid] = (inicio, fin)
        return cache_range[nid]

    rangos = []
    for child_id in hijos.get(nid, []):
        rr = rango_nodo(child_id)
        if rr:
            rangos.append(rr)

    if not rangos:
        cache_range[nid] = None
        return None

    inicio = min(r[0] for r in rangos)
    fin = max(r[1] for r in rangos)
    cache_range[nid] = (inicio, fin)
    return cache_range[nid]


preds_terminales = {nid: [] for nid in terminales_ids}
for origen, destinos in red.items():
    for destino in (destinos or []):
        if destino in terminales_ids and origen in terminales_ids:
            preds_terminales.setdefault(destino, []).append(origen)

rows = []
for nodo in lista_nodos:
    nid = nodo.get("id")
    if nid is None:
        continue

    es_terminal = bool(nodo.get("es_terminal"))
    nivel = int(nodo.get("nivel", 99))

    if (not es_terminal) and (nivel not in (1, 2, 3)):
        continue

    rr = rango_nodo(nid)
    if rr is None:
        continue
    inicio, fin = rr
    dur = max(1, fin - inicio)

    pred_str = ""
    if es_terminal:
        pred_ids = preds_terminales.get(nid, []) or []
        pred_ids = sorted(pred_ids, key=lambda x: key_codigo_natural(dict_id.get(x, {}).get("codigo", "0")))
        pred_str = ", ".join([dict_id.get(pid, {}).get("codigo", "") for pid in pred_ids if dict_id.get(pid)])

    rows.append(
        {
            "id": nid,
            "nivel": nivel,
            "codigo": nodo.get("codigo", ""),
            "nombre": nodo.get("nombre", ""),
            "is_parent": not es_terminal,
            "is_terminal": es_terminal,
            "ES": int(inicio),
            "EF": int(fin),
            "dur": int(dur),
            "predecesoras": pred_str,
        }
    )

dfp = pd.DataFrame(rows)

if dfp.empty:
    st.info("No hay datos suficientes para construir el Gantt.")
else:
    dfp["cod_key"] = dfp["codigo"].apply(key_codigo_natural)
    dfp["parent_rank"] = dfp["is_parent"].apply(lambda x: 0 if x else 1)
    dfp["grp_key"] = dfp["codigo"].astype(str).apply(lambda c: key_codigo_natural(c)[0] if len(key_codigo_natural(c)) else 0)
    dfp = dfp.sort_values(
        by=["grp_key", "cod_key", "parent_rank", "ES", "nivel"],
        ascending=[True, True, True, True, True],
    ).reset_index(drop=True)

    max_x = int(dfp["EF"].max()) if len(dfp) else 10
    hitos_all = cronograma_datos.get("hitos", []) or []

    if vista_gantt == "Completo":
        dfp_vista = dfp.copy()
    elif vista_gantt == "Solo resumen":
        dfp_vista = dfp[dfp["is_parent"].astype(bool)].copy()
    else:
        ids_con_hitos = {str(h.get("id")) for h in hitos_all}
        dfp_vista = dfp[dfp["id"].astype(str).isin(ids_con_hitos)].copy()

    def add_months(d: date, months: int) -> date:
        year = d.year + (d.month - 1 + months) // 12
        month = (d.month - 1 + months) % 12 + 1
        last_day = calendar.monthrange(year, month)[1]
        day = min(d.day, last_day)
        return date(year, month, day)

    def add_years(d: date, years: int) -> date:
        year = d.year + years
        last_day = calendar.monthrange(year, d.month)[1]
        day = min(d.day, last_day)
        return date(year, d.month, day)

    def fmt_fecha(d: date) -> str:
        return f"{d.day:02d}/{d.month:02d}"

    def x_label(t: int) -> str:
        if not modo_calendario:
            return str(int(t))

        esc = str(escala).upper().strip()

        if esc == "DÍAS":
            return fmt_fecha(fecha_inicio + timedelta(days=int(t)))
        if esc == "SEMANAS":
            return fmt_fecha(fecha_inicio + timedelta(days=int(t) * 7))
        if esc == "MESES":
            return fmt_fecha(add_months(fecha_inicio, int(t)))
        if esc == "AÑOS":
            return fmt_fecha(add_years(fecha_inicio, int(t)))

        return fmt_fecha(fecha_inicio + timedelta(days=int(t)))

    row_h = 28
    export_height = max(2200, int(len(dfp_vista) * row_h) + 120)
    left_w = 1180
    right_w = 900

    total_periodos = max(1, int(max_x) + 1)
    px_per_unit = (right_w - 40) / total_periodos
    gantt_w = right_w

    esc_u = str(escala).upper().strip()
    if not modo_calendario:
        if px_per_unit >= 35:
            tick_step = 1
        elif px_per_unit >= 22:
            tick_step = 2
        elif px_per_unit >= 14:
            tick_step = 5
        else:
            tick_step = 10
    else:
        if esc_u == "DÍAS":
            if px_per_unit >= 55:
                tick_step = 1
            elif px_per_unit >= 35:
                tick_step = 2
            elif px_per_unit >= 25:
                tick_step = 5
            else:
                tick_step = 7
        else:
            tick_step = 1

    ticks = [(t, x_label(t)) for t in range(0, max_x + 1, tick_step)]

    left_rows_html = []
    gantt_rows_html = []

    for _, r in dfp_vista.iterrows():
        codigo = escapar_html(r["codigo"])
        nombre = escapar_html(r["nombre"])
        dur = escapar_html(r["dur"])

        es_num = int(r["ES"])
        ef_num = int(r["EF"])
        es_txt = escapar_html(es_num)
        ef_txt = escapar_html(ef_num)

        if modo_calendario:
            if str(escala).upper().strip() == "DÍAS":
                es_label = escapar_html(fmt_fecha(fecha_inicio + timedelta(days=es_num)))
                ef_label = escapar_html(fmt_fecha(fecha_inicio + timedelta(days=ef_num)))
            else:
                es_label = escapar_html(x_label(es_num))
                ef_label = escapar_html(x_label(ef_num))
        else:
            es_label = es_txt
            ef_label = ef_txt

        indent = (int(r["nivel"]) - 1) * 14
        is_parent = bool(r["is_parent"])
        row_class = "row parent" if is_parent else "row task"
        rid = escapar_html(str(r["id"]))
        term_val = "0" if is_parent else "1"

        hitos = cronograma_datos.get("hitos", []) or []
        hitos_de_esta = [h for h in hitos if str(h.get("id")) == str(r["id"])]
        hitos_txt = escapar_html("; ".join([f'{h["nombre"]} ({h["tipo"]})' for h in hitos_de_esta]))

        left_rows_html.append(
            f"""
            <div class='{row_class}' data-id='{rid}' data-es='{es_num}' data-ef='{ef_num}' data-term='{term_val}' style='height:{row_h}px'>
              <div class='cell code'>{codigo}</div>
              <div class='cell name' style='padding-left:{indent}px'><span class='nm' data-title='{nombre}'>{nombre}</span></div>
              <div class='cell dur'>{dur}</div>
              <div class='cell es'>{es_label}</div>
              <div class='cell ef'>{ef_label}</div>
              <div class='cell hito' data-title='{hitos_txt}'>{hitos_txt}</div>
            </div>
            """
        )

        x = int(r["ES"]) * px_per_unit
        w = max(1, int(r["dur"]) * px_per_unit)
        bar_class = "bar parentbar" if is_parent else "bar taskbar"

        gantt_rows_html.append(
            f"""
            <div class='{row_class}' data-id='{rid}' data-es='{es_num}' data-ef='{ef_num}' data-term='{term_val}' style='height:{row_h}px'>
              <div class='barwrap'>
                <div class='{bar_class}' style='left:{x}px;width:{w}px'></div>
              </div>
            </div>
            """
        )

    today_line = ""
    if mostrar_hoy:
        xh = int(hoy_offset) * px_per_unit
        today_line = f"<div class='today' style='left:{xh}px'></div><div class='todaylabel' style='left:{xh + 6}px'>HOY</div>"

    tick_html = []
    for t, lab in ticks:
        x = t * px_per_unit
        tick_html.append(f"<div class='tick' style='left:{x}px'>{escapar_html(lab)}</div>")
        tick_html.append(f"<div class='vline' style='left:{x}px'></div>")
    ticks_html = "".join(tick_html)

    edges = []
    for origen, destinos in (red or {}).items():
        if origen not in terminales_ids:
            continue
        for destino in (destinos or []):
            if destino not in terminales_ids:
                continue
            meta = ensure_edge_meta(aristas, origen, destino)
            edges.append({"o": str(origen), "d": str(destino), "tipo": meta.get("tipo", "FC")})

    edges_json = json.dumps(edges, ensure_ascii=False)
    hitos_json = json.dumps(cronograma_datos.get("hitos", []) or [], ensure_ascii=False)

    header_html = """
    <div class='header'>
      <div class='hcell h-code'>COD</div>
      <div class='hcell h-name'>NOMBRE</div>
      <div class='hcell h-dur'>DUR</div>
      <div class='hcell h-es'>ES</div>
      <div class='hcell h-ef'>EF</div>
      <div class='hcell h-hito'>HITOS</div>
    </div>
    """

    html_t = Template("""
    <style>
      .proj-wrap {
        display:flex;
        gap:12px;
        position:relative;
        width:calc(${LEFT_W}px + ${GANTT_W}px + 12px);
      }
      .left-pane{
        width:${LEFT_W}px;
        flex:0 0 ${LEFT_W}px;
        border:1px solid #e5e7eb;
        border-radius:10px;
        overflow:hidden;
        background:#fff;
      }
      .right-pane{
        width:${GANTT_W}px;
        flex:0 0 ${GANTT_W}px;
        border:1px solid #e5e7eb;
        border-radius:10px;
        overflow:hidden;
        background:#fff;
      }
      .proj-wrap, .left-pane, .right-pane, .header, .row, .cell, .gantt-head, .gantt-body{
        font-family: system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
        font-size: 12px;
      }
      .header{
        display:grid;
        grid-template-columns: 60px 830px 60px 50px 50px 130px;
        align-items:center;
        height:34px;
        box-sizing:border-box;
        background:#0B3D2E;
        color:#fff;
        font-weight:800;
        font-size:12px;
        border-bottom:1px solid #e5e7eb;
      }
      .hcell{ padding:8px 10px; border-right:1px solid rgba(255,255,255,0.18); }
      .h-dur, .h-es, .h-ef{ min-width:0; text-align:center; }

      .body{ height:${EXPORT_H}px; overflow:auto; }
      .row {
        display:grid;
        grid-template-columns: 60px 830px 60px 50px 50px 130px;
        align-items:center;
        border-bottom:1px solid #f3f4f6;
        font-size:12px;
        width:100%;
        position:relative;
      }
      .row.parent{ background:#E5E7EB; font-weight:800; cursor:default; }
      .cell{
        padding:0 8px;
        white-space:nowrap;
        overflow:hidden;
        text-overflow:ellipsis;
        box-sizing:border-box;
      }
      .cell.dur, .cell.es, .cell.ef{
        text-align:center;
        display:flex;
        align-items:center;
        justify-content:center;
        padding-left:0;
        padding-right:0;
      }
      .nm{
        display:block;
        width:100%;
        white-space:nowrap;
        overflow:hidden;
        text-overflow:ellipsis;
      }

      .capture-bar{
        display:flex;
        justify-content:flex-end;
        margin-bottom:10px;
      }
      .capture-btn{
        background:#0B3D2E;
        color:#fff;
        border:none;
        border-radius:8px;
        padding:10px 14px;
        font-size:12px;
        font-weight:700;
        cursor:pointer;
      }
      .capture-btn:hover{ opacity:.92; }

      .gantt-head{
        position:relative;
        height:34px;
        background:#f8fafc;
        border-bottom:1px solid #e5e7eb;
        overflow:hidden;
      }
      .gantt-head-inner{ position:absolute; left:0; top:0; right:0; bottom:0; }
      .tick{
        position:absolute;
        top:6px;
        font-size:11px;
        color:#0B3D2E;
        font-weight:800;
      }
      .vline{
        position:absolute;
        top:0;
        bottom:0;
        width:1px;
        background:#eef2f7;
      }

      .gantt-body{
        position:relative;
        height:${EXPORT_H}px;
        overflow-y:scroll;
        overflow-x:scroll;
      }
      .gantt-inner{ position:relative; width:${GANTT_W}px; }
      .barwrap{ position:relative; width:100%; height:${ROW_H}px; overflow:visible; }
      .bar{
        position:absolute;
        top:6px;
        height:${BAR_H}px;
        border-radius:6px;
        z-index:3;
      }
      .taskbar{ background:rgba(11,61,46,0.75); }
      .parentbar{ background:rgba(148,163,184,0.75); }

      .today{
        position:absolute;
        top:0;
        bottom:0;
        width:2px;
        background:#ef4444;
        z-index:5;
      }
      .todaylabel{
        position:absolute;
        top:6px;
        font-size:11px;
        font-weight:800;
        color:#ef4444;
        z-index:6;
      }

      .overlay{
        position:absolute;
        left:0;
        top:0;
        width:${GANTT_W}px;
        height:${OVER_H}px;
        pointer-events:none;
        z-index:7;
      }
      .edge{
        stroke: rgba(245, 158, 11, 0.95);
        stroke-width: 4.5;
        fill: none;
      }
      .mile{
        fill: rgba(239, 68, 68, 0.95);
        stroke: rgba(127, 29, 29, 0.85);
        stroke-width: 1.2;
      }

      #tip{
        position:absolute;
        display:none;
        background:rgba(15, 23, 42, 0.95);
        color:#fff;
        padding:6px 8px;
        border-radius:6px;
        font-size:12px;
        font-weight:600;
        max-width:520px;
        z-index:999999;
        pointer-events:none;
        box-shadow:0 8px 20px rgba(0,0,0,0.25);
        white-space:normal;
      }
    </style>

    <script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>

    <div class='capture-bar'>
      <button class='capture-btn' onclick='captureCronograma()'>Descargar imagen</button>
    </div>

    <div class='proj-wrap' id='captureArea'>
      <div id="tip"></div>

      <div class='left-pane'>
        ${HEADER_HTML}
        <div class='body' id='leftBody'>
          $LEFT_ROWS
        </div>
      </div>

      <div class='right-pane'>
        <div class='gantt-head' id='gHead'>
          <div class='gantt-head-inner'>
            $TICKS
          </div>
        </div>

        <div class='gantt-body' id='gBody'>
          <div class='gantt-inner' id='gInner'>
            $TODAY
            <svg class='overlay' id='ov' viewBox='0 0 ${GANTT_W} ${OVER_H}' preserveAspectRatio='none'>
              <defs>
                <marker id='arrow' markerWidth='8' markerHeight='8' refX='4' refY='4' markerUnits='userSpaceOnUse'>
                  <circle cx='4' cy='4' r='3' fill='rgba(245, 158, 11, 0.98)'></circle>
                </marker>
              </defs>
              <g id='edges'></g>
              <g id='miles'></g>
            </svg>
            $GANTT_ROWS
          </div>
        </div>
      </div>
    </div>

    <script>
      const left = document.getElementById('leftBody');
      const gBody = document.getElementById('gBody');
      const gHead = document.getElementById('gHead');
      const gInner = document.getElementById('gInner');
      const ov = document.getElementById('ov');
      const edgesG = document.getElementById('edges');
      const milesG = document.getElementById('miles');

      const PX = $PX;
      const ROW_H = $ROW_H;
      const BAR_H = $BAR_H;
      const BAR_TOP = 6;
      const GANTT_W = ${GANTT_W};
      const OVER_H = ${OVER_H};
      const edges = $EDGES;
      const hitos = $HITOS;

      let lock = false;
      left.addEventListener('scroll', () => {
        if (lock) return;
        lock = true;
        gBody.scrollTop = left.scrollTop;
        lock = false;
      });
      gBody.addEventListener('scroll', () => {
        if (lock) return;
        lock = true;
        left.scrollTop = gBody.scrollTop;
        gHead.scrollLeft = gBody.scrollLeft;
        lock = false;
      });
      gHead.addEventListener('scroll', () => {
        if (lock) return;
        lock = true;
        gBody.scrollLeft = gHead.scrollLeft;
        lock = false;
      });

      const succ = new Map();
      const pred = new Map();
      edges.forEach(e => {
        if (!succ.has(e.o)) succ.set(e.o, []);
        if (!pred.has(e.d)) pred.set(e.d, []);
        succ.get(e.o).push(e.d);
        pred.get(e.d).push(e.o);
      });

      function getRowEl(id){
        return document.querySelector(`#gInner .row[data-id="${id}"]`);
      }

      function collectNodes(rootId, depth){
        const seen = new Set([rootId]);
        let frontier = [rootId];
        for (let i = 0; i < depth; i++){
          const next = [];
          frontier.forEach(x => {
            (pred.get(x) || []).forEach(p => { if (!seen.has(p)) { seen.add(p); next.push(p); } });
            (succ.get(x) || []).forEach(s => { if (!seen.has(s)) { seen.add(s); next.push(s); } });
          });
          frontier = next;
          if (frontier.length === 0) break;
        }
        return seen;
      }

      function barAnchor(rowEl, tipo, side){
        const es = parseInt(rowEl.dataset.es || "0", 10);
        const ef = parseInt(rowEl.dataset.ef || "0", 10);

        const rowTop = rowEl.offsetTop;
        const yMid = rowTop + BAR_TOP + (BAR_H / 2);
        const yLane = rowTop + 2;

        const xStart = es * PX;
        const xEnd = ef * PX;

        tipo = (tipo || "FC").toUpperCase();

        let useStart = false;
        if (side === "o") {
          useStart = (tipo === "CC" || tipo === "CF");
        } else {
          useStart = (tipo === "CC" || tipo === "FC");
        }

        return { x: useStart ? xStart : xEnd, yMid, yLane };
      }

      function pathBetween(a, b){
        const dx = b.x - a.x;
        if (Math.abs(dx) < 0.5){
          return `M ${a.x} ${a.yMid} L ${b.x} ${b.yMid}`;
        }

        const midX = a.x + (dx / 2);
        return `M ${a.x} ${a.yMid}
                L ${a.x} ${a.yLane}
                L ${midX} ${a.yLane}
                L ${midX} ${b.yLane}
                L ${b.x} ${b.yLane}
                L ${b.x} ${b.yMid}`;
      }

      function drawEdges(rootId, depth){
        edgesG.innerHTML = "";
        if (!rootId) return;

        const keep = collectNodes(rootId, depth);
        edges.forEach(e => {
          if (!keep.has(e.o) || !keep.has(e.d)) return;

          const ro = getRowEl(e.o);
          const rd = getRowEl(e.d);
          if (!ro || !rd) return;
          if (ro.dataset.term !== "1" || rd.dataset.term !== "1") return;

          const a = barAnchor(ro, e.tipo || "FC", "o");
          const b = barAnchor(rd, e.tipo || "FC", "d");

          const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
          p.setAttribute("d", pathBetween(a, b));
          p.setAttribute("class", "edge");
          p.setAttribute("marker-end", "url(#arrow)");
          edgesG.appendChild(p);
        });
      }

      const tip = document.getElementById("tip");
      const wrap = document.querySelector(".proj-wrap");
      let tipOn = false;

      function showTip(txt){
        if(!txt) return;
        tip.textContent = txt;
        tip.style.display = "block";
        tipOn = true;
      }

      function hideTip(){
        tip.style.display = "none";
        tip.textContent = "";
        tipOn = false;
      }

      function moveTip(ev){
        if(!tipOn) return;
        const r = wrap.getBoundingClientRect();

        let x = (ev.clientX - r.left) + 12;
        let y = (ev.clientY - r.top) + 12;

        const w = tip.offsetWidth || 260;
        const h = tip.offsetHeight || 40;
        const maxX = r.width - w - 8;
        const maxY = r.height - h - 8;

        if(x > maxX) x = Math.max(8, maxX);
        if(y > maxY) y = Math.max(8, maxY);

        tip.style.left = x + "px";
        tip.style.top = y + "px";
      }

      wrap.addEventListener("mousemove", moveTip);
      wrap.querySelectorAll(".nm, .cell.hito").forEach(el => {
        el.addEventListener("mouseenter", () => showTip(el.getAttribute("data-title")));
        el.addEventListener("mouseleave", hideTip);
      });
      left.addEventListener("scroll", hideTip);
      gBody.addEventListener("scroll", hideTip);

      function drawHitos(){
        if (!milesG) return;
        milesG.innerHTML = "";
        if (!hitos || hitos.length === 0) return;

        hitos.forEach(h => {
          const rowEl = getRowEl(h.id);
          if (!rowEl) return;
          if (rowEl.dataset.term !== "1") return;

          const es = parseInt(rowEl.dataset.es || "0", 10);
          const ef = parseInt(rowEl.dataset.ef || "0", 10);
          const y = rowEl.offsetTop + BAR_TOP + (BAR_H / 2);

          let x = (String(h.tipo).toUpperCase() === "FF") ? (ef * PX) : (es * PX);
          const s = 8;

          const minX = s + 2;
          const maxX = Math.max(minX, gBody.scrollWidth - s - 2);
          x = Math.min(Math.max(x, minX), maxX);

          const pts = `${x},${y - s} ${x + s},${y} ${x},${y + s} ${x - s},${y}`;
          const poly = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
          poly.setAttribute("points", pts);
          poly.setAttribute("class", "mile");
          milesG.appendChild(poly);
        });
      }

      function captureCronograma(){
        const area = document.getElementById("captureArea");
        if (!area) return;

        html2canvas(area, {
          backgroundColor: "#ffffff",
          useCORS: true,
          scale: 2
        }).then(srcCanvas => {
          const areaRect = area.getBoundingClientRect();

          const leftRows = area.querySelectorAll(".left-pane .row");
          const rightRows = area.querySelectorAll(".right-pane .row");

          let bottomPx = areaRect.height;

          const lastLeft = leftRows.length ? leftRows[leftRows.length - 1].getBoundingClientRect() : null;
          const lastRight = rightRows.length ? rightRows[rightRows.length - 1].getBoundingClientRect() : null;

          const bottoms = [];
          if (lastLeft) bottoms.push(lastLeft.bottom - areaRect.top);
          if (lastRight) bottoms.push(lastRight.bottom - areaRect.top);

          if (bottoms.length) {
            bottomPx = Math.max(...bottoms) + 20;
          }

          const scaleFactor = srcCanvas.width / areaRect.width;
          const cropW = srcCanvas.width;
          const cropH = Math.min(srcCanvas.height, Math.round(bottomPx * scaleFactor));

          const croppedCanvas = document.createElement("canvas");
          croppedCanvas.width = cropW;
          croppedCanvas.height = cropH;

          const croppedCtx = croppedCanvas.getContext("2d");
          croppedCtx.drawImage(srcCanvas, 0, 0, cropW, cropH, 0, 0, cropW, cropH);

          const outW = 3300;
          const outH = 2550;
          const margin = 80;

          const outCanvas = document.createElement("canvas");
          outCanvas.width = outW;
          outCanvas.height = outH;

          const ctx = outCanvas.getContext("2d");
          ctx.fillStyle = "#ffffff";
          ctx.fillRect(0, 0, outW, outH);

          const maxW = outW - margin * 2;
          const maxH = outH - margin * 2;

          const fitScale = Math.min(maxW / croppedCanvas.width, maxH / croppedCanvas.height);
          const drawW = croppedCanvas.width * fitScale;
          const drawH = croppedCanvas.height * fitScale;

          const x = (outW - drawW) / 2;
          const y = (outH - drawH) / 2;

          ctx.drawImage(croppedCanvas, x, y, drawW, drawH);

          const link = document.createElement("a");
          link.download = "cronograma_carta_horizontal.png";
          link.href = outCanvas.toDataURL("image/png");
          link.click();
        });
      }

      function renderHitosSeguro(){
        if (ov && gInner) {
          const h = Math.max(gInner.scrollHeight, gBody.scrollHeight, OVER_H);
          ov.style.height = `${h}px`;
          ov.setAttribute("viewBox", `0 0 ${GANTT_W} ${h}`);
        }
        drawHitos();
      }

      requestAnimationFrame(renderHitosSeguro);
      setTimeout(renderHitosSeguro, 120);
      setTimeout(renderHitosSeguro, 350);
      window.addEventListener("load", renderHitosSeguro);
      window.addEventListener("resize", renderHitosSeguro);
    </script>
    """)

    html = html_t.safe_substitute(
        LEFT_W=str(left_w),
        GANTT_W=str(gantt_w),
        ROW_H=str(row_h),
        BAR_H=str(row_h - 12),
        OVER_H=str(int(len(dfp_vista) * row_h) + 80),
        EXPORT_H=str(export_height),
        PX=str(px_per_unit),
        TICKS=ticks_html,
        TODAY=today_line,
        HEADER_HTML=header_html,
        LEFT_ROWS="".join(left_rows_html),
        GANTT_ROWS="".join(gantt_rows_html),
        EDGES=edges_json,
        HITOS=hitos_json,
    )

    components.html(html, width=left_w + right_w + 80, height=3200, scrolling=True)

st.session_state["cronograma_datos"] = cronograma_datos
