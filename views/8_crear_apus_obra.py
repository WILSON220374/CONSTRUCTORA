import streamlit as st
from supabase_state import cargar_apus_generados_obra, guardar_apus_generados_obra

st.title("CREAR APUS DE OBRA")
botonera_apu_container = st.empty()

if "apus_generados_obra" not in st.session_state:
    try:
        st.session_state["apus_generados_obra"] = cargar_apus_generados_obra()
    except RuntimeError as e:
        st.error(str(e))
        st.stop()
    except Exception:
        st.error("No fue posible cargar los APUs generados de obra.")
        st.stop()

presupuesto_obra_datos = st.session_state.get("presupuesto_obra_datos", {}) or {}
items_presupuesto = presupuesto_obra_datos.get("items", {}) or {}

alcance = st.session_state.get("alcance_datos", {}) or {}

mapa_ids_edt = {}

if "objetivos" in alcance and "edt_data" in alcance:
    for i, obj in enumerate(alcance["objetivos"]):
        oid = obj.get("id")
        cod_obj = f"{i+1}"
        productos = alcance["edt_data"].get(oid, [])

        for j, p in enumerate(productos):
            pid = p["id"]
            cod_prod = f"{cod_obj}.{j+1}"
            nom_prod = p.get("nombre", "Producto")
            actividades = p.get("actividades", [])

            if len(actividades) == 0:
                mapa_ids_edt[str(pid)] = {
                    "item": cod_prod,
                    "descripcion": nom_prod,
                }

            for k, a in enumerate(actividades):
                aid = a["id"]
                cod_act = f"{cod_prod}.{k+1}"
                nom_act = a.get("nombre", "Actividad")
                paquetes = a.get("paquetes", [])

                if len(paquetes) == 0:
                    mapa_ids_edt[str(aid)] = {
                        "item": cod_act,
                        "descripcion": nom_act,
                    }

                for l, pq in enumerate(paquetes):
                    pqid = pq["id"]
                    cod_paq = f"{cod_act}.{l+1}"
                    nom_paq = pq.get("nombre", "Paquete")

                    mapa_ids_edt[str(pqid)] = {
                        "item": cod_paq,
                        "descripcion": nom_paq,
                    }

items_apu_generado = []
for item_id, item_data in items_presupuesto.items():
    fuente = str(item_data.get("fuente", "") or "").strip()
    if fuente == "APU generado":
        info_edt = mapa_ids_edt.get(str(item_id), {})
        items_apu_generado.append(
            {
                "id": item_id,
                "item": info_edt.get("item", str(item_id)),
                "descripcion": info_edt.get("descripcion", "Sin descripción"),
                "fuente": fuente,
            }
        )

if not items_apu_generado:
    st.warning("No hay ítems en Presupuesto de Obra con fuente 'APU generado'.")
    st.stop()

import pandas as pd

@st.cache_data
def _cargar_base_apu():
    ruta = "data/Copia de APU.xlsx"
    return pd.read_excel(ruta)

st.markdown("### Ítems pendientes de APU generado")

opciones_items_apu = {
    f"{item['item']} - {item['descripcion']}": item["id"]
    for item in items_apu_generado
}

opciones_items_apu_labels = [""] + list(opciones_items_apu.keys())

def _on_change_item_apu_obra():
    label_sel = str(st.session_state.get("apu_obra_item_seleccionado", "") or "").strip()
    item_id_sel = opciones_items_apu.get(label_sel, "")

    apu_existente = (st.session_state.get("apus_generados_obra", {}) or {}).get(item_id_sel)

    if apu_existente:
        st.session_state["apu_obra_cod_base"] = apu_existente.get("apu_base_codigo", "")
        st.session_state["apu_obra_actividad_base"] = apu_existente.get("apu_base_actividad", "")
        st.session_state["apu_obra_data_materiales"] = apu_existente.get("materiales", [])
        st.session_state["apu_obra_data_equipos"] = apu_existente.get("equipos", [])
        st.session_state["apu_obra_data_mano_de_obra"] = apu_existente.get("mano_obra", [])

        base_actual = f"{apu_existente.get('apu_base_codigo', '')}||{apu_existente.get('apu_base_actividad', '')}"
        st.session_state["apu_obra_base_cargado_materiales"] = base_actual
        st.session_state["apu_obra_base_cargado_equipos"] = base_actual
        st.session_state["apu_obra_base_cargado_mano_de_obra"] = base_actual
    else:
        st.session_state["apu_obra_cod_base"] = ""
        st.session_state["apu_obra_actividad_base"] = ""
        st.session_state["apu_obra_data_materiales"] = []
        st.session_state["apu_obra_data_equipos"] = []
        st.session_state["apu_obra_data_mano_de_obra"] = []

        st.session_state["apu_obra_base_cargado_materiales"] = ""
        st.session_state["apu_obra_base_cargado_equipos"] = ""
        st.session_state["apu_obra_base_cargado_mano_de_obra"] = ""

item_apu_label = st.selectbox(
    "Selecciona el ítem del presupuesto",
    options=opciones_items_apu_labels,
    key="apu_obra_item_seleccionado",
    on_change=_on_change_item_apu_obra,
)

item_apu_seleccionado = opciones_items_apu.get(item_apu_label, "")

if not item_apu_seleccionado:
    st.info("Selecciona un ítem del presupuesto para cargar o generar su APU.")
    st.stop()

st.caption(f"Ítem seleccionado: {item_apu_label}")

try:
    df_apu_base = _cargar_base_apu()
except Exception as e:
    st.error("No se pudo leer data/Copia de APU.xlsx")
    st.code(str(e))
    st.stop()

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

if "apu_obra_cod_base" not in st.session_state:
    st.session_state["apu_obra_cod_base"] = ""
if "apu_obra_actividad_base" not in st.session_state:
    st.session_state["apu_obra_actividad_base"] = ""

def _reset_bloques_apu_obra():
    st.session_state["apu_obra_data_materiales"] = []
    st.session_state["apu_obra_data_equipos"] = []
    st.session_state["apu_obra_data_mano_de_obra"] = []

    st.session_state["apu_obra_base_cargado_materiales"] = ""
    st.session_state["apu_obra_base_cargado_equipos"] = ""
    st.session_state["apu_obra_base_cargado_mano_de_obra"] = ""

def _on_change_apu_obra_cod():
    cod_sel = str(st.session_state.get("apu_obra_cod_base", "") or "").strip()
    if not cod_sel:
        st.session_state["apu_obra_actividad_base"] = ""
        _reset_bloques_apu_obra()
        return

    df_sync = df_apu_base[
        df_apu_base["cod_actividad"].astype(str).str.strip() == cod_sel
    ]
    if not df_sync.empty:
        st.session_state["apu_obra_actividad_base"] = str(df_sync.iloc[0].get("actividad", "") or "").strip()

    _reset_bloques_apu_obra()

def _on_change_apu_obra_actividad():
    act_sel = str(st.session_state.get("apu_obra_actividad_base", "") or "").strip()
    if not act_sel:
        st.session_state["apu_obra_cod_base"] = ""
        _reset_bloques_apu_obra()
        return

    df_sync = df_apu_base[
        df_apu_base["actividad"].astype(str).str.strip() == act_sel
    ]
    if not df_sync.empty:
        st.session_state["apu_obra_cod_base"] = str(df_sync.iloc[0].get("cod_actividad", "") or "").strip()

    _reset_bloques_apu_obra()

st.markdown("### APU base para asociar")

c1, c2 = st.columns([1, 3])
with c1:
    cod_apu_base = st.selectbox(
        "Código APU base",
        options=[""] + codigos_actividad,
        key="apu_obra_cod_base",
        on_change=_on_change_apu_obra_cod,
    )
with c2:
    actividad_apu_base = st.selectbox(
        "Actividad APU base",
        options=[""] + actividades,
        key="apu_obra_actividad_base",
        on_change=_on_change_apu_obra_actividad,
    )

st.caption(f"APU base seleccionado: {cod_apu_base or actividad_apu_base or 'Ninguno'}")

def _buscar_apu_base_seleccionado(df_base, cod_actividad, actividad):
    cod_actividad = str(cod_actividad or "").strip()
    actividad = str(actividad or "").strip()

    if cod_actividad:
        df_filtrado = df_base[
            df_base["cod_actividad"].astype(str).str.strip() == cod_actividad
        ]
        if not df_filtrado.empty:
            return df_filtrado.copy()

    if actividad:
        df_filtrado = df_base[
            df_base["actividad"].astype(str).str.strip() == actividad
        ]
        if not df_filtrado.empty:
            return df_filtrado.copy()

    return pd.DataFrame(columns=df_base.columns)

df_apu_seleccionado = _buscar_apu_base_seleccionado(df_apu_base, cod_apu_base, actividad_apu_base)

if df_apu_seleccionado.empty:
    st.info("Selecciona un APU base para cargar su detalle.")
    st.stop()

unidad_apu = ""
for col_unidad in ["unidad", "Unidad", "UNIDAD"]:
    if col_unidad in df_apu_seleccionado.columns:
        series_unidad = (
            df_apu_seleccionado[col_unidad]
            .astype(str)
            .str.strip()
        )
        series_unidad = series_unidad[series_unidad != ""]
        if not series_unidad.empty:
            unidad_apu = str(series_unidad.iloc[0] or "").strip()
            break

st.info(f"Unidad del APU base: {unidad_apu or 'No definida'}")
def _tabla_apu_por_tipo(titulo, df_fuente, tipos_validos):
    st.markdown(f"### {titulo}")

    key_data = f"apu_obra_data_{titulo.lower().replace(' ', '_')}"
    key_widget = f"apu_obra_tabla_{titulo.lower().replace(' ', '_')}"

    key_base = f"apu_obra_base_cargado_{titulo.lower().replace(' ', '_')}"
    base_actual = f"{cod_apu_base}||{actividad_apu_base}"

    if key_data not in st.session_state or st.session_state.get(key_base) != base_actual:
        df_inicial = df_fuente[
            df_fuente["Tipo"].astype(str).str.strip().str.upper().isin(tipos_validos)
        ][["Descripción", "Unidad", "Valor Unitario", "Cantidad"]].copy()

        if df_inicial.empty:
            st.session_state[key_data] = []
            st.session_state[key_base] = base_actual
            st.info(f"Sin información para {titulo.lower()}.")
            return 0.0

        st.session_state[key_data] = df_inicial.to_dict(orient="records")
        st.session_state[key_base] = base_actual

    df_tabla = pd.DataFrame(st.session_state[key_data]).copy()

    if df_tabla.empty:
        st.info(f"Sin información para {titulo.lower()}.")
        return 0.0

    df_tabla = df_tabla[["Descripción", "Unidad", "Cantidad", "Valor Unitario"]].copy()

    df_tabla["VALOR TOTAL"] = (
        pd.to_numeric(df_tabla["Valor Unitario"], errors="coerce").fillna(0.0)
        * pd.to_numeric(df_tabla["Cantidad"], errors="coerce").fillna(0.0)
    )

    df_tabla = df_tabla[["Descripción", "Unidad", "Cantidad", "Valor Unitario", "VALOR TOTAL"]]
    def _on_change_tabla_apu_tipo():
        widget_state = st.session_state.get(key_widget, {}) or {}
        edited_rows = widget_state.get("edited_rows", {}) or {}
        added_rows = widget_state.get("added_rows", []) or []

        data_actual = st.session_state.get(key_data, [])
        df_actual = pd.DataFrame(data_actual).copy()

        if df_actual.empty:
            df_actual = pd.DataFrame(columns=["Descripción", "Unidad", "Valor Unitario", "Cantidad"])

        for row_idx, cambios in edited_rows.items():
            if row_idx >= len(df_actual):
                continue
            for col_name, valor in cambios.items():
                if col_name in df_actual.columns:
                    df_actual.at[row_idx, col_name] = valor

        for nueva_fila in added_rows:
            fila_limpia = {
                "Descripción": nueva_fila.get("Descripción", "") if isinstance(nueva_fila, dict) else "",
                "Unidad": nueva_fila.get("Unidad", "") if isinstance(nueva_fila, dict) else "",
                "Valor Unitario": nueva_fila.get("Valor Unitario", 0.0) if isinstance(nueva_fila, dict) else 0.0,
                "Cantidad": nueva_fila.get("Cantidad", 0.0) if isinstance(nueva_fila, dict) else 0.0,
            }
            df_actual = pd.concat([df_actual, pd.DataFrame([fila_limpia])], ignore_index=True)

        st.session_state[key_data] = df_actual.to_dict(orient="records")

    edited_df = st.data_editor(
        df_tabla,
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic",
        key=key_widget,
        on_change=_on_change_tabla_apu_tipo,
        column_config={
            "Descripción": st.column_config.TextColumn("Descripción"),
            "Unidad": st.column_config.TextColumn("Unidad"),
            "Valor Unitario": st.column_config.NumberColumn("Valor Unitario", min_value=0.0, step=0.01, format="%.4f"),
            "Cantidad": st.column_config.NumberColumn("Cantidad", min_value=0.0, step=0.0000000000001, format="%.4f"),
            "VALOR TOTAL": st.column_config.NumberColumn("VALOR TOTAL", disabled=True, format="%.2f"),
        },
        disabled=["VALOR TOTAL"],
    )

    if not edited_df.empty:
        edited_df = edited_df.copy()
        edited_df["VALOR TOTAL"] = (
            pd.to_numeric(edited_df["Valor Unitario"], errors="coerce").fillna(0.0)
            * pd.to_numeric(edited_df["Cantidad"], errors="coerce").fillna(0.0)
        )

        st.session_state[key_data] = edited_df[
            ["Descripción", "Unidad", "Cantidad", "Valor Unitario"]
        ].to_dict(orient="records")

        total = float(pd.to_numeric(edited_df["VALOR TOTAL"], errors="coerce").fillna(0.0).sum())
    else:
        st.session_state[key_data] = []
        total = 0.0

    c_total_1, c_total_2 = st.columns([5, 1])
    with c_total_1:
        st.markdown(f"**Total {titulo.lower()}**")
    with c_total_2:
        st.markdown(f"**{total:,.2f}**")

    st.divider()
    return total
    
total_materiales = _tabla_apu_por_tipo("Materiales", df_apu_seleccionado, {"MATERIAL", "MATERIALES"})
total_equipos = _tabla_apu_por_tipo("Equipos", df_apu_seleccionado, {"EQUIPO", "EQUIPOS"})
total_mano_obra = _tabla_apu_por_tipo("Mano de obra", df_apu_seleccionado, {"MANO DE OBRA", "MANO_OBRA", "MO"})

total_apu = total_materiales + total_equipos + total_mano_obra

c_final_1, c_final_2 = st.columns([5, 1])
with c_final_1:
    st.markdown("## TOTAL APU")
with c_final_2:
    st.markdown(f"## {total_apu:,.2f}")

if "apus_generados_obra" not in st.session_state:
    st.session_state["apus_generados_obra"] = {}

apus_generados_obra = st.session_state.get("apus_generados_obra", {}) or {}
apu_guardado_actual = apus_generados_obra.get(item_apu_seleccionado)

if apu_guardado_actual:
    st.info(f"Este ítem ya tiene un APU asociado: {apu_guardado_actual.get('apu_base_codigo', '')} - {apu_guardado_actual.get('apu_base_actividad', '')}")

with botonera_apu_container.container():
    st.markdown("### Gestión del APU generado")

    if apu_guardado_actual:
        c_btn1, c_btn2 = st.columns(2)

        with c_btn1:
            guardar_cambios_apu = st.button("Guardar cambios", use_container_width=True)
        with c_btn2:
            borrar_apu = st.button("Borrar APU", use_container_width=True)

        guardar_apu = False
        actualizar_apu = False
    else:
        c_btn1 = st.columns(1)[0]

        with c_btn1:
            guardar_apu = st.button("Generar APU", use_container_width=True)

        actualizar_apu = False
        guardar_cambios_apu = False
        borrar_apu = False
        
if guardar_apu:
    if apu_guardado_actual:
        st.warning("Este ítem ya tiene un APU guardado. Debes modificarlo, guardar cambios o borrarlo antes de generar otro.")
    else:
        st.session_state["apus_generados_obra"][item_apu_seleccionado] = {
            "item_id": item_apu_seleccionado,
            "item_label": item_apu_label,
            "apu_base_codigo": cod_apu_base,
            "apu_base_actividad": actividad_apu_base,
            "unidad_apu": unidad_apu,
            "materiales": st.session_state.get("apu_obra_data_materiales", []),
            "equipos": st.session_state.get("apu_obra_data_equipos", []),
            "mano_obra": st.session_state.get("apu_obra_data_mano_de_obra", []),
            "total_materiales": total_materiales,
            "total_equipos": total_equipos,
            "total_mano_obra": total_mano_obra,
            "total_apu": total_apu,
        }
        try:
            guardar_apus_generados_obra(st.session_state["apus_generados_obra"])
            st.success("APU generado correctamente.")
        except Exception:
            st.error("La sesión expiró. Inicia sesión de nuevo para guardar el APU.")

if guardar_cambios_apu:
    if not apu_guardado_actual:
        st.warning("Este ítem todavía no tiene un APU generado. Usa primero Generar APU.")
    else:
        st.session_state["apus_generados_obra"][item_apu_seleccionado] = {
            "item_id": item_apu_seleccionado,
            "item_label": item_apu_label,
            "apu_base_codigo": cod_apu_base,
            "apu_base_actividad": actividad_apu_base,
            "unidad_apu": unidad_apu,
            "materiales": st.session_state.get("apu_obra_data_materiales", []),
            "equipos": st.session_state.get("apu_obra_data_equipos", []),
            "mano_obra": st.session_state.get("apu_obra_data_mano_de_obra", []),
            "total_materiales": total_materiales,
            "total_equipos": total_equipos,
            "total_mano_obra": total_mano_obra,
            "total_apu": total_apu,
        }
        try:
            guardar_apus_generados_obra(st.session_state["apus_generados_obra"])
            st.success("Cambios guardados correctamente.")
        except Exception:
            st.error("La sesión expiró. Inicia sesión de nuevo para guardar los cambios del APU.")

if borrar_apu:
    if not apu_guardado_actual:
        st.warning("No hay un APU guardado para este ítem.")
    else:
        st.session_state["apus_generados_obra"].pop(item_apu_seleccionado, None)
        try:
            guardar_apus_generados_obra(st.session_state["apus_generados_obra"])
            st.session_state["apu_obra_data_materiales"] = []
            st.session_state["apu_obra_data_equipos"] = []
            st.session_state["apu_obra_data_mano_de_obra"] = []
            st.success("APU generado borrado correctamente.")
        except Exception:
            st.error("La sesión expiró. Inicia sesión de nuevo para borrar el APU.")

if guardar_cambios_apu:
    if not apu_guardado_actual:
        st.warning("Este ítem todavía no tiene un APU generado. Usa primero Generar APU.")
    else:
        st.session_state["apus_generados_obra"][item_apu_seleccionado] = {
            "item_id": item_apu_seleccionado,
            "item_label": item_apu_label,
            "apu_base_codigo": cod_apu_base,
            "apu_base_actividad": actividad_apu_base,
            "materiales": st.session_state.get("apu_obra_data_materiales", []),
            "equipos": st.session_state.get("apu_obra_data_equipos", []),
            "mano_obra": st.session_state.get("apu_obra_data_mano_de_obra", []),
            "total_materiales": total_materiales,
            "total_equipos": total_equipos,
            "total_mano_obra": total_mano_obra,
            "total_apu": total_apu,
        }
        try:
            guardar_apus_generados_obra(st.session_state["apus_generados_obra"])
            st.success("Cambios guardados correctamente.")
        except Exception:
            st.error("La sesión expiró. Inicia sesión de nuevo para guardar los cambios del APU.")

if borrar_apu:
    if not apu_guardado_actual:
        st.warning("No hay un APU guardado para este ítem.")
    else:
        st.session_state["apus_generados_obra"].pop(item_apu_seleccionado, None)
        try:
            guardar_apus_generados_obra(st.session_state["apus_generados_obra"])
            st.session_state["apu_obra_data_materiales"] = []
            st.session_state["apu_obra_data_equipos"] = []
            st.session_state["apu_obra_data_mano_de_obra"] = []
            st.success("APU generado borrado correctamente.")
        except Exception:
            st.error("La sesión expiró. Inicia sesión de nuevo para borrar el APU.")

if borrar_apu:
    if not apu_guardado_actual:
        st.warning("No hay un APU guardado para este ítem.")
    else:
        st.session_state["apus_generados_obra"].pop(item_apu_seleccionado, None)
        guardar_apus_generados_obra(st.session_state["apus_generados_obra"])
        st.session_state["apu_obra_data_materiales"] = []
        st.session_state["apu_obra_data_equipos"] = []
        st.session_state["apu_obra_data_mano_de_obra"] = []
        st.success("APU generado borrado correctamente.")
