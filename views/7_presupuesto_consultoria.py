import pandas as pd
import streamlit as st
from supabase_state import cargar_estado, guardar_estado

st.title("PRESUPUESTO CONSULTORIA")

cronograma_datos = st.session_state.get("cronograma_datos", {}) or {}
tipo_presupuesto_proyecto = str(cronograma_datos.get("tipo_presupuesto_proyecto", "Obra") or "Obra").strip()

if tipo_presupuesto_proyecto != "Consultoría":
    st.warning("Este proyecto está clasificado como Obra. Los ítems no se cargan en Presupuesto Consultoría.")
    st.stop()

alcance = st.session_state.get("alcance_datos", {}) or {}
nombre_proyecto = alcance.get("nombre_proyecto", "") or "SIN NOMBRE DEFINIDO"
st.markdown("### Encabezado")

c1, c2, c3 = st.columns([4, 1, 1])
with c1:
    st.text_input("Nombre del proyecto", value=nombre_proyecto, key="pc_nombre_proyecto", disabled=True)
with c2:
    st.number_input("Año", min_value=2000, max_value=2100, value=2026, step=1, key="pc_anio")
with c3:
    st.number_input("% IVA", min_value=0.0, max_value=100.0, value=19.0, step=0.1, key="pc_iva_pct")

st.divider()

alcance = st.session_state.get("alcance_datos", {}) or {}

try:
    apus_consultoria_datos = cargar_estado("apus_consultoria") or {}
except Exception:
    apus_consultoria_datos = {}

registros_apus_consultoria = apus_consultoria_datos.get("registros_por_oci", {}) or {}

mapa_costos_directos_apu = {
    str(oci_id).strip(): float(pd.to_numeric(registro.get("costo_directo_total", 0.0), errors="coerce") or 0.0)
    for oci_id, registro in registros_apus_consultoria.items()
    if str(oci_id).strip()
}

grupos_consultoria = []
grupos_consultoria_origen = []

if "objetivos" in alcance and "edt_data" in alcance:
    for i, obj in enumerate(alcance["objetivos"]):
        oid = obj.get("id")
        cod_obj = f"{i+1}"
        nom_obj = obj.get("texto", "Objetivo")
        productos = alcance["edt_data"].get(oid, []) or []

        rows_obj = []

        for j, p in enumerate(productos):
            cod_prod = f"{cod_obj}.{j+1}"
            nom_prod = p.get("nombre", "Producto")
            actividades = p.get("actividades", []) or []

            if len(actividades) == 0:
                row_prod = {
                    "id": str(p.get("id", "") or "").strip(),
                    "ITEM": cod_prod,
                    "DESCRIPCIÓN": nom_prod,
                }
                rows_obj.append(row_prod)
                grupos_consultoria_origen.append(
                    {
                        "group_id": cod_obj,
                        "titulo": f"{cod_obj} {nom_obj}",
                        "rows": [row_prod.copy()],
                    }
                )
            else:
                rows_prod = []

                for k, a in enumerate(actividades):
                    cod_act = f"{cod_prod}.{k+1}"
                    nom_act = a.get("nombre", "Actividad")
                    paquetes = a.get("paquetes", []) or []

                    if len(paquetes) == 0:
                        row_act = {
                            "id": str(a.get("id", "") or "").strip(),
                            "ITEM": cod_act,
                            "DESCRIPCIÓN": nom_act,
                        }
                        rows_prod.append(row_act)
                    else:
                        rows_act = []

                        for l, pq in enumerate(paquetes):
                            cod_paq = f"{cod_act}.{l+1}"
                            nom_paq = pq.get("nombre", "Paquete")
                            row_paq = {
                                "id": str(pq.get("id", "") or "").strip(),
                                "ITEM": cod_paq,
                                "DESCRIPCIÓN": nom_paq,
                            }
                            rows_act.append(row_paq)

                        if rows_act:
                            grupos_consultoria.append(
                                {
                                    "group_id": cod_act,
                                    "titulo": f"{cod_act} {nom_act}",
                                    "rows": rows_act,
                                }
                            )
                            grupos_consultoria_origen.append(
                                {
                                    "group_id": cod_act,
                                    "titulo": f"{cod_act} {nom_act}",
                                    "rows": [r.copy() for r in rows_act],
                                }
                            )

                if rows_prod:
                    grupos_consultoria.append(
                        {
                            "group_id": cod_prod,
                            "titulo": f"{cod_prod} {nom_prod}",
                            "rows": rows_prod,
                        }
                    )
                    grupos_consultoria_origen.append(
                        {
                            "group_id": cod_prod,
                            "titulo": f"{cod_prod} {nom_prod}",
                            "rows": [r.copy() for r in rows_prod],
                        }
                    )

        if rows_obj:
            grupos_consultoria.append(
                {
                    "group_id": cod_obj,
                    "titulo": f"{cod_obj} {nom_obj}",
                    "rows": rows_obj,
                }
            )
            grupos_consultoria_origen.append(
                {
                    "group_id": cod_obj,
                    "titulo": f"{cod_obj} {nom_obj}",
                    "rows": [r.copy() for r in rows_obj],
                }
            )

if not grupos_consultoria:
    st.warning("No hay nodos terminales de la EDT para cargar en Presupuesto Consultoría.")
    st.stop()

try:
    presupuesto_consultoria_guardado = cargar_estado("presupuesto_consultoria") or {}
except Exception:
    presupuesto_consultoria_guardado = {}

if "pc_items_data" not in st.session_state:
    st.session_state["pc_items_data"] = presupuesto_consultoria_guardado.get("pc_items_data", {}) or {}

items_actuales = st.session_state.get("pc_items_data", {}) or {}

if isinstance(items_actuales, list):
    items_actuales = {}

for grupo in grupos_consultoria:
    gid = grupo["group_id"]
    filas_guardadas = items_actuales.get(gid, []) or []

    nuevas_filas = []
    for idx, r in enumerate(grupo["rows"]):
        fila_guardada = filas_guardadas[idx] if idx < len(filas_guardadas) else {}
        item_codigo = str(r.get("ITEM", "") or "").strip()
        costo_unitario_apu = float(mapa_costos_directos_apu.get(item_codigo, 0.0) or 0.0)
        cantidad = float(pd.to_numeric(fila_guardada.get("CANTIDAD", 0.0), errors="coerce") or 0.0)
        subtotal = cantidad * costo_unitario_apu
        iva = subtotal * 0.19
        total = subtotal * 1.19

        nuevas_filas.append(
            {
                "ITEM": r["ITEM"],
                "DESCRIPCIÓN": r["DESCRIPCIÓN"],
                "FUENTE": "Cotización",
                "UNIDAD": str(fila_guardada.get("UNIDAD", "") or ""),
                "CANTIDAD": cantidad,
                "COSTO UNITARIO": costo_unitario_apu,
                "SUBTOTAL": subtotal,
                "IVA": iva,
                "TOTAL": total,
            }
        )

    items_actuales[gid] = nuevas_filas

st.session_state["pc_items_data"] = items_actuales
st.session_state["pc_grupos_origen"] = [
    {
        "group_id": str(r["ITEM"]).strip(),
        "titulo": f'{str(r["ITEM"]).strip()} {str(r["DESCRIPCIÓN"]).strip()}'.strip(),
        "rows": [r.copy()],
    }
    for g in grupos_consultoria
    for r in g["rows"]
]

try:
    guardar_estado(
        "presupuesto_consultoria",
        {
            "pc_items_data": st.session_state.get("pc_items_data", {}) or {},
            "pc_grupos_origen": st.session_state.get("pc_grupos_origen", []) or [],
        },
    )
except Exception:
    pass

iva_pct = 19.0


def _recalcular_y_guardar_group(group_id_cb: str, df_actual: pd.DataFrame) -> None:
    df_actual = df_actual.copy()

    df_actual["FUENTE"] = "Cotización"
    df_actual["UNIDAD"] = df_actual["UNIDAD"].astype(str)

    df_actual["CANTIDAD"] = pd.to_numeric(df_actual["CANTIDAD"], errors="coerce").fillna(0.0)
    df_actual["COSTO UNITARIO"] = pd.to_numeric(df_actual["COSTO UNITARIO"], errors="coerce").fillna(0.0)
    df_actual["SUBTOTAL"] = df_actual["CANTIDAD"] * df_actual["COSTO UNITARIO"]
    df_actual["IVA"] = df_actual["SUBTOTAL"] * (iva_pct / 100.0)
    df_actual["TOTAL"] = df_actual["SUBTOTAL"] * (1 + (iva_pct / 100.0))

    st.session_state["pc_items_data"][group_id_cb] = df_actual.to_dict(orient="records")

    try:
        guardar_estado(
            "presupuesto_consultoria",
            {
                "pc_items_data": st.session_state.get("pc_items_data", {}) or {},
                "pc_grupos_origen": st.session_state.get("pc_grupos_origen", []) or [],
            },
        )
    except Exception:
        pass


def _make_on_change_pc_items(group_id_cb):
    def _on_change():
        widget_state = st.session_state.get(f"pc_tabla_items_{group_id_cb}", {}) or {}
        edited_rows = widget_state.get("edited_rows", {}) or {}

        data_actual = st.session_state.get("pc_items_data", {}).get(group_id_cb, [])
        df_actual = pd.DataFrame(data_actual).copy()

        if df_actual.empty:
            return

        for row_idx, cambios in edited_rows.items():
            if row_idx >= len(df_actual):
                continue
            for col_name, valor in cambios.items():
                if col_name in df_actual.columns:
                    df_actual.at[row_idx, col_name] = valor

        _recalcular_y_guardar_group(group_id_cb, df_actual)

    return _on_change


total_presupuesto = 0.0

for grupo in grupos_consultoria:
    group_id = grupo["group_id"]
    st.markdown(f"### {grupo['titulo']}")

    df_base = pd.DataFrame(st.session_state["pc_items_data"].get(group_id, [])).copy()

    if df_base.empty:
        df_base = pd.DataFrame(
            [
                {
                    "ITEM": r["ITEM"],
                    "DESCRIPCIÓN": r["DESCRIPCIÓN"],
                    "FUENTE": "Cotización",
                    "UNIDAD": "",
                    "CANTIDAD": 0.0,
                    "COSTO UNITARIO": float(mapa_costos_directos_apu.get(str(r["ITEM"]).strip(), 0.0) or 0.0),
                    "SUBTOTAL": 0.0,
                    "IVA": 0.0,
                    "TOTAL": 0.0,
                }
                for r in grupo["rows"]
            ]
        )

    df_base["FUENTE"] = "Cotización"
    df_base["CANTIDAD"] = pd.to_numeric(df_base["CANTIDAD"], errors="coerce").fillna(0.0)
    df_base["COSTO UNITARIO"] = pd.to_numeric(df_base["COSTO UNITARIO"], errors="coerce").fillna(0.0)
    df_base["SUBTOTAL"] = df_base["CANTIDAD"] * df_base["COSTO UNITARIO"]
    df_base["IVA"] = df_base["SUBTOTAL"] * (iva_pct / 100.0)
    df_base["TOTAL"] = df_base["SUBTOTAL"] * (1 + (iva_pct / 100.0))

    edited_df = st.data_editor(
        df_base,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        key=f"pc_tabla_items_{group_id}",
        on_change=_make_on_change_pc_items(group_id),
        column_config={
            "ITEM": st.column_config.TextColumn("ITEM", disabled=True),
            "DESCRIPCIÓN": st.column_config.TextColumn("DESCRIPCIÓN", disabled=True),
            "FUENTE": st.column_config.TextColumn("FUENTE", disabled=True),
            "UNIDAD": st.column_config.TextColumn("UNIDAD"),
            "CANTIDAD": st.column_config.NumberColumn("CANTIDAD", min_value=0.0, step=0.01, format="%.4f"),
            "COSTO UNITARIO": st.column_config.NumberColumn("COSTO UNITARIO", disabled=True, format="%.2f"),
            "SUBTOTAL": st.column_config.NumberColumn("SUBTOTAL", disabled=True, format="%.2f"),
            "IVA": st.column_config.NumberColumn("IVA", disabled=True, format="%.2f"),
            "TOTAL": st.column_config.NumberColumn("TOTAL", disabled=True, format="%.2f"),
        },
        disabled=["ITEM", "DESCRIPCIÓN", "FUENTE", "COSTO UNITARIO", "SUBTOTAL", "IVA", "TOTAL"],
    )

    if edited_df.empty:
        total_actividad = 0.0
    else:
        edited_df = edited_df.copy()
        edited_df["FUENTE"] = "Cotización"
        edited_df["CANTIDAD"] = pd.to_numeric(edited_df["CANTIDAD"], errors="coerce").fillna(0.0)
        edited_df["COSTO UNITARIO"] = pd.to_numeric(edited_df["COSTO UNITARIO"], errors="coerce").fillna(0.0)
        edited_df["SUBTOTAL"] = edited_df["CANTIDAD"] * edited_df["COSTO UNITARIO"]
        edited_df["IVA"] = edited_df["SUBTOTAL"] * (iva_pct / 100.0)
        edited_df["TOTAL"] = edited_df["SUBTOTAL"] * (1 + (iva_pct / 100.0))
        total_actividad = float(pd.to_numeric(edited_df["TOTAL"], errors="coerce").fillna(0.0).sum())

    total_presupuesto += total_actividad
    st.metric("Total actividad", f"${total_actividad:,.2f}")
    st.divider()

st.markdown("## TOTAL PRESUPUESTO")
st.metric("Total presupuesto", f"${total_presupuesto:,.2f}")
