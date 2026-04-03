import pandas as pd
import streamlit as st

@st.cache_data
def _cargar_base_apu():
    ruta = "data/Copia de APU.xlsx"
    return pd.read_excel(ruta)

st.title("APU")

if "apu_datos" not in st.session_state:
    st.session_state["apu_datos"] = {}

try:
    df_apu_base = _cargar_base_apu()
    st.caption(f"Base APU cargada: {len(df_apu_base)} filas")
except Exception as e:
    st.error("No se pudo leer data/Copia de APU.xlsx")
    st.code(str(e))
    st.stop()

st.markdown("### Encabezado del APU")

def _buscar_apu_seleccionado(df_base, cod_actividad, actividad):
    df_busqueda = df_base.copy()

    cod_actividad = str(cod_actividad or "").strip().lower()
    actividad = str(actividad or "").strip().lower()

    if cod_actividad:
        df_filtrado = df_busqueda[
            df_busqueda["cod_actividad"].astype(str).str.strip().str.lower() == cod_actividad
        ]
        if not df_filtrado.empty:
            return df_filtrado.copy()

    if actividad:
        df_filtrado = df_busqueda[
            df_busqueda["actividad"].astype(str).str.strip().str.lower() == actividad
        ]
        if not df_filtrado.empty:
            return df_filtrado.copy()

    return pd.DataFrame(columns=df_base.columns)


codigos_actividad = sorted(
    {
        str(x).strip()
        for x in df_apu_base["cod_actividad"].dropna().tolist()
        if str(x).strip()
    }
)

actividades = sorted(
    {
        str(x).strip()
        for x in df_apu_base["actividad"].dropna().tolist()
        if str(x).strip()
    }
)

if "apu_cod_actividad_busqueda" not in st.session_state:
    st.session_state["apu_cod_actividad_busqueda"] = ""
if "apu_actividad_busqueda" not in st.session_state:
    st.session_state["apu_actividad_busqueda"] = ""

def _on_change_cod_actividad():
    cod_sel = str(st.session_state.get("apu_cod_actividad_busqueda", "") or "").strip()
    if not cod_sel:
        st.session_state["apu_actividad_busqueda"] = ""
        return

    df_sync = df_apu_base[
        df_apu_base["cod_actividad"].astype(str).str.strip() == cod_sel
    ]
    if not df_sync.empty:
        st.session_state["apu_actividad_busqueda"] = str(df_sync.iloc[0].get("actividad", "") or "").strip()

def _on_change_actividad():
    act_sel = str(st.session_state.get("apu_actividad_busqueda", "") or "").strip()
    if not act_sel:
        st.session_state["apu_cod_actividad_busqueda"] = ""
        return

    df_sync = df_apu_base[
        df_apu_base["actividad"].astype(str).str.strip() == act_sel
    ]
    if not df_sync.empty:
        st.session_state["apu_cod_actividad_busqueda"] = str(df_sync.iloc[0].get("cod_actividad", "") or "").strip()

fila1_col1, fila1_col2 = st.columns([1, 3])
with fila1_col1:
    cod_actividad_input = st.selectbox(
        "cod_actividad",
        options=[""] + codigos_actividad,
        key="apu_cod_actividad_busqueda",
        on_change=_on_change_cod_actividad,
    )
with fila1_col2:
    actividad_input = st.selectbox(
        "actividad",
        options=[""] + actividades,
        key="apu_actividad_busqueda",
        on_change=_on_change_actividad,
    )

df_apu_seleccionado = _buscar_apu_seleccionado(df_apu_base, cod_actividad_input, actividad_input)

cod_capitulo_val = ""
capitulo_val = ""
cod_subcapitulo_val = ""
subcapitulo_val = ""
und_act_val = ""

if not df_apu_seleccionado.empty:
    fila_encontrada = df_apu_seleccionado.iloc[0]

    cod_actividad_resuelto = str(fila_encontrada.get("cod_actividad", "") or "")
    actividad_resuelta = str(fila_encontrada.get("actividad", "") or "")
    cod_capitulo_val = str(fila_encontrada.get("cod_capitulo", "") or "")
    capitulo_val = str(fila_encontrada.get("capitulo", "") or "")
    cod_subcapitulo_val = str(fila_encontrada.get("cod_subcapitulo", "") or "")
    subcapitulo_val = str(fila_encontrada.get("subcapitulo", "") or "")
    und_act_val = str(fila_encontrada.get("Und. Act", "") or "")
else:
    cod_actividad_resuelto = ""
    actividad_resuelta = ""

fila2_col1, fila2_col2 = st.columns([1, 3])
with fila2_col1:
    st.text_input("cod_capitulo", value=cod_capitulo_val, disabled=True)
with fila2_col2:
    st.text_input("capitulo", value=capitulo_val, disabled=True)

fila3_col1, fila3_col2, fila3_col3 = st.columns([1, 3, 1])
with fila3_col1:
    st.text_input("cod_subcapitulo", value=cod_subcapitulo_val, disabled=True)
with fila3_col2:
    st.text_input("subcapitulo", value=subcapitulo_val, disabled=True)
with fila3_col3:
    st.text_input("Und. Act", value=und_act_val, disabled=True)

st.divider()

def _tabla_apu_desde_excel(titulo, df_fuente, tipo_filtrar):
    st.markdown(f"### {titulo}")

    if df_fuente.empty:
        st.info(f"Sin información para {titulo.lower()}.")
        return 0.0

    df_tabla = df_fuente[
        df_fuente["Tipo"].astype(str).str.strip().str.upper() == tipo_filtrar
    ][["Descripción", "Unidad", "Valor Unitario", "Cantidad"]].copy()

    if df_tabla.empty:
        st.info(f"Sin información para {titulo.lower()}.")
        return 0.0

    df_tabla["VALOR TOTAL"] = (
        pd.to_numeric(df_tabla["Valor Unitario"], errors="coerce").fillna(0.0)
        * pd.to_numeric(df_tabla["Cantidad"], errors="coerce").fillna(0.0)
    )

    st.data_editor(
        df_tabla,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        disabled=["Descripción", "Unidad", "Valor Unitario", "Cantidad", "VALOR TOTAL"],
        column_config={
            "Descripción": st.column_config.TextColumn("Descripción"),
            "Unidad": st.column_config.TextColumn("Unidad"),
            "Valor Unitario": st.column_config.NumberColumn("Valor Unitario", format="%.2f"),
            "Cantidad": st.column_config.NumberColumn("Cantidad", format="%.4f"),
            "VALOR TOTAL": st.column_config.NumberColumn("VALOR TOTAL", format="%.2f"),
        },
        key=f"apu_tabla_{tipo_filtrar.lower()}",
    )

    total = float(df_tabla["VALOR TOTAL"].sum())

    c_total_1, c_total_2 = st.columns([5, 1])
    with c_total_1:
        st.markdown(f"**Total {titulo.lower()}**")
    with c_total_2:
        st.markdown(f"**{total:,.2f}**")

    st.divider()
    return total


total_materiales = _tabla_apu_desde_excel("Materiales", df_apu_seleccionado, "MATERIAL")
total_equipos = _tabla_apu_desde_excel("Equipos", df_apu_seleccionado, "EQUIPO")
total_mano_obra = _tabla_apu_desde_excel("Mano de obra", df_apu_seleccionado, "MANO DE OBRA")

total_apu = total_materiales + total_equipos + total_mano_obra

c_final_1, c_final_2 = st.columns([5, 1])
with c_final_1:
    st.markdown("## TOTAL APU")
with c_final_2:
    st.markdown(f"## {total_apu:,.2f}")
