import streamlit as st
import pandas as pd
import json
import math
import plotly.graph_objects as go
import streamlit.components.v1 as components
from datetime import date, timedelta
import calendar
from string import Template

st.markdown("## 📊 3. PERT ")

st.markdown("""
<style>
/* Etiquetas O/M/P centradas y en negrilla */
.omp-label{
  text-align:center;
  font-weight:800;
  color:#0B3D2E;
  margin-bottom:6px;
}

/* SOLO OMP: sombreado suave y borde verde */
.pert-omp div[data-testid="stNumberInput"] input{
  background: #EAF7EF !important;
  border: 1px solid #9AD3AE !important;
  box-shadow: 0 2px 10px rgba(11,61,46,0.10) !important;
  border-radius: 10px !important;
  font-weight: 700 !important;
  text-align: center !important;
}
</style>
""", unsafe_allow_html=True)

# ----------------------------
# Helpers
# ----------------------------
def key_codigo_natural(codigo: str):
    partes = str(codigo).split(".")
    out = []
    for p in partes:
        out.append(int(p) if p.isdigit() else 0)
    return tuple(out)

def edge_key(o, d):
    return f"{o}::{d}"

def ensure_edge_meta(aristas: dict, o, d):
    k = edge_key(o, d)
    meta = aristas.get(k)
    if not isinstance(meta, dict):
        meta = {"tipo": "FC", "lag": 0}
        aristas[k] = meta
    if meta.get("tipo") not in ("FC", "CC", "FF", "CF"):
        meta["tipo"] = "FC"
    try:
        meta["lag"] = int(meta.get("lag", 0))
    except Exception:
        meta["lag"] = 0
    return meta

def detectar_bucle(red: dict, terminales_ids: set):
    # DFS en terminales
    g = {}
    for o, ds in (red or {}).items():
        if o not in terminales_ids:
            continue
        g[o] = [d for d in (ds or []) if d in terminales_ids]

    visit, stack = set(), set()
    def dfs(n):
        visit.add(n); stack.add(n)
        for v in g.get(n, []):
            if v not in visit:
                if dfs(v):
                    return True
            elif v in stack:
                return True
        stack.remove(n)
        return False

    for n in g.keys():
        if n not in visit:
            if dfs(n):
                return True
    return False

def extraer_nodos_desde_edt(alcance: dict):
    """
    Devuelve lista_nodos (todos) y terminales_ids (solo terminales).
    Cada nodo: id, codigo, nombre, nivel, padre_id, es_terminal, tipo_txt
    """
    lista_nodos = []
    terminales_ids = set()

    objetivos = alcance.get("objetivos") or []
    edt_data = alcance.get("edt_data") or {}

    for i, obj in enumerate(objetivos):
        oid = obj.get("id")
        cod_obj = f"{i+1}"
        nom_obj = obj.get("texto", "Objetivo")
        lista_nodos.append({
            "id": oid, "codigo": cod_obj, "nombre": nom_obj,
            "nivel": 1, "padre_id": None, "es_terminal": False, "tipo_txt": "OBJETIVO"
        })

        productos = edt_data.get(oid, []) if oid else []
        for j, p in enumerate(productos):
            pid = p.get("id")
            cod_prod = f"{cod_obj}.{j+1}"
            nom_prod = p.get("nombre", "Producto")
            acts = p.get("actividades", []) or []

            es_term_p = len(acts) == 0
            lista_nodos.append({
                "id": pid, "codigo": cod_prod, "nombre": nom_prod,
                "nivel": 2, "padre_id": oid, "es_terminal": es_term_p,
                "tipo_txt": "PRODUCTO"
            })
            if es_term_p and pid:
                terminales_ids.add(pid)

            for k, a in enumerate(acts):
                aid = a.get("id")
                cod_act = f"{cod_prod}.{k+1}"
                nom_act = a.get("nombre", "Actividad")
                paqs = a.get("paquetes", []) or []

                es_term_a = len(paqs) == 0
                lista_nodos.append({
                    "id": aid, "codigo": cod_act, "nombre": nom_act,
                    "nivel": 3, "padre_id": pid, "es_terminal": es_term_a,
                    "tipo_txt": "ACTIVIDAD"
                })
                if es_term_a and aid:
                    terminales_ids.add(aid)

                for l, pq in enumerate(paqs):
                    pqid = pq.get("id")
                    cod_paq = f"{cod_act}.{l+1}"
                    nom_paq = pq.get("nombre", "Paquete")
                    lista_nodos.append({
                        "id": pqid, "codigo": cod_paq, "nombre": nom_paq,
                        "nivel": 4, "padre_id": aid, "es_terminal": True,
                        "tipo_txt": "PAQUETE"
                    })
                    if pqid:
                        terminales_ids.add(pqid)

    if alcance.get("requiere_costos_indirectos", "No") == "Sí":
        costos_indirectos = alcance.get("otros_costos_indirectos_proyecto", []) or []
        if costos_indirectos:
            ci_group_id = "costos_indirectos_proyecto"
            ci_group_code = f"{len(objetivos) + 1}"
            ci_group_name = "COSTOS INDIRECTOS DEL PROYECTO"

            lista_nodos.append({
                "id": ci_group_id,
                "codigo": ci_group_code,
                "nombre": ci_group_name,
                "nivel": 1,
                "padre_id": "--",
                "es_terminal": False,
                "tipo_txt": "OBJETIVO"
            })

            for j, ci in enumerate(costos_indirectos):
                ci_id = ci.get("id")
                ci_nombre = ci.get("nombre", "Costo indirecto")
                ci_code = f"{ci_group_code}.{j+1}"

                lista_nodos.append({
                    "id": ci_id,
                    "codigo": ci_code,
                    "nombre": ci_nombre,
                    "nivel": 2,
                    "padre_id": ci_group_id,
                    "es_terminal": True,
                    "tipo_txt": "PRODUCTO"
                })
                if ci_id:
                    terminales_ids.add(ci_id)

    dict_id = {n["id"]: n for n in lista_nodos if n.get("id") is not None}
    return lista_nodos, terminales_ids, dict_id

def calc_ES_con_tipos(red: dict, aristas: dict, dur_func, terminales_ids: set):
    """
    Restricciones en ES:
      FC: ESd >= ESo + Dur_o + lag
      CC: ESd >= ESo + lag
      FF: ESd >= ESo + Dur_o + lag - Dur_d
      CF: ESd >= ESo + lag - Dur_d
    """
    edges = []
    for o, ds in (red or {}).items():
        if o not in terminales_ids:
            continue
        for d in (ds or []):
            if d not in terminales_ids:
                continue
            meta = ensure_edge_meta(aristas, o, d)
            tipo = meta["tipo"]
            lag = int(meta["lag"])
            do = dur_func(o)
            dd = dur_func(d)
            if tipo == "FC":
                w = do + lag
            elif tipo == "CC":
                w = lag
            elif tipo == "FF":
                w = do + lag - dd
            else:  # CF
                w = lag - dd
            edges.append((o, d, w))

    indeg = {t: 0 for t in terminales_ids}
    adj = {t: [] for t in terminales_ids}
    for o, d, w in edges:
        adj[o].append((d, w))
        indeg[d] += 1

    q = [n for n in terminales_ids if indeg.get(n, 0) == 0]
    topo = []
    while q:
        n = q.pop(0)
        topo.append(n)
        for d, _w in adj.get(n, []):
            indeg[d] -= 1
            if indeg[d] == 0:
                q.append(d)

    ES = {t: 0 for t in terminales_ids}
    for n in topo:
        for d, w in adj.get(n, []):
            ES[d] = max(ES.get(d, 0), ES.get(n, 0) + w)

    return ES

def barras_texto(inicio: int, dur: int, max_fin: int, width: int = 50):
    # escala simple para no hacer barras gigantes
    if max_fin <= 0:
        max_fin = 1
    scale = max_fin / width
    if scale <= 0:
        scale = 1
    s = int(inicio / scale)
    d = max(1, int(dur / scale))
    s = max(0, min(width, s))
    d = max(1, min(width - s, d))
    return (" " * s) + ("█" * d)

# ----------------------------
# Estado
# ----------------------------
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

# Limpiar red a terminales
red_limpia = {}
for o, ds in (red or {}).items():
    if o in terminales_ids:
        red_limpia[o] = [d for d in (ds or []) if d in terminales_ids]
red = red_limpia

if detectar_bucle(red, terminales_ids):
    st.error("🚨 La red tiene un bucle (dependencia circular). Corrige en '2. Cronograma'.")
    st.stop()

# ----------------------------
# DURACIÓN PERT (ceil) con default 1
# ----------------------------
def dur_pert(nid):
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

# ----------------------------
# 1) PERT primero: selector + panel automático
# ----------------------------
st.markdown("### 1) TIEMPOS O / M /P para cada actividad")

terminales = [dict_id[n] for n in terminales_ids if n in dict_id]
terminales = sorted(terminales, key=lambda x: key_codigo_natural(x["codigo"]))
terminales_labels = {t["id"]: f'{t["codigo"]} — {t["nombre"]}' for t in terminales}

sel_id = st.selectbox(
    "Seleccione actividad terminal (CÓDIGO — NOMBRE)",
    options=[t["id"] for t in terminales],
    format_func=lambda x: terminales_labels.get(x, str(x)),
    index=0
)

# Muestra el texto completo (evita corte)
st.caption(f"**Actividad seleccionada:** {terminales_labels.get(sel_id, '')}")

st.caption("Al cambiar O/M/P, se guarda automáticamente en el estado del proyecto.")
mostrar_incertidumbre = st.toggle("Mostrar incertidumbre (σ y varianza)", value=False)
rec = (cronograma_datos["pert"].get(str(sel_id), {}) or {})
# valores actuales (persisten)
O0 = rec.get("O", None)
M0 = rec.get("M", None)
P0 = rec.get("P", None)

st.markdown('<div class="pert-omp">', unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns([2, 2, 2, 4], vertical_alignment="center")

with c1:
    st.markdown('<div class="omp-label">O</div>', unsafe_allow_html=True)
    O = st.number_input(
        "",
        value=float(O0) if O0 is not None else 0.0,
        min_value=0.0,
        step=0.01,
        format="%.2f",
        key=f"pert_O_{sel_id}",
        label_visibility="collapsed",
    )

with c2:
    st.markdown('<div class="omp-label">M</div>', unsafe_allow_html=True)
    M = st.number_input(
        "",
        value=float(M0) if M0 is not None else 0.0,
        min_value=0.0,
        step=0.01,
        format="%.2f",
        key=f"pert_M_{sel_id}",
        label_visibility="collapsed",
    )

with c3:
    st.markdown('<div class="omp-label">P</div>', unsafe_allow_html=True)
    P = st.number_input(
        "",
        value=float(P0) if P0 is not None else 0.0,
        min_value=0.0,
        step=0.01,
        format="%.2f",
        key=f"pert_P_{sel_id}",
        label_visibility="collapsed",
    )

with c4:
    dur_calc = max(1, int(math.ceil((O + 4.0*M + P) / 6.0))) if (O is not None and M is not None and P is not None) else 1
    st.markdown(f"**Duración PERT (ceil):** {dur_calc} {escala}")

st.markdown("</div>", unsafe_allow_html=True)

# Guardado automático (sin botón)
cronograma_datos["pert"][str(sel_id)] = {
    "O": round(float(O), 2),
    "M": round(float(M), 2),
    "P": round(float(P), 2),
}
st.session_state["cronograma_datos"] = cronograma_datos

st.divider()

# ----------------------------
# 4) Tabla final: código, nombre, duración, predecesoras, barras
# ----------------------------
st.markdown("### 2) CRONOGRAMA")

# Opciones SOLO terminales (se arma cuando ya tengas dfp; si aún no existe aquí, pega este bloque más abajo
# justo después de crear dfp y antes de crear left_rows_html).

# Predecesoras (invertir red)
preds_map = {}
for o, ds in red.items():
    for d in ds:
        preds_map.setdefault(d, []).append(o)

id_to_cod = {n["id"]: n["codigo"] for n in lista_nodos if n.get("id") is not None}
id_to_nom = {n["id"]: n["nombre"] for n in lista_nodos if n.get("id") is not None}

def _fmt2(v):
    if v is None:
        return ""
    if isinstance(v, str) and v.strip() == "":
        return ""
    try:
        return f"{float(v):.2f}"
    except Exception:
        return str(v)

audit_rows = []
for n in sorted(lista_nodos, key=lambda x: key_codigo_natural(x["codigo"])):
    nid = n.get("id")
    cod = n.get("codigo", "")
    nom = n.get("nombre", "")
    is_parent = not bool(n.get("es_terminal", False))

    # Padres: solo contexto (sin O/M/P ni duración)
    if is_parent or nid is None:
        row = {
            "CÓDIGO": cod,
            "NOMBRE": nom,
            "O": "—",
            "M": "—",
            "P": "—",
            f"DURACIÓN PERT ({escala})": None,
            "PREDECESORAS": "",
            "_parent": True,
        }
        if mostrar_incertidumbre:
            row["σ"] = "—"
            row["Varianza"] = "—"
        audit_rows.append(row)
        continue

    # Terminales: O/M/P desde PERT y duración PERT
    dur = dur_pert(nid)
    rec_pert = (cronograma_datos.get("pert", {}) or {}).get(str(nid), {}) or {}
    O = rec_pert.get("O", "")
    M = rec_pert.get("M", "")
    P = rec_pert.get("P", "")

    pred_ids = preds_map.get(nid, []) or []
    pred_ids = sorted(pred_ids, key=lambda x: key_codigo_natural(id_to_cod.get(x, "0")))
    pred_str = ", ".join([id_to_cod.get(pid, "") for pid in pred_ids if id_to_cod.get(pid)])

    row = {
        "CÓDIGO": cod,
        "NOMBRE": nom,
        "O": _fmt2(O),
        "M": _fmt2(M),
        "P": _fmt2(P),
        f"DURACIÓN PERT ({escala})": dur,
        "PREDECESORAS": pred_str,
        "_parent": False,
    }

    if mostrar_incertidumbre:
        # σ = (P - O)/6 ; Varianza = σ^2 (2 decimales)
        sigma_fmt = ""
        var_fmt = ""
        try:
            if O not in [None, ""] and P not in [None, ""]:
                sigma = (float(P) - float(O)) / 6.0
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
df_master_view = df_master.drop(columns=["_parent"])

def _styler_master(row):
    if bool(df_master.loc[row.name, "_parent"]):
        return ["background-color: #E5E7EB; font-weight: 800; color: #111"] * len(df_master_view.columns)
    return [""] * len(df_master_view.columns)

# Estilo encabezados (verde oscuro) + filas padre (gris)
_hdr = [
    {
        "selector": "th",
        "props": [
            ("background-color", "#0B3D2E"),
            ("color", "white"),
            ("font-weight", "800"),
        ],
    }
]

sty_master = (
    df_master_view.style
    .apply(_styler_master, axis=1)
    .set_table_styles(_hdr)
)

st.dataframe(
    sty_master,
    use_container_width=True,
    hide_index=True,
    height=38 * (min(len(df_master_view), 50) + 1) + 12,
)
# ----------------------------
# ----------------------------
# 3) Gantt — Vista tipo Project (split tabla + gantt, scroll sincronizado)
# ----------------------------
st.markdown("### 3) Diagrama de Gantt ")

# Controles (no afectan el panel superior PERT)
fecha_inicio = cronograma_datos.get("fecha_inicio", date.today())
cA, cB, cC, cD = st.columns([2, 2, 3, 3], vertical_alignment="center")
with cA:
    mostrar_hoy = st.toggle("Mostrar 'Hoy'", value=bool(cronograma_datos.get("mostrar_hoy", False)))
with cB:
    hoy_offset = st.number_input(f"Hoy (offset en {escala})", value=int(cronograma_datos.get("hoy_offset", 0)), step=1)
with cC:
    modo_calendario = st.toggle("Eje en fechas (calendario)", value=bool(cronograma_datos.get("modo_calendario", False)))
with cD:
    fecha_inicio = st.date_input("Fecha inicio proyecto", value=fecha_inicio)
  
cronograma_datos["mostrar_hoy"] = bool(mostrar_hoy)
cronograma_datos["hoy_offset"] = int(hoy_offset)
cronograma_datos["modo_calendario"] = bool(modo_calendario)
cronograma_datos["fecha_inicio"] = fecha_inicio

zoom = st.slider("Zoom horizontal (px por unidad)", min_value=20, max_value=80, value=int(cronograma_datos.get("zoom_gantt", 40)), step=5)
cronograma_datos["zoom_gantt"] = int(zoom)
opciones_vista = ["Completo", "Solo resumen", "Solo hitos"]

if "vista_gantt" not in cronograma_datos:
    cronograma_datos["vista_gantt"] = "Completo"

vista_gantt = st.radio(
    "Vista del cronograma",
    options=opciones_vista,
    key="vista_gantt_selector",
    index=opciones_vista.index(cronograma_datos["vista_gantt"]),
    horizontal=True,
)

cronograma_datos["vista_gantt"] = vista_gantt
st.session_state["cronograma_datos"] = cronograma_datos

# === Cálculo base ===
ES_t = calc_ES_con_tipos(red, aristas, dur_pert, terminales_ids)
EF_t = {nid: int(ES_t.get(nid, 0) + dur_pert(nid)) for nid in terminales_ids}

# Hijos por padre
hijos = {}
for n in lista_nodos:
    pid = n.get("padre_id")
    if pid is None or n.get("id") is None:
        continue
    hijos.setdefault(pid, []).append(n["id"])

cache_range = {}
def rango_nodo(nid):
    if nid in cache_range:
        return cache_range[nid]
    n = dict_id.get(nid)
    if not n:
        cache_range[nid] = None
        return None
    if n["es_terminal"]:
        s = int(ES_t.get(nid, 0))
        f = int(EF_t.get(nid, s + 1))
        cache_range[nid] = (s, f)
        return cache_range[nid]
    desc = hijos.get(nid, [])
    rs = []
    for cid in desc:
        rr = rango_nodo(cid)
        if rr:
            rs.append(rr)
    if not rs:
        cache_range[nid] = None
        return None
    s = min(r[0] for r in rs)
    f = max(r[1] for r in rs)
    cache_range[nid] = (s, f)
    return cache_range[nid]

# Predecesoras para terminales (resumen)
preds_map = {nid: [] for nid in terminales_ids}
for o, ds in red.items():
    for d in (ds or []):
        if d in terminales_ids and o in terminales_ids:
            preds_map.setdefault(d, []).append(o)

# Build filas visibles: padres niveles 1-3 + terminales
rows = []
for n in lista_nodos:
    nid = n.get("id")
    if nid is None:
        continue
    is_terminal = bool(n.get("es_terminal"))
    nivel = int(n.get("nivel", 99))

    if (not is_terminal) and (nivel not in (1, 2, 3)):
        continue

    rr = rango_nodo(nid)
    if rr is None:
        continue
    s, f = rr
    dur = max(1, f - s)

    pred_str = ""
    if is_terminal:
        pred_ids = preds_map.get(nid, []) or []
        pred_ids = sorted(pred_ids, key=lambda x: key_codigo_natural(dict_id.get(x, {}).get("codigo", "0")))
        pred_str = ", ".join([dict_id.get(pid, {}).get("codigo", "") for pid in pred_ids if dict_id.get(pid)])

    rows.append({
        "id": nid,
        "nivel": nivel,
        "codigo": n.get("codigo", ""),
        "nombre": n.get("nombre", ""),
        "is_parent": (not is_terminal),
        "is_terminal": is_terminal,
        "ES": int(s),
        "EF": int(f),
        "dur": int(dur),
        "predecesoras": pred_str
    })

dfp = pd.DataFrame(rows)
if dfp.empty:
    st.info("No hay datos suficientes para construir el Gantt.")
else:
    dfp["cod_key"] = dfp["codigo"].apply(key_codigo_natural)
    dfp["parent_rank"] = dfp["is_parent"].apply(lambda x: 0 if x else 1)
    dfp["grp_key"] = dfp["codigo"].astype(str).apply(lambda c: key_codigo_natural(c)[0] if len(key_codigo_natural(c)) else 0)
    dfp = dfp.sort_values(by=["grp_key","cod_key","parent_rank","ES","nivel"], ascending=[True, True, True, True, True]).reset_index(drop=True)

    max_x = int(dfp["EF"].max()) if len(dfp) else 10
    hitos_all = cronograma_datos.get("hitos", []) or []

    if vista_gantt == "Completo":
        dfp_vista = dfp.copy()
    elif vista_gantt == "Solo resumen":
        dfp_vista = dfp[dfp["is_parent"].astype(bool)].copy()
    else:
        ids_con_hitos = {str(h.get("id")) for h in hitos_all}
        dfp_vista = dfp[dfp["id"].astype(str).isin(ids_con_hitos)].copy()

    MESES_ES = {
        1: "ENE", 2: "FEB", 3: "MAR", 4: "ABR", 5: "MAY", 6: "JUN",
        7: "JUL", 8: "AGO", 9: "SEP", 10: "OCT", 11: "NOV", 12: "DIC"
    }
    
    def add_months(d: date, months: int) -> date:
        y = d.year + (d.month - 1 + months) // 12
        m = (d.month - 1 + months) % 12 + 1
        last_day = calendar.monthrange(y, m)[1]
        day = min(d.day, last_day)
        return date(y, m, day)
    
    def add_years(d: date, years: int) -> date:
        y = d.year + years
        last_day = calendar.monthrange(y, d.month)[1]
        day = min(d.day, last_day)
        return date(y, d.month, day)
    
    def fmt_fecha(d: date) -> str:
        return f"{d.day:02d}-{MESES_ES[d.month]}"

    def fmt_fecha_corta(d: date) -> str:
        return f"{d.day:02d}/{d.month:02d}"
    
    def x_label(t: int) -> str:
        # Si modo calendario está apagado, NO cambia nada
        if not modo_calendario:
            return str(int(t))
    
        esc = str(escala).upper().strip()
    
        if esc == "DÍAS":
            d = fecha_inicio + timedelta(days=int(t))
            return fmt_fecha(d)
    
        if esc == "SEMANAS":
            # Solo fecha de inicio de cada semana
            d = fecha_inicio + timedelta(days=int(t) * 7)
            return fmt_fecha(d)
    
        if esc == "MESES":
            d = add_months(fecha_inicio, int(t))
            return fmt_fecha(d)
    
        if esc == "AÑOS":
            d = add_years(fecha_inicio, int(t))
            return fmt_fecha(d)
    
        # fallback seguro
        d = fecha_inicio + timedelta(days=int(t))
        return fmt_fecha(d)
    
    row_h = 28
    left_w = 680
    px_per_unit = int(zoom)
    gantt_w = max(900, (max_x + 1) * px_per_unit)
    
    # Etiquetas dinámicas para que NO se superpongan
    esc_u = str(escala).upper().strip()
    
    if not modo_calendario:
        # En modo numérico los labels son cortos, así que podemos rotular más seguido
        if px_per_unit >= 35:
            tick_step = 1
        elif px_per_unit >= 22:
            tick_step = 2
        elif px_per_unit >= 14:
            tick_step = 5
        else:
            tick_step = 10
    else:
        # En modo calendario los labels ocupan más espacio
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
            # SEMANAS / MESES / AÑOS
            tick_step = 1
    
    ticks = [(t, x_label(t)) for t in range(0, max_x + 1, tick_step)]
    
    def esc(s):
        return (str(s)
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#39;"))
    
    st.markdown("#### Hitos")
    # Solo terminales
    df_terminales = dfp[dfp["is_parent"] == False].copy()
    opciones_hitos = [f'{r["codigo"]} | {r["nombre"]}' for _, r in df_terminales.iterrows()]
    map_label_to_id = {f'{r["codigo"]} | {r["nombre"]}': str(r["id"]) for _, r in df_terminales.iterrows()}

    c1, c2, c3, c4 = st.columns([2, 4, 2, 2], vertical_alignment="bottom")
    with c1:
        hito_nombre = st.text_input("Nombre del hito", key="hito_nombre")
    with c2:
        hito_act = st.selectbox("Actividad (solo terminales)", opciones_hitos, key="hito_act")
    with c3:
        hito_tipo = st.selectbox("Tipo", ["CC", "FF"], key="hito_tipo")
    with c4:
        agregar_hito = st.button("Agregar hito", use_container_width=True)
    
    if agregar_hito:
        nombre = (hito_nombre or "").strip()
        if not nombre:
            st.warning("Escribe un nombre de hito.")
        else:
            act_id = map_label_to_id[hito_act]
            hitos_existentes = cronograma_datos.get("hitos", []) or []
            ya_tiene_hito = any(str(h.get("id")) == str(act_id) for h in hitos_existentes)

            if ya_tiene_hito:
                st.warning("La actividad ya tiene el hito.")
            else:
                cronograma_datos["hitos"].append({"id": act_id, "nombre": nombre, "tipo": hito_tipo})
                st.session_state["cronograma_datos"] = cronograma_datos
                st.success("Hito agregado.")

    with st.expander("Gestionar hitos (editar / borrar)", expanded=False):
      hitos = cronograma_datos.get("hitos", []) or []
  
      if not hitos:
          st.info("No hay hitos registrados.")
      else:
          opciones = [f'{h.get("nombre")} ({h.get("tipo")})' for h in hitos]
        
          sel = st.selectbox("Selecciona un hito", opciones, key="hito_sel_manage")
          idx = opciones.index(sel)
  
          nuevo_nombre = st.text_input(
              "Nuevo nombre del hito",
              value=str(hitos[idx].get("nombre", "")),
              key="hito_nuevo_nombre"
          )
  
          cA, cB, cC = st.columns([2, 2, 2], vertical_alignment="bottom")
  
          with cA:
              if st.button("Guardar nombre", use_container_width=True):
                  nombre = (nuevo_nombre or "").strip()
                  if not nombre:
                      st.warning("El nombre no puede quedar vacío.")
                  else:
                      cronograma_datos["hitos"][idx]["nombre"] = nombre
                      st.session_state["cronograma_datos"] = cronograma_datos
                      st.rerun()
  
          with cB:
              if st.button("Borrar este hito", use_container_width=True):
                  cronograma_datos["hitos"].pop(idx)
                  st.session_state["cronograma_datos"] = cronograma_datos
                  st.rerun()
  
          with cC:
              confirmar = st.checkbox("Confirmo borrar TODOS", key="hito_confirm_borrar_todos")
              if st.button("Borrar todos", use_container_width=True, disabled=not confirmar):
                  cronograma_datos["hitos"] = []
                  st.session_state["cronograma_datos"] = cronograma_datos
                  st.rerun()
    
    left_rows_html = []
    gantt_rows_html = []

    for _, r in dfp_vista.iterrows():
        code = esc(r["codigo"])
        name = esc(r["nombre"])
        dur = esc(r["dur"])

        es_num = int(r["ES"])
        ef_num = int(r["EF"])
        esv = esc(es_num)
        efv = esc(ef_num)

        if modo_calendario:
            es_txt = esc(fmt_fecha_corta(fecha_inicio + timedelta(days=es_num))) if str(escala).upper().strip() == "DÍAS" else esc(x_label(es_num))
            ef_txt = esc(fmt_fecha_corta(fecha_inicio + timedelta(days=ef_num))) if str(escala).upper().strip() == "DÍAS" else esc(x_label(ef_num))
        else:
            es_txt = esv
            ef_txt = efv

        pred = esc(r["predecesoras"])

        indent = (int(r["nivel"]) - 1) * 14
        is_parent = bool(r["is_parent"])
        row_class = "row parent" if is_parent else "row task"
        rid = esc(str(r["id"]))
        term_val = "0" if is_parent else "1"

      # Hitos asociados a esta actividad (solo terminales por regla)
        hitos = cronograma_datos.get("hitos", []) or []
        hitos_de_esta = [h for h in hitos if str(h.get("id")) == str(r["id"])]

        # Texto corto visible y tooltip completo
        hitos_txt = "; ".join([f'{h["nombre"]} ({h["tipo"]})' for h in hitos_de_esta])
        hitos_txt = esc(hitos_txt)

        if modo_calendario:
            left_rows_html.append(f"""
              <div class='{row_class}' data-id='{rid}' data-es='{esv}' data-ef='{efv}' data-term='{term_val}' style='height:{row_h}px'>
                <div class='cell code'>{code}</div>
                <div class='cell name' style='padding-left:{indent}px'><span class='nm' data-title='{name}'>{name}</span></div>
                <div class='cell dur'>{dur}</div>
                <div class='cell es'>{es_txt}</div>
                <div class='cell ef'>{ef_txt}</div>
                <div class='cell hito' data-title='{hitos_txt}'>{hitos_txt}</div>
              </div>
            """)
        else:
            left_rows_html.append(f"""
              <div class='{row_class}' data-id='{rid}' data-es='{esv}' data-ef='{efv}' data-term='{term_val}' style='height:{row_h}px'>
                <div class='cell code'>{code}</div>
                <div class='cell name' style='padding-left:{indent}px'><span class='nm' data-title='{name}'>{name}</span></div>
                <div class='cell dur'>{dur}</div>
                <div class='cell es'>{es_txt}</div>
                <div class='cell ef'>{ef_txt}</div>
                <div class='cell hito' data-title='{hitos_txt}'>{hitos_txt}</div>
                <div class='cell pred'>{pred}</div>
              </div>
            """)

        x = int(r["ES"]) * px_per_unit
        w = max(1, int(r["dur"]) * px_per_unit)
        bar_class = "bar parentbar" if is_parent else "bar taskbar"

        gantt_rows_html.append(f"""
          <div class='{row_class}' data-id='{rid}' data-es='{esv}' data-ef='{efv}' data-term='{term_val}' style='height:{row_h}px'>
            <div class='barwrap'>
              <div class='{bar_class}' style='left:{x}px;width:{w}px'></div>
            </div>
          </div>
        """)

    today_line = ""
    if mostrar_hoy:
        xh = int(hoy_offset) * px_per_unit
        today_line = f"<div class='today' style='left:{xh}px'></div><div class='todaylabel' style='left:{xh+6}px'>HOY</div>"

    tick_html = []
    for t, lab in ticks:
        x = t * px_per_unit
        tick_html.append(f"<div class='tick' style='left:{x}px'>{esc(lab)}</div>")
        tick_html.append(f"<div class='vline' style='left:{x}px'></div>")
    ticks_html = "".join(tick_html)

    # ==========================
    # HTML Project (sin f-string) + Flechas (modo foco)
    # ==========================
    # Edges (terminales) con tipo para puntos de anclaje (FC/CC/FF/CF)
    edges = []
    for o, ds in (red or {}).items():
        if o not in terminales_ids:
            continue
        for d in (ds or []):
            if d not in terminales_ids:
                continue
            meta = ensure_edge_meta(aristas, o, d)
            edges.append({"o": str(o), "d": str(d), "tipo": meta.get("tipo", "FC")})

    edges_json = json.dumps(edges, ensure_ascii=False)
    hitos_json = json.dumps(cronograma_datos.get("hitos", []) or [], ensure_ascii=False)

    if modo_calendario:
            header_html = """
            <div class='header'>
              <div class='hcell h-code'>CÓDIGO</div>
              <div class='hcell h-name'>NOMBRE</div>
              <div class='hcell h-dur'>DUR</div>
              <div class='hcell h-es'>ES</div>
              <div class='hcell h-ef'>EF</div>
              <div class='hcell h-hito'>HITOS</div>
            </div>
            """
    else:
        header_html = """
        <div class='header'>
          <div class='hcell h-code'>CÓDIGO</div>
          <div class='hcell h-name'>NOMBRE</div>
          <div class='hcell h-dur'>DUR</div>
          <div class='hcell h-es'>ES</div>
          <div class='hcell h-ef'>EF</div>
          <div class='hcell h-hito'>HITOS</div>
          <div class='hcell h-pred'>PREDECESORAS</div>
        </div>
        """
  

    html_t = Template("""
    <style>
      .proj-wrap { display:flex; gap:12px; position:relative; }
      .left-pane{
        width:${LEFT_W}px;
        border:1px solid #e5e7eb;
        border-radius:10px;
        overflow:hidden;
        background:#fff;
      }
      .right-pane{
        flex:1;
        border:1px solid #e5e7eb;
        border-radius:10px;
        overflow:hidden;
        background:#fff;
      }

      /* Tipografía consistente (se parece a Streamlit) */
      .proj-wrap, .left-pane, .right-pane, .header, .row, .cell, .gantt-head, .gantt-body{
        font-family: system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
        font-size: 12px;
      }

      .header{ display:flex; align-items:center; height:34px; box-sizing:border-box; background:#7B1E3A; color:#fff; font-weight:800; font-size:12px; border-bottom:1px solid #e5e7eb; }
      .hcell{ padding:8px 10px; border-right:1px solid rgba(255,255,255,0.18); }
      .h-code{ width:80px; }
      .h-name{ width:340px; }
      .h-dur{ width:70px; text-align:center; }
      .h-es, .h-ef{ width:60px; text-align:center; }
      .h-hito{ width:220px; }
      .h-pred{ flex:1; min-width:120px; }

      .body{ height:560px; overflow:auto; }
      .row { display:flex; align-items:center; border-bottom:1px solid #f3f4f6; font-size:12px; width:100%; position:relative; }
      
      .row.parent{ background:#E5E7EB; font-weight:800; cursor:default; }
     .row.selected{
        outline:1px solid rgba(11,61,46,0.35);
        outline-offset:-1px;
        background: rgba(11,61,46,0.03);
      }
      .cell{ padding:0 10px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
      .cell.code{ width:80px; }
      .cell.name{ width:340px; }
      .cell.dur{ width:70px; text-align:center; }
      .cell.es, .cell.ef{ width:60px; text-align:center; }
      .cell.hito{ width:220px; }
      .cell.pred{ flex:1; min-width:120px; }
      .nm{ display:block; width:100%; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }

      .gantt-head{
        position:relative;
        height:34px;
        background:#f8fafc;
        border-bottom:1px solid #e5e7eb;
        overflow:hidden;
        display:flex;
        align-items:center;
        justify-content:flex-end;
        gap:10px;
        padding-right:10px;
      }
      .gantt-head .toggle{
        display:flex; align-items:center; gap:6px;
        font-weight:560; color:#0B3D2E; font-size:12px;
        user-select:none;
      }
      .gantt-head .toggle input{ transform: translateY(1px); }
      .gantt-head-inner{ position:absolute; left:0; top:0; right:0; bottom:0; }
      .tick{ position:absolute; top:6px; font-size:11px; color:#0B3D2E; font-weight:800; }
      .vline{ position:absolute; top:0; bottom:0; width:1px; background:#eef2f7; }

      .gantt-body{
        position:relative;
        height:560px;
        overflow-y:scroll;
        overflow-x:scroll;
      }
      .gantt-inner{ position:relative; width:${GANTT_W}px; }
      .barwrap { position:relative; width:100%; height:${ROW_H}px; overflow:visible; }
      .bar{
        position:absolute;
        top:6px;
        height:${BAR_H}px;
        border-radius:6px;
        z-index:3;
      }
      .taskbar{ background:rgba(123,30,58,0.82); }
      .parentbar{ background:rgba(166,77,101,0.72); }

      .today{ position:absolute; top:0; bottom:0; width:2px; background:#ef4444; z-index:5; }
      .todaylabel{ position:absolute; top:6px; font-size:11px; font-weight:800; color:#ef4444; z-index:6; }

      /* Overlay SVG flechas */
      .overlay{
        position:absolute;
        left:0; top:0;
        width:${GANTT_W}px;
        height:${OVER_H}px;
        pointer-events:none;
        z-index:7;
      }
      .edge{
        stroke: rgba(245, 158, 11, 0.95);   /* naranja */
        stroke-width: 4.5;
        fill: none;
      }
     .mile{
        fill: rgba(239, 68, 68, 0.95);     /* rojo */
        stroke: rgba(127, 29, 29, 0.85);   /* borde rojo oscuro */
        stroke-width: 1.2;
      }
      .miletext{
        font-size: 11px;
        font-weight: 800;
        fill: rgba(11,61,46,0.85);
      }

    #tip{
      position: absolute;
      display: none;
      background: rgba(15, 23, 42, 0.95);
      color: #fff;
      padding: 6px 8px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      max-width: 520px;
      z-index: 999999;
      pointer-events: none;
      box-shadow: 0 8px 20px rgba(0,0,0,0.25);
      white-space: normal;
    }
  
    </style>

    <div class='proj-wrap'>
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
                </marker>>
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
      const left  = document.getElementById('leftBody');
      const gBody = document.getElementById('gBody');
      const gHead = document.getElementById('gHead');
      const gInner = document.getElementById('gInner');
      const edgesG = document.getElementById('edges');
      const milesG = document.getElementById('miles');
    
      // Data
      const PX = $PX;
      const ROW_H = $ROW_H;
      const BAR_H = $BAR_H;
      const BAR_TOP = 6;            // debe coincidir con .bar { top: 6px; }
      const edges = $EDGES;
      const hitos = $HITOS;
    
      // Sync scroll (solo top/bottom y head<->body; NO movemos overlay con transform)
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
    
      // Build maps for BFS neighborhood
      const succ = new Map();
      const pred = new Map();
      edges.forEach(e => {
        if (!succ.has(e.o)) succ.set(e.o, []);
        if (!pred.has(e.d)) pred.set(e.d, []);
        succ.get(e.o).push(e.d);
        pred.get(e.d).push(e.o);
      });
    
      // Always anchor drawing to RIGHT pane rows
      function getRowEl(id){
        return document.querySelector(`#gInner .row[data-id="${id}"]`);
      }
    
      function clearSelection(){
        document.querySelectorAll('.row.selected').forEach(el => el.classList.remove('selected'));
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
    
      // Anchor point for each row according to precedence type
      // Returns:
      //  - x: anchor x on bar edge (start or end)
      //  - yMid: exact middle of bar
      //  - yLane: "safe lane" above bar for horizontals (avoid painting on bars A/B)
      function barAnchor(rowEl, tipo, side){
        const es = parseInt(rowEl.dataset.es || "0", 10);
        const ef = parseInt(rowEl.dataset.ef || "0", 10);
    
        const rowTop = rowEl.offsetTop;
        const yMid  = rowTop + BAR_TOP + (BAR_H / 2);
        const yLane = rowTop + 2; // carril superior dentro del renglón (ajústalo si quieres)
    
        const xStart = es * PX;
        const xEnd   = ef * PX;
    
        tipo = (tipo || "FC").toUpperCase();
    
        // side: "o" origen, "d" destino
        // CC: inicio->inicio, FC: fin->inicio, FF: fin->fin, CF: inicio->fin
        let useStart = false;
    
        if (side === "o") {
          // Origen: CC y CF salen del inicio; FC y FF salen del fin
          useStart = (tipo === "CC" || tipo === "CF");
        } else {
          // Destino: CC y FC llegan al inicio; FF y CF llegan al fin
          useStart = (tipo === "CC" || tipo === "FC");
        }
    
        const x = useStart ? xStart : xEnd;
        return { x, yMid, yLane };
      }
    
      // Path rule:
      // - If dx == 0: draw vertical straight line (rule B).
      // - Else: route using lane (yLane) so horizontals do NOT paint over bars A/B.
      //   Use symmetric midX = a.x + dx/2 (your “1.5 + 1.5” idea in general form).
      function pathBetween(a, b){
        const dx = b.x - a.x;
    
        // dx == 0  -> straight vertical (you accept it)
        if (Math.abs(dx) < 0.5){
          return `M ${a.x} ${a.yMid} L ${b.x} ${b.yMid}`;
        }
    
        const midX = a.x + (dx / 2);
    
        // Up to lane, horizontal half, vertical on lane, horizontal half, down to bar middle
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
    
          // Only terminal rows
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
  // ===== Tooltip global (no se recorta por overflow) =====
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

    // posición relativa a .proj-wrap
    let x = (ev.clientX - r.left) + 12;
    let y = (ev.clientY - r.top) + 12;

    // clamp para que no se salga
    const w = tip.offsetWidth || 260;
    const h = tip.offsetHeight || 40;
    const maxX = r.width - w - 8;
    const maxY = r.height - h - 8;

    if(x > maxX) x = Math.max(8, maxX);
    if(y > maxY) y = Math.max(8, maxY);

    tip.style.left = x + "px";
    tip.style.top  = y + "px";
  }

  // mover tooltip
  wrap.addEventListener("mousemove", moveTip);

  // activar tooltip en nombre e hitos
  wrap.querySelectorAll(".nm, .cell.hito").forEach(el => {
    el.addEventListener("mouseenter", () => showTip(el.getAttribute("data-title")));
    el.addEventListener("mouseleave", hideTip);
  });

  // si haces scroll, ocultar para que no se quede “flotando”
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
          const y  = rowEl.offsetTop + BAR_TOP + (BAR_H / 2);
    
          // Hitos: si tipo "FF" -> anclar al fin, si no -> inicio
          let x = (String(h.tipo).toUpperCase() === "FF") ? (ef * PX) : (es * PX);
    
          // Tamaño uniforme del diamante
          const s = 8;
    
          // Evitar recorte en bordes del área visible
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
    
      function selectId(id){
        clearSelection();
        document.querySelectorAll(`.row[data-id="${id}"]`).forEach(el => el.classList.add('selected'));
        drawEdges(id, 1);
      }
    
      // Click in RIGHT pane tasks
      document.querySelectorAll('#gInner .row.task').forEach(el => {
        el.addEventListener('click', () => {
          const id = el.dataset.id;
          if (!id) return;
          selectId(id);
        });
      });
    
      // Click in LEFT pane tasks (optional: allow selecting from table too)
      document.querySelectorAll('#leftBody .row.task').forEach(el => {
        el.addEventListener('click', () => {
          const id = el.dataset.id;
          if (!id) return;
          selectId(id);
        });
      });
    
      // init
      drawHitos();
    </script>
    """)

    html = html_t.safe_substitute(
        LEFT_W=str(left_w),
        GANTT_W=str(gantt_w),
        ROW_H=str(row_h),
        BAR_H=str(row_h - 12),
        OVER_H=str(int(len(dfp) * row_h) + 80),
        PX=str(px_per_unit),
        TICKS=ticks_html,
        TODAY=today_line,
        HEADER_HTML=header_html,
        LEFT_ROWS="".join(left_rows_html),
        GANTT_ROWS="".join(gantt_rows_html),
        EDGES=edges_json,
        HITOS=hitos_json,
    )

    components.html(html, height=650, scrolling=False)

st.divider()
# Persistir estado
st.session_state["cronograma_datos"] = cronograma_datos
