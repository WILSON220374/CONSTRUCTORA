import pandas as pd
import streamlit as st
from supabase_state import cargar_estado, guardar_estado

st.title("FACTOR MULTIPLICADOR")

alcance = st.session_state.get("alcance_datos", {}) or {}
nombre_proyecto = alcance.get("nombre_proyecto", "") or "SIN NOMBRE DEFINIDO"

st.markdown(f"## {nombre_proyecto}")

try:
    fm_datos = cargar_estado("factor_multiplicador") or {}
except Exception:
    fm_datos = {}

if "fm_valor_base" not in st.session_state:
    st.session_state["fm_valor_base"] = float(fm_datos.get("valor_base", 0.0) or 0.0)

key_prest = "fm_prest_widget_data"
key_ind = "fm_ind_widget_data"
key_util = "fm_util_widget_data"

prest_cols = ["No.", "Factor", "Base", "Valor"]
ind_cols = ["No.", "Factor", "Base", "Valor"]
util_cols = ["No.", "Factor", "Base", "Valor"]


def _normalizar(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    df = df.copy()

    for c in cols:
        if c not in df.columns:
            df[c] = "" if c in ["No.", "Factor", "Base"] else 0.0

    df = df[cols].copy()
    df["No."] = df["No."].fillna("").astype(str)
    df["Factor"] = df["Factor"].fillna("").astype(str)
    df["Base"] = df["Base"].fillna("").astype(str)
    df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce").fillna(0.0)

    return df


def _guardar_factor_multiplicador():
    try:
        df_prest_guardar = _normalizar(pd.DataFrame(st.session_state.get(key_prest, [])), prest_cols)
        df_ind_guardar = _normalizar(pd.DataFrame(st.session_state.get(key_ind, [])), ind_cols)
        df_util_guardar = _normalizar(pd.DataFrame(st.session_state.get(key_util, [])), util_cols)

        total_prest = float(pd.to_numeric(df_prest_guardar["Valor"], errors="coerce").fillna(0.0).sum())
        total_ind = float(pd.to_numeric(df_ind_guardar["Valor"], errors="coerce").fillna(0.0).sum())
        total_util = float(pd.to_numeric(df_util_guardar["Valor"], errors="coerce").fillna(0.0).sum())
        factor_final = float(st.session_state.get("fm_valor_base", 0.0) or 0.0) + total_prest + total_ind + total_util

        guardar_estado(
            "factor_multiplicador",
            {
                "valor_base": float(st.session_state.get("fm_valor_base", 0.0) or 0.0),
                "prestacional": df_prest_guardar.to_dict(orient="records"),
                "costos_indirectos": df_ind_guardar.to_dict(orient="records"),
                "utilidad": df_util_guardar.to_dict(orient="records"),
                "total_prestacional": total_prest,
                "total_costos_indirectos": total_ind,
                "total_utilidad": total_util,
                "factor_multiplicador_final": factor_final,
            },
        )

        try:
            ci_datos = cargar_estado("costos_indirectos") or {}
        except Exception:
            ci_datos = {}

        ci_datos["factor_multiplicador_personal"] = factor_final
        guardar_estado("costos_indirectos", ci_datos)
        st.session_state["costos_indirectos_factor_multiplicador"] = factor_final

        return True
    except Exception:
        st.error("La sesión expiró. Inicia sesión de nuevo para guardar el factor multiplicador.")
        return False


prest_default = [
    {"No.": "1.1", "Factor": "Cesantías", "Base": "/12.", "Valor": 0.0833},
    {"No.": "1.2", "Factor": "Intereses sobre cesantías", "Base": "*1%", "Valor": 0.0100},
    {"No.": "1.3", "Factor": "Prima anual", "Base": "/12.", "Valor": 0.0833},
    {"No.": "1.4", "Factor": "Caja de compensación", "Base": "4%", "Valor": 0.0400},
    {"No.": "1.5", "Factor": "SENA", "Base": "2%", "Valor": 0.0200},
    {"No.": "1.6", "Factor": "ICBF", "Base": "3%", "Valor": 0.0300},
    {"No.": "1.7", "Factor": "Seguridad Social - Salud", "Base": "8,50%", "Valor": 0.0850},
    {"No.": "1.8", "Factor": "Seguridad Social - Pensión", "Base": "*12%", "Valor": 0.1200},
    {"No.": "1.9", "Factor": "ARP Personal en Obra", "Base": "6,96%", "Valor": 0.0696},
    {"No.": "1.10", "Factor": "ARP Personal en Oficina", "Base": "0,52%", "Valor": 0.0052},
    {"No.": "1.11", "Factor": "Vacaciones", "Base": "ene-24", "Valor": 0.0417},
    {"No.": "1.12", "Factor": "Ausencias justificadas", "Base": "%", "Valor": 0.0100},
    {"No.": "1.13", "Factor": "Auxilio de Transporte", "Base": "%", "Valor": 0.1100},
    {"No.": "1.14", "Factor": "Indemnizaciones", "Base": "%", "Valor": 0.0100},
    {"No.": "1.15", "Factor": "Otros", "Base": "%", "Valor": 0.0100},
]

ind_default = [
    {"No.": "2.1", "Factor": "Impuesto de renta", "Base": "%", "Valor": 0.1100},
    {"No.": "2.2", "Factor": "Gastos Bancarios y financieros", "Base": "%", "Valor": 0.1400},
    {"No.": "2.3", "Factor": "Perfecionamiento del contrato", "Base": "%", "Valor": 0.0200},
    {"No.": "2.4", "Factor": "Otros", "Base": "%", "Valor": 0.0950},
]

util_default = [
    {"No.": "3.1", "Factor": "Utilidad", "Base": "%", "Valor": 0.1023},
]


def _cargar_tabla_inicial(key_tabla, datos_guardados, datos_default, cols):
    if key_tabla in st.session_state:
        df_actual = _normalizar(pd.DataFrame(st.session_state.get(key_tabla, [])), cols)
        st.session_state[key_tabla] = df_actual.to_dict(orient="records")
        return

    df_inicial = _normalizar(pd.DataFrame(datos_guardados), cols)
    st.session_state[key_tabla] = df_inicial.to_dict(orient="records")

_cargar_tabla_inicial(
    key_prest,
    fm_datos.get("prestacional", prest_default),
    prest_default,
    prest_cols,
)

_cargar_tabla_inicial(
    key_ind,
    fm_datos.get("costos_indirectos", ind_default),
    ind_default,
    ind_cols,
)

_cargar_tabla_inicial(
    key_util,
    fm_datos.get("utilidad", util_default),
    util_default,
    util_cols,
)

df_prest_base_fix = _normalizar(pd.DataFrame(st.session_state.get(key_prest, [])), prest_cols)

mapa_base_excel = {
    "1.4": "4%",
    "1.5": "2%",
    "1.6": "3%",
    "1.7": "8,50%",
    "1.8": "*12%",
    "1.9": "6,96%",
    "1.10": "0,52%",
    "1.11": "ene-24",
    "1.12": "%",
    "1.13": "%",
    "1.14": "%",
    "1.15": "%",
}

mapa_valor_excel = {
    "1.1": 0.0833,
    "1.2": 0.0100,
    "1.3": 0.0833,
    "1.4": 0.0400,
    "1.5": 0.0200,
    "1.6": 0.0300,
    "1.7": 0.0850,
    "1.8": 0.1200,
    "1.9": 0.0696,
    "1.10": 0.0052,
    "1.11": 0.0417,
    "1.12": 0.0100,
    "1.13": 0.1100,
    "1.14": 0.0100,
    "1.15": 0.0100,
}

valores_legacy_prest = {
    "1.7": [0.0, 0.0800],
    "1.9": [0.0, 0.0600],
    "1.10": [0.0],
    "1.11": [0.0, 0.0400],
}

for i in df_prest_base_fix.index:
    no_item = str(df_prest_base_fix.at[i, "No."]).strip()

    if no_item in mapa_base_excel:
        base_actual = str(df_prest_base_fix.at[i, "Base"]).strip()
        if base_actual in ["0.04", "0.02", "0.03", "0.085", "0.0696", "0.0052", "/24.", "ene-24", "%", "*12%"]:
            df_prest_base_fix.at[i, "Base"] = mapa_base_excel[no_item]

    if no_item in mapa_valor_excel:
        pass

df_ind_fix = _normalizar(pd.DataFrame(st.session_state.get(key_ind, [])), ind_cols)
mapa_ind_default = {str(x["No."]).strip(): x for x in ind_default}

for i in df_ind_fix.index:
    no_item = str(df_ind_fix.at[i, "No."]).strip()
    if no_item in mapa_ind_default:
        fila_default = mapa_ind_default[no_item]
        df_ind_fix.at[i, "Factor"] = fila_default["Factor"]
        df_ind_fix.at[i, "Base"] = fila_default["Base"]

        valor_actual = pd.to_numeric(df_ind_fix.at[i, "Valor"], errors="coerce")
        if pd.isna(valor_actual) or abs(float(valor_actual)) < 0.000001:
            df_ind_fix.at[i, "Valor"] = fila_default["Valor"]

st.session_state[key_ind] = df_ind_fix.to_dict(orient="records")

df_util_fix = _normalizar(pd.DataFrame(st.session_state.get(key_util, [])), util_cols)
for i in df_util_fix.index:
    no_item = str(df_util_fix.at[i, "No."]).strip()
    if no_item == "3.1":
        valor_actual = pd.to_numeric(df_util_fix.at[i, "Valor"], errors="coerce")
        if pd.isna(valor_actual) or abs(float(valor_actual)) < 0.000001:
            df_util_fix.at[i, "Valor"] = 0.1023
st.session_state[key_util] = df_util_fix.to_dict(orient="records")


def _on_change_prest():
    widget = st.session_state.get("fm_prest_widget", {}) or {}
    edited_rows = widget.get("edited_rows", {}) or {}
    added_rows = widget.get("added_rows", []) or []
    deleted_rows = widget.get("deleted_rows", []) or []

    data = _normalizar(pd.DataFrame(st.session_state.get(key_prest, [])), prest_cols)

    if deleted_rows:
        data = data.drop(index=deleted_rows, errors="ignore").reset_index(drop=True)

    for row_idx, cambios in edited_rows.items():
        if row_idx >= len(data):
            continue
        for col_name, valor in cambios.items():
            if col_name in data.columns:
                data.at[row_idx, col_name] = valor

    if added_rows:
        df_added = pd.DataFrame(added_rows)
        data = pd.concat([data, _normalizar(df_added, prest_cols)], ignore_index=True)

    st.session_state[key_prest] = _normalizar(data, prest_cols).to_dict(orient="records")
    _guardar_factor_multiplicador()


def _on_change_ind():
    widget = st.session_state.get("fm_ind_widget", {}) or {}
    edited_rows = widget.get("edited_rows", {}) or {}
    added_rows = widget.get("added_rows", []) or []
    deleted_rows = widget.get("deleted_rows", []) or []

    data = _normalizar(pd.DataFrame(st.session_state.get(key_ind, [])), ind_cols)

    if deleted_rows:
        data = data.drop(index=deleted_rows, errors="ignore").reset_index(drop=True)

    for row_idx, cambios in edited_rows.items():
        if row_idx >= len(data):
            continue
        for col_name, valor in cambios.items():
            if col_name in data.columns:
                data.at[row_idx, col_name] = valor

    if added_rows:
        df_added = pd.DataFrame(added_rows)
        data = pd.concat([data, _normalizar(df_added, ind_cols)], ignore_index=True)

    st.session_state[key_ind] = _normalizar(data, ind_cols).to_dict(orient="records")
    _guardar_factor_multiplicador()


def _on_change_util():
    widget = st.session_state.get("fm_util_widget", {}) or {}
    edited_rows = widget.get("edited_rows", {}) or {}
    added_rows = widget.get("added_rows", []) or []
    deleted_rows = widget.get("deleted_rows", []) or []

    data = _normalizar(pd.DataFrame(st.session_state.get(key_util, [])), util_cols)

    if deleted_rows:
        data = data.drop(index=deleted_rows, errors="ignore").reset_index(drop=True)

    for row_idx, cambios in edited_rows.items():
        if row_idx >= len(data):
            continue
        for col_name, valor in cambios.items():
            if col_name in data.columns:
                data.at[row_idx, col_name] = valor

    if added_rows:
        df_added = pd.DataFrame(added_rows)
        data = pd.concat([data, _normalizar(df_added, util_cols)], ignore_index=True)

    st.session_state[key_util] = _normalizar(data, util_cols).to_dict(orient="records")
    _guardar_factor_multiplicador()


st.number_input(
    "Valor base",
    min_value=0.0,
    step=0.01,
    format="%.2f",
    key="fm_valor_base",
)

if st.button("Guardar factor multiplicador", width="stretch"):
    _guardar_factor_multiplicador()

st.divider()
st.markdown("## 1. Factor prestacional")

df_prest = _normalizar(pd.DataFrame(st.session_state.get(key_prest, [])), prest_cols)
st.data_editor(
    df_prest,
    hide_index=True,
    width="stretch",
    num_rows="dynamic",
    key="fm_prest_widget",
    on_change=_on_change_prest,
    column_config={
        "No.": st.column_config.TextColumn("No."),
        "Factor": st.column_config.TextColumn("Factor"),
        "Base": st.column_config.TextColumn("Base"),
        "Valor": st.column_config.NumberColumn("Valor", min_value=0.0, step=0.0001, format="%.4f"),
    },
)

df_prest_total = _normalizar(pd.DataFrame(st.session_state.get(key_prest, [])), prest_cols)
total_prestacional = float(pd.to_numeric(df_prest_total["Valor"], errors="coerce").fillna(0.0).sum())
cp1, cp2 = st.columns([5, 1])
with cp1:
    st.markdown("### Total factor prestacional")
with cp2:
    st.markdown(f"## {total_prestacional:,.4f}")

st.divider()
st.markdown("## 2. Costos indirectos")

df_ind = _normalizar(pd.DataFrame(st.session_state.get(key_ind, [])), ind_cols)
st.data_editor(
    df_ind,
    hide_index=True,
    width="stretch",
    num_rows="dynamic",
    key="fm_ind_widget",
    on_change=_on_change_ind,
    column_config={
        "No.": st.column_config.TextColumn("No."),
        "Factor": st.column_config.TextColumn("Factor"),
        "Base": st.column_config.TextColumn("Base"),
        "Valor": st.column_config.NumberColumn("Valor", min_value=0.0, step=0.0001, format="%.4f"),
    },
)

df_ind_total = _normalizar(pd.DataFrame(st.session_state.get(key_ind, [])), ind_cols)
total_costos_indirectos = float(pd.to_numeric(df_ind_total["Valor"], errors="coerce").fillna(0.0).sum())
ci1, ci2 = st.columns([5, 1])
with ci1:
    st.markdown("### Total costos indirectos")
with ci2:
    st.markdown(f"## {total_costos_indirectos:,.4f}")

st.divider()
st.markdown("## 3. Utilidad")

df_util = _normalizar(pd.DataFrame(st.session_state.get(key_util, [])), util_cols)
st.data_editor(
    df_util,
    hide_index=True,
    width="stretch",
    num_rows="dynamic",
    key="fm_util_widget",
    on_change=_on_change_util,
    column_config={
        "No.": st.column_config.TextColumn("No."),
        "Factor": st.column_config.TextColumn("Factor"),
        "Base": st.column_config.TextColumn("Base"),
        "Valor": st.column_config.NumberColumn("Valor", min_value=0.0, step=0.0001, format="%.4f"),
    },
)

df_util_total = _normalizar(pd.DataFrame(st.session_state.get(key_util, [])), util_cols)
total_utilidad = float(pd.to_numeric(df_util_total["Valor"], errors="coerce").fillna(0.0).sum())
cu1, cu2 = st.columns([5, 1])
with cu1:
    st.markdown("### Total utilidad")
with cu2:
    st.markdown(f"## {total_utilidad:,.4f}")

factor_multiplicador_final = (
    float(st.session_state.get("fm_valor_base", 0.0) or 0.0)
    + total_prestacional
    + total_costos_indirectos
    + total_utilidad
)

st.divider()
cf1, cf2 = st.columns([5, 1])
with cf1:
    st.markdown("## FACTOR MULTIPLICADOR FINAL")
with cf2:
    st.markdown(f"## {factor_multiplicador_final:,.4f}")
