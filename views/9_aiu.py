import pandas as pd
import streamlit as st
from pathlib import Path
from supabase_state import cargar_estado, guardar_estado

st.title("AIU")

# -----------------------------
# Carga base
# -----------------------------
alcance = st.session_state.get("alcance_datos", {}) or {}
nombre_proyecto = alcance.get("nombre_proyecto", "") or "SIN NOMBRE DEFINIDO"

cronograma_datos = st.session_state.get("cronograma_datos", {}) or {}
tipo_presupuesto_proyecto = str(cronograma_datos.get("tipo_presupuesto_proyecto", "Obra") or "Obra").strip()

if tipo_presupuesto_proyecto != "Obra":
    st.warning("Este proyecto está clasificado como Consultoría. La hoja AIU aplica solo para proyectos de Obra.")
    st.stop()

st.markdown(f"## {nombre_proyecto}")

# Estado guardado AIU
try:
    aiu_datos = cargar_estado("aiu") or {}
except Exception:
    aiu_datos = {}

# Presupuesto de obra
presupuesto_obra_datos = st.session_state.get("presupuesto_obra_datos", {}) or {}
if not presupuesto_obra_datos:
    try:
        presupuesto_obra_datos = cargar_estado("presupuesto_obra") or {}
    except Exception:
        presupuesto_obra_datos = {}

costo_directo_presupuesto = float(
    (presupuesto_obra_datos.get("resumen", {}) or {}).get("costo_directo_total", 0.0) or 0.0
)
st.session_state["aiu_costo_directo"] = costo_directo_presupuesto

# -----------------------------
# Catálogo sueldos gobernación
# -----------------------------
ruta_sueldos = Path("data") / "sueldos.xlsx"

try:
    df_sueldos_raw = pd.read_excel(ruta_sueldos)
except Exception:
    df_sueldos_raw = pd.DataFrame(columns=["ITEM", "DESCIPCION", "UNIDAD", "VALOR"])

df_sueldos_raw.columns = [str(c).strip() for c in df_sueldos_raw.columns]

renombres = {}
for c in df_sueldos_raw.columns:
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
    df_sueldos_raw = df_sueldos_raw.rename(columns=renombres)

for col in ["ITEM", "DESCIPCION", "UNIDAD", "VALOR"]:
    if col not in df_sueldos_raw.columns:
        df_sueldos_raw[col] = ""

df_sueldos = df_sueldos_raw[["ITEM", "DESCIPCION", "UNIDAD", "VALOR"]].copy()
df_sueldos["ITEM"] = df_sueldos["ITEM"].fillna("").astype(str).str.strip()
df_sueldos["DESCIPCION"] = df_sueldos["DESCIPCION"].fillna("").astype(str).str.strip()
df_sueldos["UNIDAD"] = df_sueldos["UNIDAD"].fillna("").astype(str).str.strip()
df_sueldos["VALOR"] = pd.to_numeric(df_sueldos["VALOR"], errors="coerce").fillna(0.0)

map_item_gober = {
    row["ITEM"]: {
        "descripcion_gober": row["DESCIPCION"],
        "unidad": row["UNIDAD"],
        "basico": float(row["VALOR"]),
        "label": f"{row['ITEM']} | {row['DESCIPCION']}" if row["ITEM"] and row["DESCIPCION"] else row["ITEM"],
    }
    for _, row in df_sueldos.iterrows()
    if row["ITEM"]
}

map_desc_gober = {
    row["DESCIPCION"]: {
        "item_gober": row["ITEM"],
        "unidad": row["UNIDAD"],
        "basico": float(row["VALOR"]),
    }
    for _, row in df_sueldos.iterrows()
    if row["DESCIPCION"]
}

opciones_item_gober = sorted([x for x in df_sueldos["ITEM"].tolist() if x])
opciones_desc_gober = sorted([x for x in df_sueldos["DESCIPCION"].tolist() if x])
opciones_item_gober_label = [""] + sorted(
    [v.get("label", "") for v in map_item_gober.values() if str(v.get("label", "")).strip()]
)
# -----------------------------
# Definiciones 1.1
# -----------------------------
key_data = "aiu_11_personal_data"
key_widget = "aiu_11_personal_widget"

columnas_base = [
    "Seleccionar gober",
    "Item",
    "Item gober",
    "Descripción",
    "Fuente",
    "Unidad",
    "Cant",
    "Tiempo",
    "Prestac.",
    "% Disponib",
    "Básico",
]

columnas_texto = ["Seleccionar gober", "Item gober", "Descripción", "Fuente", "Unidad"]
columnas_num = ["Cant", "Tiempo", "Prestac.", "% Disponib", "Básico"]

fila_vacia = {
    "Seleccionar gober": "",
    "Item": 1,
    "Item gober": "",
    "Descripción": "",
    "Fuente": "Cotización",
    "Unidad": "",
    "Cant": 0.0,
    "Tiempo": 0.0,
    "Prestac.": 0.0,
    "% Disponib": 0.0,
    "Básico": 0.0,
}

if "aiu_duracion_meses" not in st.session_state:
    st.session_state["aiu_duracion_meses"] = int(aiu_datos.get("duracion_meses", 1) or 1)

if key_data not in st.session_state:
    st.session_state[key_data] = aiu_datos.get("personal_administrativo", [fila_vacia.copy()])


def _normalizar_df_11(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in columnas_base:
        if col not in df.columns:
            df[col] = "" if col in columnas_texto else 0.0

    df = df[columnas_base].copy()

    for col in columnas_texto:
        df[col] = df[col].fillna("").astype(str)

    for col in columnas_num:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df["Fuente"] = df["Fuente"].replace("", "Cotización")
    df["Item"] = list(range(1, len(df) + 1))

    for idx in df.index:
        fuente = str(df.at[idx, "Fuente"]).strip()

        if fuente == "Precios gobernación":
            item_gober = str(df.at[idx, "Item gober"]).strip()
            seleccion_gober = str(df.at[idx, "Seleccionar gober"]).strip()

            if seleccion_gober:
                codigo_sel = seleccion_gober.split(" | ", 1)[0].strip()
                if codigo_sel in map_item_gober:
                    ref = map_item_gober[codigo_sel]
                    df.at[idx, "Item gober"] = codigo_sel
                    df.at[idx, "Unidad"] = ref["unidad"]
                    df.at[idx, "Básico"] = ref["basico"]
                df.at[idx, "Seleccionar gober"] = ""

            elif item_gober and item_gober in map_item_gober:
                ref = map_item_gober[item_gober]
                df.at[idx, "Unidad"] = ref["unidad"]
                df.at[idx, "Básico"] = ref["basico"]
        else:
            df.at[idx, "Seleccionar gober"] = ""
            df.at[idx, "Item gober"] = ""

    return df


def _recalcular_11(df: pd.DataFrame) -> pd.DataFrame:
    df = _normalizar_df_11(df)

    df["Valor total"] = (
        df["Cant"]
        * df["Tiempo"]
        * df["Básico"]
        * (1 + (df["Prestac."] / 100.0))
        * (df["% Disponib"] / 100.0)
    )

    costo_directo = float(st.session_state.get("aiu_costo_directo", 0.0) or 0.0)
    if costo_directo > 0:
        df["%"] = (df["Valor total"] / costo_directo) * 100.0
    else:
        df["%"] = 0.0

    return df


def _guardar_aiu():
    try:
        personal_df = _recalcular_11(pd.DataFrame(st.session_state.get("aiu_11_personal_data", [])))
        equipos_df = _recalcular_12(pd.DataFrame(st.session_state.get("aiu_12_equipos_data", [])))
        gastos_generales_df = _recalcular_13(pd.DataFrame(st.session_state.get("aiu_13_gastos_generales_data", [])))
        gastos_legales_df = _recalcular_14(pd.DataFrame(st.session_state.get("aiu_14_gastos_legales_data", [])))

        total_personal = float(pd.to_numeric(personal_df["Valor total"], errors="coerce").fillna(0.0).sum())
        total_equipos = float(pd.to_numeric(equipos_df["Valor total"], errors="coerce").fillna(0.0).sum())
        total_gastos_generales = float(pd.to_numeric(gastos_generales_df["Valor total"], errors="coerce").fillna(0.0).sum())
        total_gastos_legales = float(pd.to_numeric(gastos_legales_df["Valor total"], errors="coerce").fillna(0.0).sum())

        administracion_valor = total_personal + total_equipos + total_gastos_generales + total_gastos_legales
        imprevistos_porcentaje = float(st.session_state.get("aiu_imprevistos_porcentaje", 0.0) or 0.0)
        utilidad_porcentaje = float(st.session_state.get("aiu_utilidad_porcentaje", 0.0) or 0.0)

        imprevistos_valor = costo_directo_presupuesto * (imprevistos_porcentaje / 100.0)
        utilidad_valor = costo_directo_presupuesto * (utilidad_porcentaje / 100.0)
        aiu_total_valor = administracion_valor + imprevistos_valor + utilidad_valor

        guardar_estado(
            "aiu",
            {
                "duracion_meses": int(st.session_state.get("aiu_duracion_meses", 1) or 1),
                "personal_administrativo": st.session_state.get("aiu_11_personal_data", []),
                "equipos_generales": st.session_state.get("aiu_12_equipos_data", []),
                "gastos_generales": st.session_state.get("aiu_13_gastos_generales_data", []),
                "gastos_legales": st.session_state.get("aiu_14_gastos_legales_data", []),
                "imprevistos_porcentaje": imprevistos_porcentaje,
                "utilidad_porcentaje": utilidad_porcentaje,
                "administracion_valor": administracion_valor,
                "imprevistos_valor": imprevistos_valor,
                "utilidad_valor": utilidad_valor,
                "aiu_total_valor": aiu_total_valor,
            },
        )
        return True
    except Exception:
        st.error("La sesión expiró. Inicia sesión de nuevo para guardar los cambios del AIU.")
        return False


def _on_change_11():
    widget_state = st.session_state.get(key_widget, {}) or {}
    edited_rows = widget_state.get("edited_rows", {}) or {}
    added_rows = widget_state.get("added_rows", []) or []
    deleted_rows = widget_state.get("deleted_rows", []) or []

    data_actual = st.session_state.get(key_data, [])
    df_actual = pd.DataFrame(data_actual).copy()
    df_actual = _normalizar_df_11(df_actual) if not df_actual.empty else pd.DataFrame(columns=columnas_base)

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
            "Seleccionar gober": nueva_fila.get("Seleccionar gober", "") if isinstance(nueva_fila, dict) else "",
            "Item": 0,
            "Item gober": nueva_fila.get("Item gober", "") if isinstance(nueva_fila, dict) else "",
            "Descripción": nueva_fila.get("Descripción", "") if isinstance(nueva_fila, dict) else "",
            "Fuente": nueva_fila.get("Fuente", "Cotización") if isinstance(nueva_fila, dict) else "Cotización",
            "Unidad": nueva_fila.get("Unidad", "") if isinstance(nueva_fila, dict) else "",
            "Cant": nueva_fila.get("Cant", 0.0) if isinstance(nueva_fila, dict) else 0.0,
            "Tiempo": nueva_fila.get("Tiempo", 0.0) if isinstance(nueva_fila, dict) else 0.0,
            "Prestac.": nueva_fila.get("Prestac.", 0.0) if isinstance(nueva_fila, dict) else 0.0,
            "% Disponib": nueva_fila.get("% Disponib", 0.0) if isinstance(nueva_fila, dict) else 0.0,
            "Básico": nueva_fila.get("Básico", 0.0) if isinstance(nueva_fila, dict) else 0.0,
        }
        df_actual = pd.concat([df_actual, pd.DataFrame([fila_limpia])], ignore_index=True)

    if df_actual.empty:
        df_actual = pd.DataFrame([fila_vacia.copy()])

    df_actual = _normalizar_df_11(df_actual)
    st.session_state[key_data] = df_actual.to_dict(orient="records")
    _guardar_aiu()


# -----------------------------
# Encabezado
# -----------------------------
c1, c2 = st.columns([2, 1])
with c1:
    cdx1, cdx2 = st.columns([2, 1])
    with cdx1:
        st.markdown("### Costo directo")
    with cdx2:
        st.markdown(f"## $ {costo_directo_presupuesto:,.2f}")

with c2:
    st.number_input(
        "Duración (meses)",
        min_value=1,
        step=1,
        key="aiu_duracion_meses",
    )

st.divider()

# -----------------------------
# 1.1 Personal administrativo
# -----------------------------
st.markdown("## 1. ADMINISTRACIÓN")
st.markdown("### 1.1 Personal administrativo")

df_11_base = pd.DataFrame(st.session_state.get(key_data, [])).copy()
if df_11_base.empty:
    df_11_base = pd.DataFrame([fila_vacia.copy()])

df_11_base = _normalizar_df_11(df_11_base)
df_11 = _recalcular_11(df_11_base)

st.data_editor(
    df_11,
    hide_index=True,
    width="stretch",
    num_rows="dynamic",
    key=key_widget,
    on_change=_on_change_11,
    column_config={
        "Seleccionar gober": st.column_config.SelectboxColumn(
            "Seleccionar gober",
            options=opciones_item_gober_label,
        ),
        "Item": st.column_config.NumberColumn("Item", disabled=True, format="%d"),
        "Item gober": st.column_config.TextColumn("Item gober", disabled=True),
        "Descripción": st.column_config.TextColumn("Descripción"),
        "Fuente": st.column_config.SelectboxColumn(
            "Fuente",
            options=["Cotización", "Precios gobernación"],
        ),
        "Unidad": st.column_config.TextColumn("Unidad"),
        "Cant": st.column_config.NumberColumn("Cant", min_value=0.0, step=0.01, format="%.2f"),
        "Tiempo": st.column_config.NumberColumn("Tiempo", min_value=0.0, step=0.01, format="%.2f"),
        "Prestac.": st.column_config.NumberColumn("Prestac.", min_value=0.0, step=0.01, format="%.2f"),
        "% Disponib": st.column_config.NumberColumn("% Disponib", min_value=0.0, step=0.01, format="%.2f"),
        "Básico": st.column_config.NumberColumn("Básico", min_value=0.0, step=0.01, format="$ %.2f"),
        "Valor total": st.column_config.NumberColumn("Valor total", disabled=True, format="$ %.2f"),
        "%": st.column_config.NumberColumn("%", disabled=True, format="%.2f"),
    },
    disabled=["Item", "Item gober", "Descripción gober", "Valor total", "%"],
)

df_11_final = _recalcular_11(pd.DataFrame(st.session_state.get(key_data, [])))
total_11 = float(pd.to_numeric(df_11_final["Valor total"], errors="coerce").fillna(0.0).sum())
porc_11 = float(pd.to_numeric(df_11_final["%"], errors="coerce").fillna(0.0).sum())

c_total_1, c_total_2 = st.columns([5, 1])
with c_total_1:
    st.markdown("**Total personal administrativo**")
with c_total_2:
    st.markdown(f"**$ {total_11:,.2f}**")

c_porc_1, c_porc_2 = st.columns([5, 1])
with c_porc_1:
    st.markdown("**% sobre costo directo**")
with c_porc_2:
    st.markdown(f"**{porc_11:,.2f}%**")

st.divider()
st.markdown("### 1.2 Equipos generales, movilización e instalación")

key_data_12 = "aiu_12_equipos_data"
key_widget_12 = "aiu_12_equipos_widget"

columnas_base_12 = [
    "Item",
    "Descripción",
    "Unidad",
    "Cantidad",
    "Tiempo",
    "Tarifa",
]

columnas_texto_12 = ["Descripción", "Unidad"]
columnas_num_12 = ["Cantidad", "Tiempo", "Tarifa"]

fila_vacia_12 = {
    "Item": 1,
    "Descripción": "",
    "Unidad": "",
    "Cantidad": 0.0,
    "Tiempo": 0.0,
    "Tarifa": 0.0,
}

if key_data_12 not in st.session_state:
    st.session_state[key_data_12] = aiu_datos.get("equipos_generales", [fila_vacia_12.copy()])


def _normalizar_df_12(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in columnas_base_12:
        if col not in df.columns:
            df[col] = "" if col in columnas_texto_12 else 0.0

    df = df[columnas_base_12].copy()

    for col in columnas_texto_12:
        df[col] = df[col].fillna("").astype(str)

    for col in columnas_num_12:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df["Item"] = list(range(1, len(df) + 1))
    return df


def _recalcular_12(df: pd.DataFrame) -> pd.DataFrame:
    df = _normalizar_df_12(df)

    df["Valor total"] = (
        df["Cantidad"]
        * df["Tiempo"]
        * df["Tarifa"]
    )

    costo_directo = float(st.session_state.get("aiu_costo_directo", 0.0) or 0.0)
    if costo_directo > 0:
        df["%"] = (df["Valor total"] / costo_directo) * 100.0
    else:
        df["%"] = 0.0

    return df


def _on_change_12():
    widget_state = st.session_state.get(key_widget_12, {}) or {}
    edited_rows = widget_state.get("edited_rows", {}) or {}
    added_rows = widget_state.get("added_rows", []) or []
    deleted_rows = widget_state.get("deleted_rows", []) or []

    data_actual = st.session_state.get(key_data_12, [])
    df_actual = pd.DataFrame(data_actual).copy()
    df_actual = _normalizar_df_12(df_actual) if not df_actual.empty else pd.DataFrame(columns=columnas_base_12)

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
            "Item": 0,
            "Descripción": nueva_fila.get("Descripción", "") if isinstance(nueva_fila, dict) else "",
            "Unidad": nueva_fila.get("Unidad", "") if isinstance(nueva_fila, dict) else "",
            "Cantidad": nueva_fila.get("Cantidad", 0.0) if isinstance(nueva_fila, dict) else 0.0,
            "Tiempo": nueva_fila.get("Tiempo", 0.0) if isinstance(nueva_fila, dict) else 0.0,
            "Tarifa": nueva_fila.get("Tarifa", 0.0) if isinstance(nueva_fila, dict) else 0.0,
        }
        df_actual = pd.concat([df_actual, pd.DataFrame([fila_limpia])], ignore_index=True)

    if df_actual.empty:
        df_actual = pd.DataFrame([fila_vacia_12.copy()])

    df_actual = _normalizar_df_12(df_actual)
    st.session_state[key_data_12] = df_actual.to_dict(orient="records")
    _guardar_aiu()


df_12_base = pd.DataFrame(st.session_state.get(key_data_12, [])).copy()
if df_12_base.empty:
    df_12_base = pd.DataFrame([fila_vacia_12.copy()])

df_12_base = _normalizar_df_12(df_12_base)
df_12 = _recalcular_12(df_12_base)

st.data_editor(
    df_12,
    hide_index=True,
    width="stretch",
    num_rows="dynamic",
    key=key_widget_12,
    on_change=_on_change_12,
    column_config={
        "Item": st.column_config.NumberColumn("Item", disabled=True, format="%d"),
        "Descripción": st.column_config.TextColumn("Descripción"),
        "Unidad": st.column_config.TextColumn("Unidad"),
        "Cantidad": st.column_config.NumberColumn("Cantidad", min_value=0.0, step=0.01, format="%.2f"),
        "Tiempo": st.column_config.NumberColumn("Tiempo", min_value=0.0, step=0.01, format="%.2f"),
        "Tarifa": st.column_config.NumberColumn("Tarifa", min_value=0.0, step=0.01, format="$ %.2f"),
        "Valor total": st.column_config.NumberColumn("Valor total", disabled=True, format="$ %.2f"),
        "%": st.column_config.NumberColumn("%", disabled=True, format="%.2f"),
    },
    disabled=["Item", "Valor total", "%"],
)

df_12_final = _recalcular_12(pd.DataFrame(st.session_state.get(key_data_12, [])))
total_12 = float(pd.to_numeric(df_12_final["Valor total"], errors="coerce").fillna(0.0).sum())
porc_12 = float(pd.to_numeric(df_12_final["%"], errors="coerce").fillna(0.0).sum())

c_total_12_1, c_total_12_2 = st.columns([5, 1])
with c_total_12_1:
    st.markdown("**Total equipos generales, movilización e instalación**")
with c_total_12_2:
    st.markdown(f"**$ {total_12:,.2f}**")

c_porc_12_1, c_porc_12_2 = st.columns([5, 1])
with c_porc_12_1:
    st.markdown("**% sobre costo directo**")
with c_porc_12_2:
    st.markdown(f"**{porc_12:,.2f}%**")

st.divider()
st.markdown("### 1.3 Gastos generales")

key_data_13 = "aiu_13_gastos_generales_data"
key_widget_13 = "aiu_13_gastos_generales_widget"

columnas_base_13 = [
    "Item",
    "Descripción",
    "Unid",
    "Cantidad",
    "Tiempo",
    "Tarifa",
]

columnas_texto_13 = ["Descripción", "Unid"]
columnas_num_13 = ["Cantidad", "Tiempo", "Tarifa"]

fila_vacia_13 = {
    "Item": 1,
    "Descripción": "",
    "Unid": "",
    "Cantidad": 0.0,
    "Tiempo": 0.0,
    "Tarifa": 0.0,
}

if key_data_13 not in st.session_state:
    st.session_state[key_data_13] = aiu_datos.get("gastos_generales", [fila_vacia_13.copy()])


def _normalizar_df_13(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in columnas_base_13:
        if col not in df.columns:
            df[col] = "" if col in columnas_texto_13 else 0.0

    df = df[columnas_base_13].copy()

    for col in columnas_texto_13:
        df[col] = df[col].fillna("").astype(str)

    for col in columnas_num_13:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df["Item"] = [f"1.3.{i}" for i in range(1, len(df) + 1)]
    return df


def _recalcular_13(df: pd.DataFrame) -> pd.DataFrame:
    df = _normalizar_df_13(df)

    df["Valor total"] = (
        df["Cantidad"]
        * df["Tiempo"]
        * df["Tarifa"]
    )

    costo_directo = float(st.session_state.get("aiu_costo_directo", 0.0) or 0.0)
    if costo_directo > 0:
        df["%"] = (df["Valor total"] / costo_directo) * 100.0
    else:
        df["%"] = 0.0

    return df


def _on_change_13():
    widget_state = st.session_state.get(key_widget_13, {}) or {}
    edited_rows = widget_state.get("edited_rows", {}) or {}
    added_rows = widget_state.get("added_rows", []) or []
    deleted_rows = widget_state.get("deleted_rows", []) or []

    data_actual = st.session_state.get(key_data_13, [])
    df_actual = pd.DataFrame(data_actual).copy()
    df_actual = _normalizar_df_13(df_actual) if not df_actual.empty else pd.DataFrame(columns=columnas_base_13)

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
            "Item": "",
            "Descripción": nueva_fila.get("Descripción", "") if isinstance(nueva_fila, dict) else "",
            "Unid": nueva_fila.get("Unid", "") if isinstance(nueva_fila, dict) else "",
            "Cantidad": nueva_fila.get("Cantidad", 0.0) if isinstance(nueva_fila, dict) else 0.0,
            "Tiempo": nueva_fila.get("Tiempo", 0.0) if isinstance(nueva_fila, dict) else 0.0,
            "Tarifa": nueva_fila.get("Tarifa", 0.0) if isinstance(nueva_fila, dict) else 0.0,
        }
        df_actual = pd.concat([df_actual, pd.DataFrame([fila_limpia])], ignore_index=True)

    if df_actual.empty:
        df_actual = pd.DataFrame([fila_vacia_13.copy()])

    df_actual = _normalizar_df_13(df_actual)
    st.session_state[key_data_13] = df_actual.to_dict(orient="records")
    _guardar_aiu()


df_13_base = pd.DataFrame(st.session_state.get(key_data_13, [])).copy()
if df_13_base.empty:
    df_13_base = pd.DataFrame([fila_vacia_13.copy()])

df_13_base = _normalizar_df_13(df_13_base)
df_13 = _recalcular_13(df_13_base)

st.data_editor(
    df_13,
    hide_index=True,
    width="stretch",
    num_rows="dynamic",
    key=key_widget_13,
    on_change=_on_change_13,
    column_config={
        "Item": st.column_config.TextColumn("Item", disabled=True),
        "Descripción": st.column_config.TextColumn("Descripción"),
        "Unid": st.column_config.TextColumn("Unid"),
        "Cantidad": st.column_config.NumberColumn("Cantidad", min_value=0.0, step=0.01, format="%.2f"),
        "Tiempo": st.column_config.NumberColumn("Tiempo", min_value=0.0, step=0.01, format="%.2f"),
        "Tarifa": st.column_config.NumberColumn("Tarifa", min_value=0.0, step=0.01, format="$ %.2f"),
        "Valor total": st.column_config.NumberColumn("Valor total", disabled=True, format="$ %.2f"),
        "%": st.column_config.NumberColumn("%", disabled=True, format="%.2f"),
    },
    disabled=["Item", "Valor total", "%"],
)

df_13_final = _recalcular_13(pd.DataFrame(st.session_state.get(key_data_13, [])))
total_13 = float(pd.to_numeric(df_13_final["Valor total"], errors="coerce").fillna(0.0).sum())
porc_13 = float(pd.to_numeric(df_13_final["%"], errors="coerce").fillna(0.0).sum())

c_total_13_1, c_total_13_2 = st.columns([5, 1])
with c_total_13_1:
    st.markdown("**Total gastos generales**")
with c_total_13_2:
    st.markdown(f"**$ {total_13:,.2f}**")

c_porc_13_1, c_porc_13_2 = st.columns([5, 1])
with c_porc_13_1:
    st.markdown("**% sobre costo directo**")
with c_porc_13_2:
    st.markdown(f"**{porc_13:,.2f}%**")

st.divider()
st.markdown("### 1.4 Gastos legales, jurídicos, tributarios")

key_data_14 = "aiu_14_gastos_legales_data"
key_widget_14 = "aiu_14_gastos_legales_widget"

columnas_base_14 = [
    "Item",
    "Descripción",
    "Unid",
    "Cantidad",
    "Frec",
    "Tarifa",
]

columnas_texto_14 = ["Descripción", "Unid"]
columnas_num_14 = ["Cantidad", "Frec", "Tarifa"]

fila_vacia_14 = {
    "Item": "1.4.1",
    "Descripción": "",
    "Unid": "",
    "Cantidad": 0.0,
    "Frec": 0.0,
    "Tarifa": 0.0,
}

if key_data_14 not in st.session_state:
    st.session_state[key_data_14] = aiu_datos.get("gastos_legales", [fila_vacia_14.copy()])


def _normalizar_df_14(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in columnas_base_14:
        if col not in df.columns:
            df[col] = "" if col in columnas_texto_14 else 0.0

    df = df[columnas_base_14].copy()

    for col in columnas_texto_14:
        df[col] = df[col].fillna("").astype(str)

    for col in columnas_num_14:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df["Item"] = [f"1.4.{i}" for i in range(1, len(df) + 1)]
    return df


def _recalcular_14(df: pd.DataFrame) -> pd.DataFrame:
    df = _normalizar_df_14(df)

    df["Valor total"] = (
        df["Cantidad"]
        * df["Frec"]
        * df["Tarifa"]
    )

    costo_directo = float(st.session_state.get("aiu_costo_directo", 0.0) or 0.0)
    if costo_directo > 0:
        df["%"] = (df["Valor total"] / costo_directo) * 100.0
    else:
        df["%"] = 0.0

    return df


def _on_change_14():
    widget_state = st.session_state.get(key_widget_14, {}) or {}
    edited_rows = widget_state.get("edited_rows", {}) or {}
    added_rows = widget_state.get("added_rows", []) or []
    deleted_rows = widget_state.get("deleted_rows", []) or []

    data_actual = st.session_state.get(key_data_14, [])
    df_actual = pd.DataFrame(data_actual).copy()
    df_actual = _normalizar_df_14(df_actual) if not df_actual.empty else pd.DataFrame(columns=columnas_base_14)

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
            "Item": "",
            "Descripción": nueva_fila.get("Descripción", "") if isinstance(nueva_fila, dict) else "",
            "Unid": nueva_fila.get("Unid", "") if isinstance(nueva_fila, dict) else "",
            "Cantidad": nueva_fila.get("Cantidad", 0.0) if isinstance(nueva_fila, dict) else 0.0,
            "Frec": nueva_fila.get("Frec", 0.0) if isinstance(nueva_fila, dict) else 0.0,
            "Tarifa": nueva_fila.get("Tarifa", 0.0) if isinstance(nueva_fila, dict) else 0.0,
        }
        df_actual = pd.concat([df_actual, pd.DataFrame([fila_limpia])], ignore_index=True)

    if df_actual.empty:
        df_actual = pd.DataFrame([fila_vacia_14.copy()])

    df_actual = _normalizar_df_14(df_actual)
    st.session_state[key_data_14] = df_actual.to_dict(orient="records")
    _guardar_aiu()


df_14_base = pd.DataFrame(st.session_state.get(key_data_14, [])).copy()
if df_14_base.empty:
    df_14_base = pd.DataFrame([fila_vacia_14.copy()])

df_14_base = _normalizar_df_14(df_14_base)
df_14 = _recalcular_14(df_14_base)

st.data_editor(
    df_14,
    hide_index=True,
    width="stretch",
    num_rows="dynamic",
    key=key_widget_14,
    on_change=_on_change_14,
    column_config={
        "Item": st.column_config.TextColumn("Item", disabled=True),
        "Descripción": st.column_config.TextColumn("Descripción"),
        "Unid": st.column_config.TextColumn("Unid"),
        "Cantidad": st.column_config.NumberColumn("Cantidad", min_value=0.0, step=0.01, format="%.2f"),
        "Frec": st.column_config.NumberColumn("Frec", min_value=0.0, step=0.01, format="%.2f"),
        "Tarifa": st.column_config.NumberColumn("Tarifa", min_value=0.0, step=0.01, format="$ %.2f"),
        "Valor total": st.column_config.NumberColumn("Valor total", disabled=True, format="$ %.2f"),
        "%": st.column_config.NumberColumn("%", disabled=True, format="%.2f"),
    },
    disabled=["Item", "Valor total", "%"],
)

df_14_final = _recalcular_14(pd.DataFrame(st.session_state.get(key_data_14, [])))
total_14 = float(pd.to_numeric(df_14_final["Valor total"], errors="coerce").fillna(0.0).sum())
porc_14 = float(pd.to_numeric(df_14_final["%"], errors="coerce").fillna(0.0).sum())

c_total_14_1, c_total_14_2 = st.columns([5, 1])
with c_total_14_1:
    st.markdown("**Total gastos legales, jurídicos, tributarios**")
with c_total_14_2:
    st.markdown(f"**$ {total_14:,.2f}**")

c_porc_14_1, c_porc_14_2 = st.columns([5, 1])
with c_porc_14_1:
    st.markdown("**% sobre costo directo**")
with c_porc_14_2:
    st.markdown(f"**{porc_14:,.2f}%**")

st.divider()
st.markdown("## RESUMEN DE COSTOS - COMPONENTE ADMINISTRACIÓN")

total_administracion = total_11 + total_12 + total_13 + total_14
porc_administracion = porc_11 + porc_12 + porc_13 + porc_14

resumen_admin = pd.DataFrame(
    [
        {
            "Concepto": "1.1 PERSONAL ADMINISTRATIVO",
            "Valor": total_11,
            "%": porc_11,
        },
        {
            "Concepto": "1.2 EQUIPOS GENERALES, MOVILIZACIÓN E INSTALACIÓN",
            "Valor": total_12,
            "%": porc_12,
        },
        {
            "Concepto": "1.3 GASTOS GENERALES",
            "Valor": total_13,
            "%": porc_13,
        },
        {
            "Concepto": "1.4 GASTOS LEGALES, JURÍDICOS, TRIBUTARIOS",
            "Valor": total_14,
            "%": porc_14,
        },
        {
            "Concepto": "TOTAL ADMINISTRACIÓN",
            "Valor": total_administracion,
            "%": porc_administracion,
        },
    ]
)

st.dataframe(
    resumen_admin,
    hide_index=True,
    width="stretch",
    column_config={
        "Concepto": st.column_config.TextColumn("Concepto"),
        "Valor": st.column_config.NumberColumn("Valor", format="$ %.2f"),
        "%": st.column_config.NumberColumn("%", format="%.2f"),
    },
)

st.divider()
st.markdown("## 2. IMPREVISTOS")

if "aiu_imprevistos_porcentaje" not in st.session_state:
    st.session_state["aiu_imprevistos_porcentaje"] = float(aiu_datos.get("imprevistos_porcentaje", 0.0) or 0.0)

c_imp_1, c_imp_2 = st.columns([2, 1])

with c_imp_1:
    st.number_input(
        "Porcentaje de imprevistos",
        min_value=0.0,
        step=0.01,
        format="%.2f",
        key="aiu_imprevistos_porcentaje",
    )

imprevistos_valor = costo_directo_presupuesto * (
    float(st.session_state.get("aiu_imprevistos_porcentaje", 0.0) or 0.0) / 100.0
)

with c_imp_2:
    st.markdown("### Valor imprevistos")
    st.markdown(f"## $ {imprevistos_valor:,.2f}")

st.divider()
st.markdown("## 3. UTILIDAD")

if "aiu_utilidad_porcentaje" not in st.session_state:
    st.session_state["aiu_utilidad_porcentaje"] = float(aiu_datos.get("utilidad_porcentaje", 0.0) or 0.0)

c_ut_1, c_ut_2 = st.columns([2, 1])

with c_ut_1:
    st.number_input(
        "Porcentaje de utilidad",
        min_value=0.0,
        step=0.01,
        format="%.2f",
        key="aiu_utilidad_porcentaje",
    )

utilidad_valor = costo_directo_presupuesto * (
    float(st.session_state.get("aiu_utilidad_porcentaje", 0.0) or 0.0) / 100.0
)

with c_ut_2:
    st.markdown("### Valor utilidad")
    st.markdown(f"## $ {utilidad_valor:,.2f}")


st.divider()
st.markdown("## RESUMEN FINAL DEL AIU")

administracion_valor = total_administracion
administracion_pct = porc_administracion

imprevistos_pct = float(st.session_state.get("aiu_imprevistos_porcentaje", 0.0) or 0.0)
utilidad_pct = float(st.session_state.get("aiu_utilidad_porcentaje", 0.0) or 0.0)

resumen_final_aiu = pd.DataFrame(
    [
        {
            "Componente": "Administración",
            "Valor": administracion_valor,
            "%": administracion_pct,
        },
        {
            "Componente": "Imprevistos",
            "Valor": imprevistos_valor,
            "%": imprevistos_pct,
        },
        {
            "Componente": "Utilidad",
            "Valor": utilidad_valor,
            "%": utilidad_pct,
        },
    ]
)

st.dataframe(
    resumen_final_aiu,
    hide_index=True,
    width="stretch",
    column_config={
        "Componente": st.column_config.TextColumn("Componente"),
        "Valor": st.column_config.NumberColumn("Valor", format="$ %.2f"),
        "%": st.column_config.NumberColumn("%", format="%.2f"),
    },
)

aiu_total_valor = administracion_valor + imprevistos_valor + utilidad_valor
aiu_total_pct = administracion_pct + imprevistos_pct + utilidad_pct

c_aiu_1, c_aiu_2 = st.columns([5, 1])
with c_aiu_1:
    st.markdown("### TOTAL AIU")
with c_aiu_2:
    st.markdown(f"## $ {aiu_total_valor:,.2f}")

c_aiu_3, c_aiu_4 = st.columns([5, 1])
with c_aiu_3:
    st.markdown("### % TOTAL AIU")
with c_aiu_4:
    st.markdown(f"## {aiu_total_pct:,.2f}%")

# ---------------------------------
# Conexión con Presupuesto de Obra
# ---------------------------------
if "presupuesto_obra_datos" not in st.session_state or not isinstance(st.session_state.get("presupuesto_obra_datos"), dict):
    st.session_state["presupuesto_obra_datos"] = {}

if "configuracion" not in st.session_state["presupuesto_obra_datos"] or not isinstance(
    st.session_state["presupuesto_obra_datos"].get("configuracion"), dict
):
    st.session_state["presupuesto_obra_datos"]["configuracion"] = {}

st.session_state["presupuesto_obra_datos"]["configuracion"]["aiu_administracion_pct"] = float(administracion_pct or 0.0)
st.session_state["presupuesto_obra_datos"]["configuracion"]["aiu_imprevistos_pct"] = float(imprevistos_pct or 0.0)
st.session_state["presupuesto_obra_datos"]["configuracion"]["aiu_utilidad_pct"] = float(utilidad_pct or 0.0)
st.session_state["presupuesto_obra_datos"]["configuracion"]["aiu_pct_global"] = float(aiu_total_pct or 0.0)

try:
    guardar_estado(
        "aiu",
        {
            "duracion_meses": int(st.session_state.get("aiu_duracion_meses", 1) or 1),
            "personal_administrativo": st.session_state.get("aiu_11_personal_data", []),
            "equipos_generales": st.session_state.get("aiu_12_equipos_data", []),
            "gastos_generales": st.session_state.get("aiu_13_gastos_generales_data", []),
            "gastos_legales": st.session_state.get("aiu_14_gastos_legales_data", []),
            "imprevistos_porcentaje": float(imprevistos_pct or 0.0),
            "utilidad_porcentaje": float(utilidad_pct or 0.0),
            "administracion_valor": float(administracion_valor or 0.0),
            "imprevistos_valor": float(imprevistos_valor or 0.0),
            "utilidad_valor": float(utilidad_valor or 0.0),
            "aiu_total_valor": float(aiu_total_valor or 0.0),
        },
    )

    guardar_estado("presupuesto_obra", st.session_state["presupuesto_obra_datos"])
except RuntimeError as e:
    if "No se pudo refrescar la sesión" in str(e):
        st.warning("La sesión expiró. Inicia sesión de nuevo para guardar cambios del AIU.")
    else:
        raise
