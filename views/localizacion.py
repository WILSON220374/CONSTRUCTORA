import math
from copy import deepcopy
from uuid import uuid4

import plotly.graph_objects as go
import streamlit as st

from session_state import init_session_state
from supabase_state import cargar_estado, guardar_estado


st.set_page_config(page_title="Localización", layout="wide")
init_session_state()


CRITERIOS_BASE = [
    {"factor": "Cercanía de fuentes de abastecimiento", "tipo": "Objetivo", "editable": False},
    {"factor": "Disponibilidad de servicios públicos domiciliarios (agua, energía y otros)", "tipo": "Objetivo", "editable": False},
    {"factor": "Estructura impositiva y legal", "tipo": "Objetivo", "editable": False},
    {"factor": "Orden público", "tipo": "Objetivo", "editable": False},
    {"factor": "Topografía", "tipo": "Objetivo", "editable": False},
    {"factor": "Cercanía a la población objetivo", "tipo": "Objetivo", "editable": False},
    {"factor": "Comunicaciones", "tipo": "Objetivo", "editable": False},
    {"factor": "Costo y disponibilidad de terrenos", "tipo": "Objetivo", "editable": False},
    {"factor": "Disponibilidad y costo de mano de obra", "tipo": "Objetivo", "editable": False},
    {"factor": "Impacto para la equidad de género", "tipo": "Subjetivo", "editable": False},
    {"factor": "Aspectos administrativos y políticos", "tipo": "Subjetivo", "editable": False},
    {"factor": "Factores ambientales", "tipo": "Subjetivo", "editable": False},
    {"factor": "Medios y costos de transporte", "tipo": "Subjetivo", "editable": False},
    {"factor": "Otros", "tipo": "Subjetivo", "editable": True},
]


def nueva_localizacion(nombre: str) -> dict:
    return {
        "id": f"loc_{uuid4().hex[:8]}",
        "nombre": nombre,
    }


def nuevo_factor(base: dict, localizaciones: list[dict]) -> dict:
    return {
        "id": f"fac_{uuid4().hex[:8]}",
        "factor": base["factor"],
        "tipo": base["tipo"],
        "editable": base["editable"],
        "aplica": False,
        "ponderacion": 0.0,
        "calificaciones": {loc["id"]: None for loc in localizaciones},
    }


def payload_vacio() -> dict:
    localizaciones = [
        nueva_localizacion("Localización 1"),
        nueva_localizacion("Localización 2"),
    ]
    return {
        "nombre_proyecto": "",
        "localizaciones": localizaciones,
        "factores": [nuevo_factor(base, localizaciones) for base in CRITERIOS_BASE],
        "totales": {loc["id"]: 0.0 for loc in localizaciones},
        "ranking": [],
        "seleccionada": {},
        "validacion": {
            "suma_ponderacion": 0.0,
            "ponderacion_ok": False,
        },
    }


def normalizar_payload(payload: dict | None) -> dict:
    data = deepcopy(payload) if isinstance(payload, dict) else payload_vacio()

    if "localizaciones" not in data or not isinstance(data["localizaciones"], list) or len(data["localizaciones"]) < 2:
        data["localizaciones"] = [
            nueva_localizacion("Localización 1"),
            nueva_localizacion("Localización 2"),
        ]

    if "factores" not in data or not isinstance(data["factores"], list) or len(data["factores"]) == 0:
        data["factores"] = [nuevo_factor(base, data["localizaciones"]) for base in CRITERIOS_BASE]

    loc_ids = [loc["id"] for loc in data["localizaciones"]]

    for i, factor in enumerate(data["factores"]):
        factor.setdefault("id", f"fac_{uuid4().hex[:8]}")
        factor.setdefault("factor", CRITERIOS_BASE[i]["factor"] if i < len(CRITERIOS_BASE) else f"Factor {i + 1}")
        factor.setdefault("tipo", CRITERIOS_BASE[i]["tipo"] if i < len(CRITERIOS_BASE) else "Objetivo")
        factor.setdefault("editable", CRITERIOS_BASE[i]["editable"] if i < len(CRITERIOS_BASE) else False)
        factor.setdefault("aplica", False)
        factor.setdefault("ponderacion", 0.0)
        factor.setdefault("calificaciones", {})

        nuevas_calificaciones = {}
        for loc_id in loc_ids:
            nuevas_calificaciones[loc_id] = factor["calificaciones"].get(loc_id, None)
        factor["calificaciones"] = nuevas_calificaciones

    data.setdefault("totales", {loc_id: 0.0 for loc_id in loc_ids})
    data.setdefault("ranking", [])
    data.setdefault("seleccionada", {})
    data.setdefault(
        "validacion",
        {
            "suma_ponderacion": 0.0,
            "ponderacion_ok": False,
        },
    )

    return data


def recalcular(data: dict) -> dict:
    locs = data["localizaciones"]
    factors = data["factores"]

    totales = {loc["id"]: 0.0 for loc in locs}
    suma_ponderacion = 0.0

    for factor in factors:
        aplica = bool(factor.get("aplica", False))
        ponderacion = float(factor.get("ponderacion", 0) or 0)

        if not aplica:
            ponderacion = 0.0
            factor["ponderacion"] = 0.0

        suma_ponderacion += ponderacion

        for loc in locs:
            loc_id = loc["id"]
            calif = factor["calificaciones"].get(loc_id, None)

            if not aplica or calif in (None, ""):
                continue

            try:
                calif_num = float(calif)
            except Exception:
                continue

            puntaje = (ponderacion / 100.0) * calif_num
            totales[loc_id] += puntaje

    ranking = []
    for loc in locs:
        ranking.append(
            {
                "id": loc["id"],
                "nombre": (loc["nombre"] or "").strip() or "Sin nombre",
                "puntaje": round(totales.get(loc["id"], 0.0), 4),
            }
        )

    ranking.sort(key=lambda x: x["puntaje"], reverse=True)
    seleccionada = ranking[0] if ranking else {}

    data["totales"] = totales
    data["ranking"] = ranking
    data["seleccionada"] = seleccionada
    data["validacion"] = {
        "suma_ponderacion": round(suma_ponderacion, 4),
        "ponderacion_ok": math.isclose(suma_ponderacion, 100.0, rel_tol=0, abs_tol=0.0001),
    }

    return data


def cargar_localizacion() -> dict:
    if "localizacion_datos" in st.session_state and isinstance(st.session_state["localizacion_datos"], dict):
        data = normalizar_payload(st.session_state["localizacion_datos"])
        st.session_state["localizacion_datos"] = data
        return data

    data = cargar_estado("localizacion")
    data = normalizar_payload(data)
    st.session_state["localizacion_datos"] = data
    return data


def guardar_localizacion(data: dict) -> None:
    st.session_state["localizacion_datos"] = data
    guardar_estado("localizacion", data)

    payload_todo = {
        "integrantes": st.session_state.get("integrantes", []),
        "alcance_datos": st.session_state.get("alcance_datos", {}),
        "informes_config": st.session_state.get("informes_config", {}),
        "cronograma_datos": st.session_state.get("cronograma_datos", {}),
        "localizacion_datos": st.session_state.get("localizacion_datos", {}),
    }
    guardar_estado("todo", payload_todo)


def hay_localizaciones_sin_nombre(data: dict) -> bool:
    return any(not (loc.get("nombre") or "").strip() for loc in data["localizaciones"])


def hay_calificaciones_faltantes(data: dict) -> bool:
    for factor in data["factores"]:
        if factor.get("aplica", False):
            for loc in data["localizaciones"]:
                if factor["calificaciones"].get(loc["id"], None) in (None, ""):
                    return True
    return False


localizacion_datos = cargar_localizacion()
nombre_proyecto = st.session_state.get("alcance_datos", {}).get("nombre_proyecto", "").strip()
localizacion_datos["nombre_proyecto"] = nombre_proyecto
localizacion_datos = recalcular(localizacion_datos)
st.session_state["localizacion_datos"] = localizacion_datos


st.markdown(
    """
    <style>
    .loc-card{
        border:1px solid #E5E7EB;
        border-radius:14px;
        padding:14px;
        background:#FFFFFF;
        box-shadow:0 1px 4px rgba(0,0,0,.05);
        margin-bottom:10px;
    }
    .loc-title{
        font-size:15px;
        font-weight:700;
        color:#0B3D2E;
        margin-bottom:8px;
    }
    .result-card{
        border:1px solid #D1FAE5;
        border-radius:14px;
        padding:16px;
        background:#F0FDF4;
        margin-bottom:12px;
    }
    .result-label{
        font-size:12px;
        color:#4B5563;
        margin-bottom:4px;
    }
    .result-value{
        font-size:20px;
        font-weight:700;
        color:#145A32;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


st.markdown("## LOCALIZACIÓN")
if nombre_proyecto:
    st.markdown(f"### {nombre_proyecto}")


st.markdown("### Alternativas de localización")

col_add, col_save = st.columns([1, 1])

with col_add:
    if st.button("➕ Agregar localización", use_container_width=True):
        nuevas = deepcopy(st.session_state["localizacion_datos"])
        idx = len(nuevas["localizaciones"]) + 1
        nueva = nueva_localizacion(f"Localización {idx}")
        nuevas["localizaciones"].append(nueva)
        for factor in nuevas["factores"]:
            factor["calificaciones"][nueva["id"]] = None
        nuevas = recalcular(nuevas)
        guardar_localizacion(nuevas)
        st.rerun()

with col_save:
    if st.button("💾 Guardar localización", use_container_width=True):
        data = recalcular(deepcopy(st.session_state["localizacion_datos"]))
        guardar_localizacion(data)
        st.success("Localización guardada.")


locs = st.session_state["localizacion_datos"]["localizaciones"]
cols_locs = st.columns(len(locs))

for i, loc in enumerate(locs):
    with cols_locs[i]:
        st.markdown(
            f"<div class='loc-card'><div class='loc-title'>Alternativa {i + 1}</div></div>",
            unsafe_allow_html=True,
        )

        nuevo_nombre = st.text_input(
            "Nombre",
            value=loc["nombre"],
            key=f"nombre_{loc['id']}",
            label_visibility="collapsed",
            placeholder=f"Localización {i + 1}",
        )
        st.session_state["localizacion_datos"]["localizaciones"][i]["nombre"] = nuevo_nombre

        puede_borrar = len(st.session_state["localizacion_datos"]["localizaciones"]) > 2
        if st.button("🗑️ Eliminar", key=f"del_{loc['id']}", use_container_width=True, disabled=not puede_borrar):
            nuevas = deepcopy(st.session_state["localizacion_datos"])
            nuevas["localizaciones"] = [x for x in nuevas["localizaciones"] if x["id"] != loc["id"]]
            for factor in nuevas["factores"]:
                factor["calificaciones"].pop(loc["id"], None)
            nuevas = recalcular(nuevas)
            guardar_localizacion(nuevas)
            st.rerun()


st.markdown("### Matriz de evaluación")
st.caption("Califique cada criterio en escala de 1 a 5, donde 1 es la menor valoración y 5 la mayor.")

data = recalcular(deepcopy(st.session_state["localizacion_datos"]))
st.session_state["localizacion_datos"] = data

if data["validacion"]["ponderacion_ok"]:
    st.success(f"La ponderación total es {data['validacion']['suma_ponderacion']:.2f}%")
else:
    st.error(f"La ponderación total actual es {data['validacion']['suma_ponderacion']:.2f}%. Debe ser exactamente 100%.")

## Fila 1: encabezados agrupados
enc_top = st.columns(
    [3.8, 0.8, 1.0, len(data["localizaciones"]) * 0.9, len(data["localizaciones"]) * 1.0]
)
enc_top[0].markdown("**Factor**")
enc_top[1].markdown("**Aplica**")
enc_top[2].markdown("**Ponderación (%)**")
enc_top[3].markdown(
    """
    <div style="
        background:#EAF4EC;
        border:1px solid #D1E7D3;
        border-radius:10px;
        padding:10px 12px;
        text-align:center;
        font-weight:700;
        color:#145A32;
        width:100%;
    ">
        Calificación
    </div>
    """,
    unsafe_allow_html=True,
)
enc_top[4].markdown(
    """
    <div style="
        background:#EEF4FF;
        border:1px solid #D6E4FF;
        border-radius:10px;
        padding:10px 12px;
        text-align:center;
        font-weight:700;
        color:#1D4ED8;
        width:100%;
    ">
        Puntajes
    </div>
    """,
    unsafe_allow_html=True,
)

# Fila 2: nombres de localizaciones
enc_cols = st.columns(
    [3.8, 0.8, 1.0]
    + [0.9 for _ in data["localizaciones"]]
    + [1.0 for _ in data["localizaciones"]]
)
enc_cols[0].markdown("")
enc_cols[1].markdown("")
enc_cols[2].markdown("")

j = 3
for i, loc in enumerate(data["localizaciones"]):
    nombre_loc = (loc["nombre"] or "").strip() or "Sin nombre"
    enc_cols[j + i].markdown(f"<div style='text-align:center; font-weight:700;'>{nombre_loc}</div>", unsafe_allow_html=True)

j = 3 + len(data["localizaciones"])
for i, loc in enumerate(data["localizaciones"]):
    nombre_loc = (loc["nombre"] or "").strip() or "Sin nombre"
    enc_cols[j + i].markdown(f"<div style='text-align:center; font-weight:700;'>{nombre_loc}</div>", unsafe_allow_html=True)

st.divider()

for grupo in ["Objetivo", "Subjetivo"]:
    st.markdown(f"#### Factores {grupo.lower()}s")

    for idx_factor, factor in enumerate(st.session_state["localizacion_datos"]["factores"]):
        if factor["tipo"] != grupo:
            continue

        cols = st.columns(
            [3.8, 0.8, 1.0]
            + [0.9 for _ in data["localizaciones"]]
            + [1.0 for _ in data["localizaciones"]]
        )

        if factor.get("editable", False):
            nuevo_factor = cols[0].text_input(
                "Factor",
                value=factor["factor"],
                key=f"factor_{factor['id']}",
                label_visibility="collapsed",
            )
            st.session_state["localizacion_datos"]["factores"][idx_factor]["factor"] = nuevo_factor
        else:
            cols[0].write(factor["factor"])

        aplica = cols[1].checkbox(
            "Aplica",
            value=bool(factor.get("aplica", False)),
            key=f"aplica_{factor['id']}",
            label_visibility="collapsed",
        )
        st.session_state["localizacion_datos"]["factores"][idx_factor]["aplica"] = aplica

        ponderacion_actual = float(factor.get("ponderacion", 0) or 0)
        ponderacion = cols[2].number_input(
            "Ponderación",
            min_value=0.0,
            max_value=100.0,
            value=ponderacion_actual,
            step=0.5,
            key=f"pond_{factor['id']}",
            label_visibility="collapsed",
            disabled=not aplica,
        )
        st.session_state["localizacion_datos"]["factores"][idx_factor]["ponderacion"] = 0.0 if not aplica else float(ponderacion)

        col_inicio_calif = 3
        col_inicio_puntaje = 3 + len(data["localizaciones"])
        puntajes_fila = {}

        for i, loc in enumerate(data["localizaciones"]):
            loc_id = loc["id"]
            calif_actual = st.session_state["localizacion_datos"]["factores"][idx_factor]["calificaciones"].get(loc_id, None)
            valor_inicial = 1 if calif_actual in (None, "") else int(calif_actual)

            calif = cols[col_inicio_calif + i].selectbox(
                "Calificación",
                options=[1, 2, 3, 4, 5],
                index=[1, 2, 3, 4, 5].index(valor_inicial),
                key=f"calif_{factor['id']}_{loc_id}",
                label_visibility="collapsed",
                disabled=not aplica,
            )

            st.session_state["localizacion_datos"]["factores"][idx_factor]["calificaciones"][loc_id] = None if not aplica else int(calif)

            factor_ref = st.session_state["localizacion_datos"]["factores"][idx_factor]
            pond_ref = float(factor_ref.get("ponderacion", 0) or 0)
            cal_ref = factor_ref["calificaciones"].get(loc_id, None)

            puntaje = 0.0 if (not aplica or cal_ref in (None, "")) else (pond_ref / 100.0) * float(cal_ref)
            puntajes_fila[loc_id] = puntaje

        max_puntaje = max(puntajes_fila.values()) if puntajes_fila else 0.0

        for i, loc in enumerate(data["localizaciones"]):
            loc_id = loc["id"]
            puntaje = puntajes_fila.get(loc_id, 0.0)

            if aplica and max_puntaje > 0 and math.isclose(puntaje, max_puntaje, rel_tol=0, abs_tol=0.0001):
                cols[col_inicio_puntaje + i].markdown(
                    f"<div style='width:100%; min-height:38px; display:flex; align-items:center; justify-content:center; background:#DCFCE7; color:#166534; padding:8px 10px; border-radius:8px; font-weight:700; text-align:center; box-sizing:border-box;'>{puntaje:.2f}</div>",
                    unsafe_allow_html=True,
                )
            else:
                cols[col_inicio_puntaje + i].markdown(
                    f"<div style='width:100%; min-height:38px; display:flex; align-items:center; justify-content:center; padding:8px 10px; border-radius:8px; font-weight:700; text-align:center; box-sizing:border-box;'>{puntaje:.2f}</div>",
                    unsafe_allow_html=True,
                )
    st.divider()


data = recalcular(deepcopy(st.session_state["localizacion_datos"]))
st.session_state["localizacion_datos"] = data

if hay_localizaciones_sin_nombre(data):
    st.warning("Todas las localizaciones deben tener nombre.")

if hay_calificaciones_faltantes(data):
    st.warning("Hay factores aplicables con calificaciones faltantes.")

if not data["validacion"]["ponderacion_ok"]:
    st.warning("La suma de ponderaciones debe ser exactamente 100%.")


st.markdown("### Resultado final")

seleccionada = data.get("seleccionada", {})
nombre_sel = seleccionada.get("nombre", "Sin definir")
puntaje_sel = seleccionada.get("puntaje", 0.0)

st.markdown(
    f"""
    <div class="result-card">
        <div class="result-label">Ubicación seleccionada</div>
        <div class="result-value">{nombre_sel}</div>
        <div class="result-label">Puntaje: {puntaje_sel:.4f}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("#### Ranking de localizaciones")
if data["ranking"]:
    filas = []
    for pos, item in enumerate(data["ranking"], start=1):
        filas.append(
            {
                "Posición": pos,
                "Localización": item["nombre"],
                "Puntaje": round(item["puntaje"], 4),
            }
        )
    st.dataframe(filas, use_container_width=True, hide_index=True)
else:
    st.info("Aún no hay resultados para mostrar.")

st.markdown("#### Comparativo gráfico")
if data["ranking"]:
    nombres = [x["nombre"] for x in data["ranking"]]
    puntajes = [x["puntaje"] for x in data["ranking"]]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=puntajes,
            y=nombres,
            orientation="h",
            text=[f"{v:.4f}" for v in puntajes],
            textposition="outside",
        )
    )
    fig.update_layout(
        height=max(320, 90 + len(nombres) * 60),
        margin=dict(l=30, r=30, t=20, b=30),
        yaxis=dict(autorange="reversed"),
        xaxis_title="Puntaje total",
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("El gráfico aparecerá cuando existan puntajes calculados.")


if st.button("✅ Consolidar localización", use_container_width=True):
    data = recalcular(deepcopy(st.session_state["localizacion_datos"]))

    errores = []
    if hay_localizaciones_sin_nombre(data):
        errores.append("Todas las localizaciones deben tener nombre.")
    if not data["validacion"]["ponderacion_ok"]:
        errores.append("La suma de ponderaciones debe ser exactamente 100%.")
    if hay_calificaciones_faltantes(data):
        errores.append("Hay factores aplicables sin calificación en una o más localizaciones.")

    if errores:
        for err in errores:
            st.error(err)
    else:
        guardar_localizacion(data)
        st.success("Localización consolidada y guardada.")
