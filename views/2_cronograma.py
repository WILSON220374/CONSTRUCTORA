import streamlit as st
import pandas as pd
import graphviz
import html
import math
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode, GridUpdateMode
import streamlit.components.v1 as components

# =========================
# CSS
# =========================
st.markdown(
    """
<style>
    [data-testid="stDataFrame"] th {
        color: #003366 !important;
        font-weight: bold !important;
        text-transform: uppercase;
    }
</style>
""",
    unsafe_allow_html=True,
)

# Título movido más abajo para que el selector de tipo de proyecto quede primero

# =========================
# Persistencia / estado
# =========================
if "cronograma_datos" not in st.session_state or not isinstance(st.session_state["cronograma_datos"], dict):
    st.session_state["cronograma_datos"] = {}

cronograma_datos = st.session_state["cronograma_datos"]
cronograma_datos.setdefault("escala_tiempo", "DÍAS")
cronograma_datos.setdefault("duraciones", {})  # nid(str) -> int
cronograma_datos.setdefault("aristas", {})     # "o::d" -> {"tipo":"FC","lag":0}

# Pendientes para configuración antes de aplicar
st.session_state.setdefault("pendiente_red", None)       # dict red propuesta
st.session_state.setdefault("pendiente_edges", [])       # lista edge_keys propuestas
st.session_state.setdefault("pendiente_eliminados", [])  # lista edge_keys eliminadas

# Selección de tarea (Relaciones)
st.session_state.setdefault("rel_task_id", None)

# Red aplicada
if "red_dependencias" not in st.session_state:
    red_guardada = cronograma_datos.get("red_dependencias")
    st.session_state["red_dependencias"] = red_guardada if isinstance(red_guardada, dict) else {}

# =========================
# Datos globales
# =========================
alcance = st.session_state.get("alcance_datos", {})
nombre_proyecto = alcance.get("nombre_proyecto", "SIN NOMBRE DEFINIDO")

st.markdown("""
<style>
div[data-testid="stRadio"] label p {
    font-size: 1.55rem !important;
    font-weight: 600 !important;
}
div[data-testid="stRadio"] div[role="radiogroup"] label {
    transform: scale(1.08);
    transform-origin: left center;
}
.tipo-proyecto-titulo {
    font-size: 2.25rem;
    font-weight: 700;
    margin-bottom: 0.35rem;
}
.tipo-proyecto-ayuda {
    font-size: 1.35rem !important;
    line-height: 1.45;
    padding-top: 0.35rem;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="tipo-proyecto-titulo">Tipo de proyecto</div>', unsafe_allow_html=True)

cronograma_datos.setdefault("tipo_presupuesto_proyecto", "Obra")

col_tipo1, col_tipo2 = st.columns([3, 7])
with col_tipo1:
    cronograma_datos["tipo_presupuesto_proyecto"] = st.radio(
        "El proyecto es de:",
        options=["Obra", "Consultoría"],
        index=["Obra", "Consultoría"].index(cronograma_datos.get("tipo_presupuesto_proyecto", "Obra")),
        horizontal=True,
        key="tipo_presupuesto_proyecto_crono",
    )
with col_tipo2:
    st.markdown(
        '<div class="tipo-proyecto-ayuda">Esta selección define en cuál hoja se cargarán los ítems del cronograma.</div>',
        unsafe_allow_html=True,
    )
st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)
st.title("📅 Cronograma")
st.markdown(f"**Proyecto:** {nombre_proyecto}")

col_esc1, col_esc2 = st.columns([3, 7])
with col_esc1:
    cronograma_datos["escala_tiempo"] = st.selectbox(
        "Escala de tiempo del proyecto",
        options=["DÍAS", "SEMANAS", "MESES", "AÑOS"],
        index=["DÍAS", "SEMANAS", "MESES", "AÑOS"].index(cronograma_datos.get("escala_tiempo", "DÍAS")),
        key="escala_tiempo_crono",
    )
with col_esc2:
    st.caption("La escala seleccionada se usa para **Duración** y **Adelanto/Retraso** (lead/lag).")

st.divider()

# ==========================================
# 🚀 MOTOR EXTRACTOR: EDT
# ==========================================
todos_los_nodos = []
nodos_terminales_ids = set()

if "objetivos" in alcance and "edt_data" in alcance:
    for i, obj in enumerate(alcance["objetivos"]):
        oid = obj.get("id")
        cod_obj = f"{i+1}"
        nom_obj = obj.get("texto", "Objetivo")

        todos_los_nodos.append(
            {"id": oid, "codigo": cod_obj, "nombre_puro": nom_obj,
             "es_terminal": False, "padre_id": None, "ruta_completa": "", "nivel_profundidad": 1}
        )

        productos = alcance["edt_data"].get(oid, [])
        for j, p in enumerate(productos):
            pid = p["id"]
            cod_prod = f"{cod_obj}.{j+1}"
            nom_prod = p.get("nombre", "Producto")
            actividades = p.get("actividades", [])
            es_term_p = len(actividades) == 0

            todos_los_nodos.append(
                {"id": pid, "codigo": cod_prod, "nombre_puro": nom_prod,
                 "es_terminal": es_term_p, "padre_id": oid, "ruta_completa": f"{nom_obj}", "nivel_profundidad": 2}
            )
            if es_term_p:
                nodos_terminales_ids.add(pid)

            for k, a in enumerate(actividades):
                aid = a["id"]
                cod_act = f"{cod_prod}.{k+1}"
                nom_act = a.get("nombre", "Actividad")
                paquetes = a.get("paquetes", [])
                es_term_a = len(paquetes) == 0

                todos_los_nodos.append(
                    {"id": aid, "codigo": cod_act, "nombre_puro": nom_act,
                     "es_terminal": es_term_a, "padre_id": pid, "ruta_completa": f"{nom_obj} ➔ {nom_prod}", "nivel_profundidad": 3}
                )
                if es_term_a:
                    nodos_terminales_ids.add(aid)

                for l, pq in enumerate(paquetes):
                    pqid = pq["id"]
                    cod_paq = f"{cod_act}.{l+1}"
                    nom_paq = pq.get("nombre", "Paquete")

                    todos_los_nodos.append(
                        {"id": pqid, "codigo": cod_paq, "nombre_puro": nom_paq,
                         "es_terminal": True, "padre_id": aid, "ruta_completa": f"{nom_obj} ➔ {nom_prod} ➔ {nom_act}", "nivel_profundidad": 4}
                    )
                    nodos_terminales_ids.add(pqid)

if alcance.get("requiere_costos_indirectos", "No") == "Sí":
    costos_indirectos = alcance.get("otros_costos_indirectos_proyecto", []) or []
    if costos_indirectos:
        ci_group_id = "costos_indirectos_proyecto"
        ci_group_code = f"{len(alcance.get('objetivos', [])) + 1}"
        ci_group_name = "COSTOS INDIRECTOS DEL PROYECTO"

        todos_los_nodos.append(
            {
                "id": ci_group_id,
                "codigo": ci_group_code,
                "nombre_puro": ci_group_name,
                "es_terminal": False,
                "padre_id": None,
                "ruta_completa": "",
                "nivel_profundidad": 1,
            }
        )

        for j, ci in enumerate(costos_indirectos):
            ci_id = ci.get("id")
            ci_nombre = ci.get("nombre", "Costo indirecto")
            ci_code = f"{ci_group_code}.{j+1}"

            todos_los_nodos.append(
                {
                    "id": ci_id,
                    "codigo": ci_code,
                    "nombre_puro": ci_nombre,
                    "es_terminal": True,
                    "padre_id": ci_group_id,
                    "ruta_completa": ci_group_name,
                    "nivel_profundidad": 2,
                }
            )
            nodos_terminales_ids.add(ci_id)

# Duración default = 1
for nid in nodos_terminales_ids:
    cronograma_datos["duraciones"].setdefault(str(nid), 1)
# ==========================================
# Helpers
# ==========================================
def edge_key(o, d):
    return f"{o}::{d}"

def ensure_edge_meta(o, d):
    k = edge_key(o, d)
    meta = cronograma_datos["aristas"].get(k)
    if not isinstance(meta, dict):
        meta = {"tipo": "FC", "lag": 0}
        cronograma_datos["aristas"][k] = meta

    if meta.get("tipo") not in ("FC", "CC", "FF", "CF"):
        meta["tipo"] = "FC"
    try:
        meta["lag"] = int(meta.get("lag", 0))
    except Exception:
        meta["lag"] = 0
    return meta

def dur(nid):
    """Duración oficial: PERT redondeada hacia arriba. Si falta O/M/P => 1."""
    rec = (cronograma_datos.get("pert", {}) or {}).get(str(nid), {}) or {}
    O = rec.get("O", None)
    M = rec.get("M", None)
    P = rec.get("P", None)

    if O is None or M is None or P is None:
        return 1

    try:
        val = (float(O) + 4.0 * float(M) + float(P)) / 6.0
    except Exception:
        return 1

    return max(1, int(math.ceil(val)))

def detectar_bucle(grafo):
    visitados = set()
    pila = set()

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

    for nodo_inicio in grafo:
        if nodo_inicio not in visitados:
            if dfs(nodo_inicio):
                return True
    return False

def calc_ES(red_aplicada):
    terminals = list(nodos_terminales_ids)
    edges = []  # (o, d, w): ES_d >= ES_o + w

    for o, dests in red_aplicada.items():
        for d in dests:
            meta = ensure_edge_meta(o, d)
            tipo = meta["tipo"]
            lag = int(meta["lag"])
            di = dur(o)
            dj = dur(d)

            if tipo == "FC":
                w = di + lag
            elif tipo == "CC":
                w = lag
            elif tipo == "FF":
                w = di + lag - dj
            else:  # CF
                w = lag - dj

            edges.append((o, d, w))

    indeg = {t: 0 for t in terminals}
    adj = {t: [] for t in terminals}
    for o, d, w in edges:
        adj.setdefault(o, [])
        adj.setdefault(d, [])
        indeg.setdefault(o, 0)
        indeg.setdefault(d, 0)
        adj[o].append((d, w))
        indeg[d] += 1

    q = [n for n, deg in indeg.items() if deg == 0]
    topo = []
    while q:
        n = q.pop(0)
        topo.append(n)
        for (d, _w) in adj.get(n, []):
            indeg[d] -= 1
            if indeg[d] == 0:
                q.append(d)

    ES = {t: 0 for t in terminals}
    for n in topo:
        for d, w in adj.get(n, []):
            ES[d] = max(ES.get(d, 0), ES.get(n, 0) + w)

    return ES


def calc_slack_y_critica(red_aplicada, aristas, terminales_ids, dur_func):
    """Calcula ES, EF, LS, holgura y conjunto crítico (holgura 0) sobre terminales."""
    # Construir edges con peso w tal que ES[d] >= ES[o] + w
    edges = []
    for o, dests in (red_aplicada or {}).items():
        if o not in terminales_ids:
            continue
        for d in (dests or []):
            if d not in terminales_ids:
                continue
            meta = ensure_edge_meta(o, d)
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

    # Topológico
    indeg = {t: 0 for t in terminales_ids}
    adj = {t: [] for t in terminales_ids}
    rev = {t: [] for t in terminales_ids}
    for o, d, w in edges:
        adj.setdefault(o, [])
        adj[o].append((d, w))
        rev.setdefault(d, [])
        rev[d].append((o, w))
        indeg[d] = indeg.get(d, 0) + 1
        indeg.setdefault(o, indeg.get(o, 0))

    q = [n for n, deg in indeg.items() if deg == 0]
    topo = []
    while q:
        n = q.pop(0)
        topo.append(n)
        for d, _w in adj.get(n, []):
            indeg[d] -= 1
            if indeg[d] == 0:
                q.append(d)

    # Forward: ES
    ES = {t: 0 for t in terminales_ids}
    for n in topo:
        for d, w in adj.get(n, []):
            ES[d] = max(ES.get(d, 0), ES.get(n, 0) + w)

    EF = {t: ES.get(t, 0) + dur_func(t) for t in terminales_ids}
    T = max(EF.values()) if EF else 0

    # Backward: LS con desigualdad LS[o] <= LS[d] - w
    LS = {t: T - dur_func(t) for t in terminales_ids}
    for n in reversed(topo):
        # si n tiene sucesores, limitar LS[n]
        sucs = adj.get(n, [])
        if sucs:
            LS[n] = min(LS[n], min(LS[d] - w for d, w in sucs))

    slack = {t: LS.get(t, 0) - ES.get(t, 0) for t in terminales_ids}
    crit = {t for t, s in slack.items() if s == 0}
    return ES, EF, LS, slack, crit, T

    
# ==========================================
# TOP RUTAS (Top 10) por duración (solo códigos)
# ==========================================
def _code_key(c):
    try:
        return tuple(int(x) for x in str(c).split("."))
    except Exception:
        return (999999,)

def top_k_rutas(red_aplicada, aristas, terminales_ids, dur_func, id_to_codigo, k=10):
    """Devuelve Top-K rutas más largas (inicio→fin) como {'ruta','duracion'} usando tipo/lag."""
    # predecesoras y sucesoras
    succ = {n: [] for n in terminales_ids}
    pred = {n: [] for n in terminales_ids}

    def edge_meta(o, d):
        m = aristas.get(edge_key(o, d), {}) or {}
        tipo = m.get("tipo", "FC")
        lag = m.get("lag", 0)
        if tipo not in ("FC", "CC", "FF", "CF"):
            tipo = "FC"
        try:
            lag = int(lag)
        except Exception:
            lag = 0
        return tipo, lag

    def w_edge(o, d):
        tipo, lag = edge_meta(o, d)
        do = dur_func(o)
        dd = dur_func(d)
        if tipo == "FC":
            return do + lag
        if tipo == "CC":
            return lag
        if tipo == "FF":
            return do + lag - dd
        # CF
        return lag - dd

    edges = []
    for o, dests in (red_aplicada or {}).items():
        if o not in terminales_ids:
            continue
        for d in (dests or []):
            if d not in terminales_ids:
                continue
            w = w_edge(o, d)
            edges.append((o, d, w))
            succ[o].append(d)
            pred[d].append(o)

    inicios = [n for n in terminales_ids if len(pred.get(n, [])) == 0]
    finales = [n for n in terminales_ids if len(succ.get(n, [])) == 0]

    # Topo order
    indeg = {n: 0 for n in terminales_ids}
    adj = {n: [] for n in terminales_ids}
    for o, d, w in edges:
        adj[o].append((d, w))
        indeg[d] += 1

    q = [n for n in terminales_ids if indeg[n] == 0]
    topo = []
    while q:
        n = q.pop(0)
        topo.append(n)
        for d, _w in adj.get(n, []):
            indeg[d] -= 1
            if indeg[d] == 0:
                q.append(d)

    # best[n] = lista top-k de (len, [codigos])
    best = {n: [] for n in terminales_ids}
    for s in inicios:
        best[s] = [(0, [id_to_codigo.get(s, str(s))])]

    for n in topo:
        for d, w in adj.get(n, []):
            cand = []
            for ln, path in best.get(n, []):
                cand.append((ln + w, path + [id_to_codigo.get(d, str(d))]))
            if not cand:
                continue
            merged = best.get(d, []) + cand
            merged.sort(key=lambda x: x[0], reverse=True)

            seen = set()
            cleaned = []
            for ln, pth in merged:
                key = "->".join(pth)
                if key in seen:
                    continue
                seen.add(key)
                cleaned.append((ln, pth))
                if len(cleaned) >= k:
                    break
            best[d] = cleaned

    rutas = []
    for f in finales:
        for ln, pth in best.get(f, []):
            dur_total = ln + dur_func(f)
            rutas.append({"ruta": " → ".join(pth), "duracion": int(dur_total)})

    rutas.sort(key=lambda r: r["duracion"], reverse=True)

    seen = set()
    out = []
    for r in rutas:
        if r["ruta"] in seen:
            continue
        seen.add(r["ruta"])
        out.append(r)
        if len(out) >= k:
            break
    return out



# ==========================================
# Red aplicada (limpia)
# ==========================================
red_actual = st.session_state.get("red_dependencias", {})
if not isinstance(red_actual, dict):
    red_actual = {}

nodos_validos = set(nodos_terminales_ids)

red_limpia = {}
for o, dests in red_actual.items():
    if o in nodos_validos:
        destinos_validos = [d for d in dests if d in nodos_validos]
        if destinos_validos:
            red_limpia[o] = destinos_validos

nodos_red = set(red_actual.keys())
for dests in red_actual.values():
    nodos_red.update(dests)

nodos_eliminados = [nid for nid in nodos_red if nid not in nodos_validos]

for nid_eliminado in nodos_eliminados:
    predecesores_validos = [
        o for o, dests in red_actual.items()
        if o in nodos_validos and nid_eliminado in dests
    ]
    sucesores_validos = [
        d for d in red_actual.get(nid_eliminado, [])
        if d in nodos_validos
    ]

    for pred in predecesores_validos:
        red_limpia.setdefault(pred, [])
        for suc in sucesores_validos:
            if suc != pred and suc not in red_limpia[pred]:
                red_limpia[pred].append(suc)

st.session_state["red_dependencias"] = red_limpia
red_aplicada = st.session_state["red_dependencias"]

# Base para Relaciones: si hay pendiente, usamos pendiente; si no, aplicada
red_base = st.session_state["pendiente_red"] if isinstance(st.session_state.get("pendiente_red"), dict) else red_aplicada

# Diccionarios rápidos
dict_cod_to_id = {n["codigo"]: n["id"] for n in todos_los_nodos if n["es_terminal"]}
dict_id_to_cod = {n["id"]: n["codigo"] for n in todos_los_nodos}
dict_id_to_nom = {n["id"]: n["nombre_puro"] for n in todos_los_nodos}

# ==========================================
# 🎨 COLORES POR PADRE
# ==========================================
paleta_colores = [
    "#aed6f1", "#f8c471", "#abebc6", "#d7bde2", "#f5b041", "#85c1e9",
    "#f1948a", "#82e0aa", "#e59866", "#bb8fce", "#76d7c4", "#f7dc6f"
]
color_padres = {}
contador_color = 0
for nodo in todos_los_nodos:
    if nodo["es_terminal"]:
        padre = nodo["padre_id"]
        if padre not in color_padres:
            color_padres[padre] = paleta_colores[contador_color % len(paleta_colores)]
            contador_color += 1

# ==========================================
# Tabs
# ==========================================
tab_red = st.container()  # Hoja única: Diagrama de Red

# ==========================================================
# TAB 1: Diagrama de Red
# ==========================================================
with tab_red:
    st.header("🕸️ Construcción de Secuencias")

    if not todos_los_nodos:
        st.warning("⚠️ No hay EDT definida. Ve a Alcance.")
    else:
        c_inst, c_casc = st.columns([7, 3])
        c_inst.info("💡 Edita PREDECESORAS (códigos separados por coma) y DURACIÓN. Luego actualiza.")

        # ✅ Cascada
        if c_casc.button("🌊 Enlazar Todo en Cascada", use_container_width=True):
            nueva_red_cascada = {}
            terminales_lista = [n["id"] for n in todos_los_nodos if n["es_terminal"]]
            for idx in range(len(terminales_lista) - 1):
                nueva_red_cascada.setdefault(terminales_lista[idx], [])
                nueva_red_cascada[terminales_lista[idx]].append(terminales_lista[idx + 1])

            st.session_state["red_dependencias"] = nueva_red_cascada
            cronograma_datos["red_dependencias"] = nueva_red_cascada
            st.session_state["pendiente_red"] = None
            st.session_state["pendiente_edges"] = []
            st.session_state["pendiente_eliminados"] = []
            st.rerun()

        # =========================
        # Panel único de precedencias (Tipo / Lag) - Edición aquí (sin hoja Relaciones)
        # =========================
        st.subheader("🔗 Precedencias (Tipo y Lag)")

        # lista de tareas terminales para selector (código + nombre)
        terminal_ids = [n["id"] for n in todos_los_nodos if n.get("es_terminal")]
        def _key_cod_from_id(_id):
            cod = dict_id_to_cod.get(_id, "0")
            return tuple(int(p) if p.isdigit() else 0 for p in str(cod).split("."))

        terminal_ids = sorted(terminal_ids, key=_key_cod_from_id)

        if terminal_ids:
            st.session_state.setdefault("task_precedencia_id", terminal_ids[0])

            task_id = st.selectbox(
                "Seleccione la tarea terminal a configurar:",
                options=terminal_ids,
                index=terminal_ids.index(st.session_state["task_precedencia_id"]) if st.session_state["task_precedencia_id"] in terminal_ids else 0,
                format_func=lambda _id: f'{dict_id_to_cod.get(_id,"")} — {dict_id_to_nom.get(_id,"")}',
                key="task_precedencia_id",
            )

            # predecesoras según red aplicada
            preds = [orig for orig, sucs in red_aplicada.items() if task_id in sucs]
            preds = sorted(preds, key=_key_cod_from_id)

            if not preds:
                st.info("Esta tarea no tiene predecesoras. Defínalas en la columna PREDECESORAS y oprima 'Actualizar Red'.")
            else:
                st.caption("La edición se guarda al instante. Escala del lag: " + str(cronograma_datos.get("escala_tiempo", "DÍAS")))
                tipos = ["FC", "CC", "FF", "CF"]

                for pid in preds:
                    meta = ensure_edge_meta(pid, task_id)

                    c1, c2, c3 = st.columns([6, 2, 2])
                    with c1:
                        st.write(f'**{dict_id_to_cod.get(pid,"")} — {dict_id_to_nom.get(pid,"")}**')
                    with c2:
                        nuevo_tipo = st.selectbox(
                            "Tipo",
                            options=tipos,
                            index=tipos.index(meta["tipo"]) if meta.get("tipo") in tipos else 0,
                            key=f"tipo_{pid}_{task_id}",
                            label_visibility="collapsed",
                        )
                    with c3:
                        nuevo_lag = st.number_input(
                            "Lag",
                            value=int(meta.get("lag", 0)),
                            step=1,
                            key=f"lag_{pid}_{task_id}",
                            label_visibility="collapsed",
                        )

                    # guardar al instante
                    if nuevo_tipo != meta.get("tipo") or int(nuevo_lag) != int(meta.get("lag", 0)):
                        meta["tipo"] = nuevo_tipo
                        meta["lag"] = int(nuevo_lag)

        st.divider()
        # Tabla editable
        datos_tabla = []
        for nodo in todos_los_nodos:
            nid = nodo["id"]
            if nodo["es_terminal"]:
                preds_ids = [orig for orig, sucs in red_aplicada.items() if nid in sucs]
                preds_cods = [dict_id_to_cod.get(pid, "") for pid in preds_ids]
                sucs_ids = red_aplicada.get(nid, [])
                sucs_cods = [dict_id_to_cod.get(sid, "") for sid in sucs_ids]
                str_preds = ", ".join([c for c in preds_cods if c])
                str_sucs = ", ".join([c for c in sucs_cods if c])
                dur_val = dur(nid)
                # Resumen de precedencias (Tipo/Lag) alineado con PREDECESORAS
                preds_orden = sorted(preds_ids, key=lambda _pid: tuple(int(p) if p.isdigit() else 0 for p in str(dict_id_to_cod.get(_pid, "0")).split(".")))
                tipos_list = []
                lags_list = []
                for _pid in preds_orden:
                    _meta = ensure_edge_meta(_pid, nid)
                    tipos_list.append(str(_meta.get("tipo", "FC")))
                    lags_list.append(str(int(_meta.get("lag", 0))))
                str_tipos = ", ".join(tipos_list)
                str_lags = ", ".join(lags_list)
            else:
                str_preds = ""
                str_sucs = ""
                dur_val = ""
                str_tipos = ""
                str_lags = ""

            datos_tabla.append({
                "ID_Oculto": nid,
                "es_terminal": nodo["es_terminal"],
                "nivel_profundidad": nodo["nivel_profundidad"],
                "CÓDIGO": nodo["codigo"],
                "ESTRUCTURA DE DESGLOSE (EDT)": nodo["nombre_puro"],
                "DURACIÓN": dur_val,
                "PREDECESORAS (Editar ✏️)": str_preds,
                "TIPO (Resumen)": str_tipos,
                "LAG (Resumen)": str_lags,
                "SUCESORAS (Auto 🔒)": str_sucs
            })

        df = pd.DataFrame(datos_tabla)

        gb = GridOptionsBuilder.from_dataframe(df)
        gb.configure_column("ID_Oculto", hide=True)
        gb.configure_column("es_terminal", hide=True)
        gb.configure_column("nivel_profundidad", hide=True)
        gb.configure_column("CÓDIGO", editable=False, width=110)
        gb.configure_column("ESTRUCTURA DE DESGLOSE (EDT)", editable=False, width=320)

        editable_term_js = JsCode("function(params){ return params.data.es_terminal === true; }")
        gb.configure_column("DURACIÓN", editable=False, width=110)
        gb.configure_column("PREDECESORAS (Editar ✏️)", editable=editable_term_js, width=260)
        gb.configure_column("TIPO (Resumen)", editable=False, width=140)
        gb.configure_column("LAG (Resumen)", editable=False, width=140)
        gb.configure_column("SUCESORAS (Auto 🔒)", editable=False, width=220)

        row_style_js = JsCode(
            """
        function(params) {
            if (params.data.es_terminal === true) {
                return { 'background-color': '#ffffff', 'color': '#000000' };
            } else if (params.data.nivel_profundidad === 1) {
                return { 'background-color': '#d5d8dc', 'color': '#000000', 'font-weight': 'bold' };
            } else if (params.data.nivel_profundidad === 2) {
                return { 'background-color': '#e5e7e9', 'color': '#000000', 'font-weight': 'bold' };
            } else if (params.data.nivel_profundidad === 3) {
                return { 'background-color': '#f2f4f4', 'color': '#000000' };
            } else {
                return { 'background-color': '#f8f9f9', 'color': '#000000' };
            }
        }
        """
        )
        gb.configure_grid_options(getRowStyle=row_style_js)
        gridOptions = gb.build()

        n_filas = len(df)
        alto_fila = 32
        alto_header = 38
        margen = 16
        alto_max = 750
        altura_grid = min(alto_header + margen + (n_filas * alto_fila), alto_max)

        ag = AgGrid(
            df,
            gridOptions=gridOptions,
            update_mode=GridUpdateMode.VALUE_CHANGED,
            allow_unsafe_jscode=True,
            theme="streamlit",
            height=altura_grid,
            fit_columns_on_grid_load=True,
        )

        if st.button("🔄 Actualizar Red y Verificar", type="primary"):

            df_edit = ag["data"]

            # Red propuesta
            nueva_red = {}
            cod_err = []
            for _, row in df_edit.iterrows():
                dest = row["ID_Oculto"]
                if dest in nodos_terminales_ids:
                    preds_str = str(row.get("PREDECESORAS (Editar ✏️)", "")).strip()
                    if preds_str and preds_str not in ("nan", "None"):
                        cods = [c.strip() for c in preds_str.split(",") if c.strip()]
                        for cod in cods:
                            if cod in dict_cod_to_id:
                                ori = dict_cod_to_id[cod]
                                if ori != dest:
                                    nueva_red.setdefault(ori, [])
                                    if dest not in nueva_red[ori]:
                                        nueva_red[ori].append(dest)
                            else:
                                cod_err.append(cod)

            if detectar_bucle(nueva_red):
                st.error("🚨 Dependencia circular detectada. Corrige los códigos.")
                st.stop()

            actuales = set(edge_key(o, d) for o, ds in red_aplicada.items() for d in ds)
            propuestos = set(edge_key(o, d) for o, ds in nueva_red.items() for d in ds)

            for k in (propuestos - actuales):
                cronograma_datos["aristas"].setdefault(k, {"tipo": "FC", "lag": 0})

            # APLICACIÓN INMEDIATA (sin red pendiente)
            st.session_state["red_dependencias"] = nueva_red
            cronograma_datos["red_dependencias"] = nueva_red
            st.session_state["pendiente_red"] = None
            st.session_state["pendiente_edges"] = []
            st.session_state["pendiente_eliminados"] = []

            if cod_err:
                st.warning(f"⚠️ Códigos ignorados: {', '.join(sorted(set(cod_err)))}")

            st.success("✅ Red actualizada. El diagrama se ha recalculado con FC y 0 por defecto en relaciones nuevas.")
            st.rerun()

        # ======== Gráfico ========
        st.divider()
        st.markdown("#### 🗺️ DIAGRAMA DE RED")

        opciones_foco = ["Ver Todo"] + [n["id"] for n in todos_los_nodos if n["es_terminal"]]
        foco = st.selectbox(
            "🔦 Modo Foco (Analizar Impacto):",
            options=opciones_foco,
            format_func=lambda x: "Ver Todo el Proyecto" if x == "Ver Todo" else f"{dict_id_to_cod.get(x,'')} - {dict_id_to_nom.get(x,'')}",
            key="foco_red_tab1",
        )

        if not any(len(v) for v in red_aplicada.values()):
            st.info("Aún no has enlazado ninguna tarea.")
        elif detectar_bucle(red_aplicada):
            st.error("🚨 Hay un bucle. Corrige dependencias.")
        else:
            dot = graphviz.Digraph(engine="dot")
            dot.attr(rankdir="LR", bgcolor="white")
            aristas = cronograma_datos.get("aristas", {}) or {}
            cronograma_datos["aristas"] = aristas
            ES, EF, LS, slack, crit, T_proy = calc_slack_y_critica(red_aplicada, aristas, nodos_terminales_ids, dur)
            # --- RUTA CRÍTICA (terminales) + TOP 10 RUTAS ---
            st.markdown(f"**Duración total del proyecto:** {int(T_proy)} {cronograma_datos.get('escala_tiempo','DÍAS')}")

            # Ruta crítica (solo códigos)
            crit_codes = sorted([dict_id_to_cod.get(n, "") for n in crit], key=_code_key)
            if crit_codes:
                st.markdown("**Ruta crítica (holgura 0):**")
                st.success(" → ".join([c for c in crit_codes if c]))
            else:
                st.info("No se identificaron actividades con holgura 0.")

            # Top 10 rutas más largas (inicios→finales), solo códigos
            rutas_top = top_k_rutas(
                red_aplicada=red_aplicada,
                aristas=aristas,
                terminales_ids=nodos_terminales_ids,
                dur_func=dur,
                id_to_codigo=dict_id_to_cod,
                k=10,
            )

            st.markdown("**Rutas de ejecución proyecto :**")
            if rutas_top:
                df_rutas = pd.DataFrame(
                    [{"RUTA": f"Ruta {i+1}", "DURACIÓN": r["duracion"], "SECUENCIA (CÓDIGOS)": r["ruta"]}
                     for i, r in enumerate(rutas_top)]
                )
                st.dataframe(df_rutas, use_container_width=True, hide_index=True)
            else:
                st.info("No se encontraron rutas completas (inicio→fin).")
            nodos_iluminados = set()
            if foco != "Ver Todo":
                nodos_iluminados.add(foco)
                for o, dests in red_aplicada.items():
                    if foco in dests:
                        nodos_iluminados.add(o)
                for d in red_aplicada.get(foco, []):
                    nodos_iluminados.add(d)

            tiene_pred = {nid: False for nid in nodos_terminales_ids}
            tiene_suc = {nid: len(red_aplicada.get(nid, [])) > 0 for nid in nodos_terminales_ids}
            for sucs in red_aplicada.values():
                for s in sucs:
                    tiene_pred[s] = True

            for nodo in todos_los_nodos:
                if not nodo["es_terminal"]:
                    continue
                nid = nodo["id"]

                es_huerfana = not tiene_pred[nid] and not tiene_suc[nid]
                es_inicio = not tiene_pred[nid] and tiene_suc[nid]
                es_fin = tiene_pred[nid] and not tiene_suc[nid]

                if foco != "Ver Todo" and nid not in nodos_iluminados:
                    fill = "#f8f9f9"
                    fcolor = "#bdc3c7"
                    bcolor = "#ecf0f1"
                else:
                    fcolor = "#17202a"
                    if es_huerfana:
                        fill = "#ffffff"
                        bcolor = "#e74c3c"
                    elif es_inicio:
                        fill = "#d5f5e3"
                        bcolor = "#27ae60"
                    elif es_fin:
                        fill = "#fadbd8"
                        bcolor = "#c0392b"
                    else:
                        fill = color_padres.get(nodo["padre_id"], "#e5e7e9")
                        bcolor = "#34495e"

                # --- NUEVO LABEL: 2 líneas, sin ruta/padre ---
                nombre_raw = str(nodo["nombre_puro"])
                nombre_txt = (nombre_raw[:25] + "...") if len(nombre_raw) > 25 else nombre_raw

                label = f'<<FONT POINT-SIZE="16" COLOR="{fcolor}"><B>{html.escape(str(nodo["codigo"]))}</B></FONT>'
                label += f'<BR/><FONT POINT-SIZE="11" COLOR="{fcolor}">{html.escape(nombre_txt)}</FONT>'

                if es_huerfana:
                    label += '<BR/><FONT COLOR="#c0392b" POINT-SIZE="10"><B>(Sin enlazar)</B></FONT>'

                label += ">"

                dot.node(
                    str(nid),
                    label=label,
                    shape="box",
                    style="filled",
                    fillcolor=fill,
                    color=("#c0392b" if nid in crit else bcolor),
                    penwidth=("3" if nid in crit else "1.5"),
                    fontname="Helvetica",
                    margin="0.12,0.06",
                )

           # Alinear por ES SOLO cuando no hay foco (Ver Todo)
            if foco == "Ver Todo":
                buckets = {}
                for nid in nodos_terminales_ids:
                    buckets.setdefault(int(ES.get(nid, 0)), []).append(nid)

                for esv, nodes in sorted(buckets.items(), key=lambda x: x[0]):
                    with dot.subgraph() as s:
                        s.attr(rank="same")
                        for nid in nodes:
                            s.node(str(nid))

            for o, ds in red_aplicada.items():
                for d in ds:
                    col = "#7f8c8d"
                    if foco != "Ver Todo":
                        if o not in nodos_iluminados or d not in nodos_iluminados:
                            col = "#f2f4f4"
                    meta = ensure_edge_meta(o, d)
                    etiqueta = f"{meta['tipo']} {int(meta['lag']):+d}"
                    dot.edge(str(o), str(d), color=col, penwidth="1.5", label=etiqueta, fontsize="10", fontcolor="#2c3e50")

            svg = dot.pipe(format="svg").decode("utf-8")
            components.html(
                f"""
                <div style="width:100%; height:650px; overflow:auto; border:1px solid #e6e6e6; border-radius:10px; padding:8px; background:white;">
                    {svg}
                </div>
                """,
                height=670,
                scrolling=True,
            )

# ==========================================================
# TAB 2: Relaciones (Tipo de precedencia y Lag) — selector robusto
# ==========================================================

# =========================
# Guardar estado
# =========================
cronograma_datos["red_dependencias"] = st.session_state.get("red_dependencias", {})
st.session_state["cronograma_datos"] = cronograma_datos
