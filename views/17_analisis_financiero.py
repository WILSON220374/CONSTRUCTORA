import copy
import json
import uuid

import numpy_financial as npf
import pandas as pd
import streamlit as st

from supabase_state import cargar_estado, guardar_estado


STATE_KEY = "analisis_financiero_datos"
LOADED_KEY = "_analisis_financiero_cargado"
STORAGE_KEY = "analisis_financiero"


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


def _tabla_base_anios() -> list:
    filas = []
    for anio in range(1, 11):
        filas.append(
            {
                "AÑO": anio,
                "CANTIDAD": 0.0,
                "VALOR UNITARIO": 0.0,
                "VALOR TOTAL": 0.0,
            }
        )
    return filas


def _nuevo_bloque(tipo: str, metodo: str = "") -> dict:
    return {
        "id": str(uuid.uuid4()),
        "tipo": tipo,
        "metodo": metodo if tipo == "Beneficio" else "",
        "descripcion": "",
        "unidad": "",
        "filas": _tabla_base_anios(),
        "total_general": 0.0,
    }


def _normalizar_filas(filas) -> list:
    filas_norm = []

    if not isinstance(filas, list):
        filas = []

    mapa_existente = {}
    for fila in filas:
        if isinstance(fila, dict):
            anio = int(_safe_float(fila.get("AÑO"), 0))
            if anio > 0:
                mapa_existente[anio] = fila

    for anio in range(1, 11):
        fila = mapa_existente.get(anio, {})
        cantidad = _safe_float(fila.get("CANTIDAD"), 0.0)
        valor_unitario = _safe_float(fila.get("VALOR UNITARIO"), 0.0)
        valor_total = round(cantidad * valor_unitario, 2)

        filas_norm.append(
            {
                "AÑO": anio,
                "CANTIDAD": cantidad,
                "VALOR UNITARIO": valor_unitario,
                "VALOR TOTAL": valor_total,
            }
        )

    return filas_norm


def _normalizar_bloque(bloque: dict) -> dict:
    if not isinstance(bloque, dict):
        bloque = {}

    tipo = _safe_str(bloque.get("tipo"))
    if tipo not in ("Ingreso", "Beneficio"):
        tipo = "Ingreso"

    metodo = _safe_str(bloque.get("metodo"))
    if tipo != "Beneficio":
        metodo = ""
    elif metodo not in ("Costos evitados o inducidos", "Precios hedónicos"):
        metodo = "Costos evitados o inducidos"

    filas = _normalizar_filas(bloque.get("filas", []))
    total_general = round(sum(_safe_float(f["VALOR TOTAL"]) for f in filas), 2)

    return {
        "id": _safe_str(bloque.get("id")) or str(uuid.uuid4()),
        "tipo": tipo,
        "metodo": metodo,
        "descripcion": _safe_str(bloque.get("descripcion")),
        "unidad": _safe_str(bloque.get("unidad")),
        "filas": filas,
        "total_general": total_general,
    }


def _normalizar_data(data) -> dict:
    if not isinstance(data, dict):
        data = {}

    bloques = data.get("bloques", [])
    if not isinstance(bloques, list):
        bloques = []

    bloques_norm = [_normalizar_bloque(b) for b in bloques]

    return {
        "bloques": bloques_norm,
        "tasa_descuento": _safe_float(data.get("tasa_descuento", 0.0), 0.0),
        "rpc_bien": _safe_str(data.get("rpc_bien")),
        "rpc_valor": _safe_float(data.get("rpc_valor", 0.0), 0.0),
    }

def _cargar_data_inicial():
    if LOADED_KEY in st.session_state:
        return

    try:
        data = cargar_estado(STORAGE_KEY) or {}
    except Exception:
        data = {}

    st.session_state[STATE_KEY] = _normalizar_data(data)
    st.session_state[LOADED_KEY] = True


def _guardar_data(data: dict):
    data_normalizada = _normalizar_data(data)
    st.session_state[STATE_KEY] = data_normalizada
    guardar_estado(STORAGE_KEY, data_normalizada)


def _catalogo_rpc() -> pd.DataFrame:
    try:
        df_rpc = pd.read_excel("data/razon precio cuenta.xlsx")
    except Exception:
        return pd.DataFrame(columns=["Bien", "RPC"])

    columnas = {col: str(col).strip() for col in df_rpc.columns}
    df_rpc = df_rpc.rename(columns=columnas)

    columnas_requeridas = ["Bien", "RPC"]
    for columna in columnas_requeridas:
        if columna not in df_rpc.columns:
            df_rpc[columna] = ""

    df_rpc = df_rpc[["Bien", "RPC"]].copy()
    df_rpc["Bien"] = df_rpc["Bien"].astype(str).str.strip()
    df_rpc["RPC"] = pd.to_numeric(df_rpc["RPC"], errors="coerce").fillna(0.0)

    df_rpc = df_rpc[df_rpc["Bien"] != ""].drop_duplicates(subset=["Bien"]).reset_index(drop=True)
    return df_rpc


def _tipo_presupuesto_proyecto() -> str:

    cronograma_datos = st.session_state.get("cronograma_datos", {}) or {}
    valor_cronograma = _safe_str(cronograma_datos.get("tipo_presupuesto_proyecto"))
    if valor_cronograma in ("Obra", "Consultoría"):
        return valor_cronograma

    return "Obra"

def _consolidado_por_tipo(bloques: list, tipo_objetivo: str) -> dict:
    consolidado = {anio: 0.0 for anio in range(0, 11)}

    for bloque in bloques:
        if _safe_str(bloque.get("tipo")) != tipo_objetivo:
            continue

        for fila in _normalizar_filas(bloque.get("filas", [])):
            anio = int(_safe_float(fila.get("AÑO", 0), 0))
            if anio in consolidado:
                consolidado[anio] += _safe_float(fila.get("VALOR TOTAL", 0.0), 0.0)

    return {anio: round(valor, 2) for anio, valor in consolidado.items()}


def _total_inversion_consultoria() -> float:
    try:
        presupuesto_consultoria = cargar_estado("presupuesto_consultoria") or {}
    except Exception:
        presupuesto_consultoria = {}

    pc_items_data = presupuesto_consultoria.get("pc_items_data", {}) or {}
    total = 0.0

    if isinstance(pc_items_data, dict):
        for filas in pc_items_data.values():
            if not isinstance(filas, list):
                continue
            for fila in filas:
                if isinstance(fila, dict):
                    total += _safe_float(fila.get("TOTAL", 0.0), 0.0)

    return round(total, 2)


def _total_inversion_obra() -> float:
    try:
        presupuesto_obra = cargar_estado("presupuesto_obra") or {}
    except Exception:
        presupuesto_obra = {}

    try:
        aiu_datos = cargar_estado("aiu") or {}
    except Exception:
        aiu_datos = {}

    try:
        costos_indirectos_datos = cargar_estado("costos_indirectos") or {}
    except Exception:
        costos_indirectos_datos = {}

    resumen = presupuesto_obra.get("resumen", {}) or {}
    costo_directo_total = _safe_float(resumen.get("costo_directo_total", 0.0), 0.0)

    aiu_total = (
        _safe_float(aiu_datos.get("administracion_valor", 0.0), 0.0)
        + _safe_float(aiu_datos.get("imprevistos_valor", 0.0), 0.0)
        + _safe_float(aiu_datos.get("utilidad_valor", 0.0), 0.0)
    )

    otros_costos = 0.0
    registros_por_oci = costos_indirectos_datos.get("registros_por_oci", {}) or {}
    if isinstance(registros_por_oci, dict):
        for registro in registros_por_oci.values():
            if isinstance(registro, dict):
                otros_costos += _safe_float(registro.get("valor_total_final", 0.0), 0.0)

    return round(costo_directo_total + aiu_total + otros_costos, 2)


def _total_inversion_proyecto() -> float:
    if _tipo_presupuesto_proyecto() == "Consultoría":
        return _total_inversion_consultoria()
    return _total_inversion_obra()


def _tabla_flujo_caja(bloques: list) -> pd.DataFrame:
    ingresos = _consolidado_por_tipo(bloques, "Ingreso")
    beneficios = _consolidado_por_tipo(bloques, "Beneficio")
    inversion_total = _total_inversion_proyecto()

    filas = [
        {"CONCEPTO": "Ingresos", **{str(anio): ingresos.get(anio, 0.0) for anio in range(0, 11)}},
        {"CONCEPTO": "Beneficios", **{str(anio): beneficios.get(anio, 0.0) for anio in range(0, 11)}},
        {"CONCEPTO": "Inversión", **{str(anio): 0.0 for anio in range(0, 11)}},
    ]

    filas[2]["0"] = round(inversion_total * -1, 2)

    fila_total = {"CONCEPTO": "Total"}
    for anio in range(0, 11):
        columna = str(anio)
        fila_total[columna] = round(sum(_safe_float(fila.get(columna, 0.0), 0.0) for fila in filas), 2)

    filas.append(fila_total)

    return pd.DataFrame(filas, columns=["CONCEPTO", *[str(anio) for anio in range(0, 11)]])


def _tabla_total_neto(flujo_caja_df: pd.DataFrame, rpc_valor: float) -> pd.DataFrame:
    fila_total = flujo_caja_df[flujo_caja_df["CONCEPTO"] == "Total"]

    if fila_total.empty:
        valores = {str(anio): 0.0 for anio in range(0, 11)}
    else:
        fila_total = fila_total.iloc[0]
        valores = {
            str(anio): round(_safe_float(fila_total.get(str(anio), 0.0), 0.0) * _safe_float(rpc_valor, 0.0), 2)
            for anio in range(0, 11)
        }

    return pd.DataFrame(
        [{"CONCEPTO": "Total Neto", **valores}],
        columns=["CONCEPTO", *[str(anio) for anio in range(0, 11)]],
    )


def _serie_total_neto(total_neto_df: pd.DataFrame) -> list:
    if total_neto_df.empty:
        return [0.0 for _ in range(0, 11)]

    fila = total_neto_df.iloc[0]
    return [_safe_float(fila.get(str(anio), 0.0), 0.0) for anio in range(0, 11)]


def _calcular_vpn(flujos: list, tasa_descuento: float) -> float:
    tasa = _safe_float(tasa_descuento, 0.0) / 100.0
    return round(_safe_float(npf.npv(tasa, flujos), 0.0), 2)


def _calcular_tir(flujos: list):
    try:
        tir = npf.irr(flujos)
        if tir is None:
            return None
        if pd.isna(tir):
            return None
        return round(_safe_float(tir, 0.0) * 100, 2)
    except Exception:
        return None


def _calcular_beneficio_costo(flujos: list):
    beneficios = round(sum(_safe_float(flujos[t], 0.0) for t in range(1, min(len(flujos), 11))), 2)
    costo_inicial = round(_safe_float(flujos[0], 0.0) * -1, 2)

    if costo_inicial <= 0:
        return None

    return round(beneficios / costo_inicial, 4)

def _etiqueta_bloque(bloque: dict, indice: int) -> str:
    tipo = _safe_str(bloque.get("tipo"))
    descripcion = _safe_str(bloque.get("descripcion"))
    metodo = _safe_str(bloque.get("metodo"))

    if tipo == "Beneficio":
        base = f"Beneficio {indice}"
        if metodo:
            base += f" - {metodo}"
    else:
        base = f"Ingreso {indice}"

    if descripcion:
        base += f" | {descripcion}"

    return base


def _render_bloque(bloque: dict, indice: int) -> tuple:
    bloque_id = _safe_str(bloque["id"])
    bloque_editado = copy.deepcopy(bloque)

    with st.container(border=True):
        st.markdown(f"### {_etiqueta_bloque(bloque_editado, indice)}")

        col_tipo, col_metodo, col_eliminar = st.columns([1, 1, 0.6])

        with col_tipo:
            tipo = st.selectbox(
                "Tipo",
                options=["Ingreso", "Beneficio"],
                index=0 if bloque_editado["tipo"] == "Ingreso" else 1,
                key=f"tipo_{bloque_id}",
            )
            bloque_editado["tipo"] = tipo

        with col_metodo:
            if bloque_editado["tipo"] == "Beneficio":
                metodo_opciones = ["Costos evitados o inducidos", "Precios hedónicos"]
                metodo_actual = bloque_editado["metodo"] if bloque_editado["metodo"] in metodo_opciones else metodo_opciones[0]

                metodo = st.selectbox(
                    "Método",
                    options=metodo_opciones,
                    index=metodo_opciones.index(metodo_actual),
                    key=f"metodo_{bloque_id}",
                )
                bloque_editado["metodo"] = metodo
            else:
                st.text_input(
                    "Método",
                    value="",
                    disabled=True,
                    key=f"metodo_disabled_{bloque_id}",
                )
                bloque_editado["metodo"] = ""

        with col_eliminar:
            st.write("")
            st.write("")
            eliminar = st.button(
                "Eliminar",
                key=f"eliminar_{bloque_id}",
                width="stretch",
            )

        col_desc, col_unidad = st.columns(2)

        with col_desc:
            bloque_editado["descripcion"] = st.text_area(
                "Descripción",
                value=bloque_editado["descripcion"],
                key=f"descripcion_{bloque_id}",
                height=120,
            )

        with col_unidad:
            bloque_editado["unidad"] = st.text_input(
                "Unidad",
                value=bloque_editado["unidad"],
                key=f"unidad_{bloque_id}",
            )

        df = pd.DataFrame(_normalizar_filas(bloque_editado["filas"]))
        filas_originales = df.to_dict("records")

        df_editado = st.data_editor(
            df,
            width="stretch",
            hide_index=True,
            num_rows="fixed",
            key=f"tabla_{bloque_id}_{st.session_state.get(f'_refrescar_tabla_{bloque_id}', False)}",
            column_config={
                "AÑO": st.column_config.NumberColumn("AÑO", disabled=True, format="%d"),
                "CANTIDAD": st.column_config.NumberColumn("CANTIDAD", min_value=0.0, step=0.01, format="%.2f"),
                "VALOR UNITARIO": st.column_config.NumberColumn("VALOR UNITARIO", min_value=0.0, step=0.01, format="%.2f"),
                "VALOR TOTAL": st.column_config.NumberColumn("VALOR TOTAL", disabled=True, format="%.2f"),
            },
            disabled=["AÑO", "VALOR TOTAL"],
        )

        filas_actualizadas = []
        total_general = 0.0

        for _, row in df_editado.iterrows():
            anio = int(_safe_float(row.get("AÑO"), 0))
            cantidad = _safe_float(row.get("CANTIDAD"), 0.0)
            valor_unitario = _safe_float(row.get("VALOR UNITARIO"), 0.0)
            valor_total = round(cantidad * valor_unitario, 2)
            total_general += valor_total

            filas_actualizadas.append(
                {
                    "AÑO": anio,
                    "CANTIDAD": cantidad,
                    "VALOR UNITARIO": valor_unitario,
                    "VALOR TOTAL": valor_total,
                }
            )

        requiere_refresco = filas_actualizadas != filas_originales

        bloque_editado["filas"] = filas_actualizadas
        bloque_editado["total_general"] = round(total_general, 2)

        st.markdown(
            f"""
            <div style="padding: 0.75rem 1rem; border: 1px solid #d9d9d9; border-radius: 0.5rem; background-color: #f8f9fa; margin-top: 0.5rem;">
                <b>Total general:</b> {bloque_editado["total_general"]:,.2f}
            </div>
            """,
            unsafe_allow_html=True,
        )

    return bloque_editado, eliminar, requiere_refresco


st.set_page_config(page_title="ANÁLISIS FINANCIERO", layout="wide")
st.title("ANÁLISIS FINANCIERO")
st.subheader("Ingresos y beneficios")

_cargar_data_inicial()

data_actual = _normalizar_data(st.session_state.get(STATE_KEY, {}))
bloques_actuales = data_actual["bloques"]

st.caption(
    "Registre los ingresos y beneficios del proyecto. Cada bloque conserva descripción, unidad, cantidades, valores unitarios, valores totales por año y total general."
)

with st.container(border=True):
    st.markdown("### Agregar nuevo registro")

    col_nuevo_tipo, col_nuevo_metodo, col_boton = st.columns([1, 1, 0.6])

    with col_nuevo_tipo:
        nuevo_tipo = st.selectbox(
            "Seleccione si el nuevo registro es un ingreso o un beneficio",
            options=["Ingreso", "Beneficio"],
            key="nuevo_tipo_ingreso_beneficio",
        )

    with col_nuevo_metodo:
        if nuevo_tipo == "Beneficio":
            nuevo_metodo = st.selectbox(
                "Método del beneficio",
                options=["Costos evitados o inducidos", "Precios hedónicos"],
                key="nuevo_metodo_beneficio",
            )
        else:
            st.text_input(
                "Método del beneficio",
                value="",
                disabled=True,
                key="nuevo_metodo_beneficio_disabled",
            )
            nuevo_metodo = ""

    with col_boton:
        st.write("")
        st.write("")
        agregar = st.button("Agregar registro", width="stretch")

    if agregar:
        bloques_actuales.append(_nuevo_bloque(nuevo_tipo, nuevo_metodo))
        nuevo_payload = {
            "bloques": bloques_actuales,
            "tasa_descuento": data_actual.get("tasa_descuento", 0.0),
            "rpc_bien": data_actual.get("rpc_bien", ""),
            "rpc_valor": data_actual.get("rpc_valor", 0.0),
        }
        _guardar_data(nuevo_payload)
        st.success("Registro agregado correctamente.")
        st.rerun()

if not bloques_actuales:
    st.info("Aún no hay registros creados.")
else:
    nuevos_bloques = []
    eliminar_ids = set()
    refrescar_tablas = False

    for indice, bloque in enumerate(bloques_actuales, start=1):
        bloque_editado, eliminar, requiere_refresco = _render_bloque(bloque, indice)
        nuevos_bloques.append(bloque_editado)

        if eliminar:
            eliminar_ids.add(_safe_str(bloque_editado["id"]))

        if requiere_refresco:
            refrescar_tablas = True

    if eliminar_ids:
        nuevos_bloques = [b for b in nuevos_bloques if _safe_str(b["id"]) not in eliminar_ids]
        _guardar_data(
            {
                "bloques": nuevos_bloques,
                "tasa_descuento": data_actual.get("tasa_descuento", 0.0),
                "rpc_bien": data_actual.get("rpc_bien", ""),
                "rpc_valor": data_actual.get("rpc_valor", 0.0),
            }
        )
        st.success("Registro eliminado correctamente.")
        st.rerun()

    payload_nuevo = _normalizar_data(
        {
            "bloques": nuevos_bloques,
            "tasa_descuento": data_actual.get("tasa_descuento", 0.0),
            "rpc_bien": data_actual.get("rpc_bien", ""),
            "rpc_valor": data_actual.get("rpc_valor", 0.0),
        }
    )

    if refrescar_tablas:
        st.session_state[STATE_KEY] = payload_nuevo
        for bloque in payload_nuevo["bloques"]:
            bloque_id = _safe_str(bloque["id"])
            st.session_state[f"_refrescar_tabla_{bloque_id}"] = not st.session_state.get(
                f"_refrescar_tabla_{bloque_id}", False
            )
        st.rerun()

    total_ingresos = round(
        sum(
            _safe_float(b["total_general"])
            for b in payload_nuevo["bloques"]
            if _safe_str(b.get("tipo")) == "Ingreso"
        ),
        2,
    )

    total_beneficios = round(
        sum(
            _safe_float(b["total_general"])
            for b in payload_nuevo["bloques"]
            if _safe_str(b.get("tipo")) == "Beneficio"
        ),
        2,
    )

    total_general_hoja = round(total_ingresos + total_beneficios, 2)

    st.markdown("## Resumen general")
    col_r1, col_r2, col_r3 = st.columns(3)

    with col_r1:
        st.metric("Total ingresos", f"{total_ingresos:,.2f}")

    with col_r2:
        st.metric("Total beneficios", f"{total_beneficios:,.2f}")

    with col_r3:
        st.metric("Total general hoja", f"{total_general_hoja:,.2f}")

    st.markdown("## FLUJO DE CAJA")

    flujo_caja_df = _tabla_flujo_caja(payload_nuevo["bloques"])

    st.dataframe(
        flujo_caja_df,
        width="stretch",
        hide_index=True,
    )

    st.markdown("## TASA DE DESCUENTO Y RAZÓN PRECIO CUENTA")

    rpc_catalogo = _catalogo_rpc()
    opciones_bien = rpc_catalogo["Bien"].tolist()

    valor_guardado_bien = _safe_str(payload_nuevo.get("rpc_bien"))
    if valor_guardado_bien in opciones_bien:
        index_bien = opciones_bien.index(valor_guardado_bien)
    else:
        index_bien = 0 if opciones_bien else None

    col_td_1, col_td_2 = st.columns([1.2, 1])

    with col_td_1:
        tasa_descuento = st.number_input(
            "TASA DE DESCUENTO (%)",
            min_value=0.0,
            step=0.01,
            value=_safe_float(payload_nuevo.get("tasa_descuento", 0.0), 0.0),
            format="%.2f",
            key="tasa_descuento_analisis_financiero",
        )

    with col_td_2:
        if opciones_bien:
            rpc_bien = st.selectbox(
                "BIEN",
                options=opciones_bien,
                index=index_bien,
                key="rpc_bien_analisis_financiero",
            )
            rpc_valor = _safe_float(
                rpc_catalogo.loc[rpc_catalogo["Bien"] == rpc_bien, "RPC"].iloc[0],
                0.0,
            )
        else:
            rpc_bien = ""
            rpc_valor = 0.0
            st.selectbox(
                "BIEN",
                options=[""],
                index=0,
                disabled=True,
                key="rpc_bien_analisis_financiero_vacio",
            )

    st.text_input(
        "RPC",
        value=f"{rpc_valor:.4f}",
        disabled=True,
    )

    payload_nuevo["tasa_descuento"] = tasa_descuento
    payload_nuevo["rpc_bien"] = rpc_bien
    payload_nuevo["rpc_valor"] = rpc_valor
    st.session_state[STATE_KEY] = _normalizar_data(payload_nuevo)

    st.markdown("## TOTAL NETO")

    total_neto_df = _tabla_total_neto(flujo_caja_df, rpc_valor)

    st.dataframe(
        total_neto_df,
        width="stretch",
        hide_index=True,
    )

    flujos_total_neto = _serie_total_neto(total_neto_df)
    vpn_valor = _calcular_vpn(flujos_total_neto, tasa_descuento)
    tir_valor = _calcular_tir(flujos_total_neto)
    bc_valor = _calcular_beneficio_costo(flujos_total_neto)

    st.markdown("## INDICADORES")

    vpn_fondo = "linear-gradient(135deg, #123b6d 0%, #0b2747 100%)" if vpn_valor >= 0 else "linear-gradient(135deg, #6b1633 0%, #3f0b1d 100%)"
    vpn_borde = "#0b2747" if vpn_valor >= 0 else "#3f0b1d"

    tir_ok = tir_valor is not None and tir_valor >= tasa_descuento
    tir_fondo = "linear-gradient(135deg, #123b6d 0%, #0b2747 100%)" if tir_ok else "linear-gradient(135deg, #6b1633 0%, #3f0b1d 100%)"
    tir_borde = "#0b2747" if tir_ok else "#3f0b1d"

    bc_ok = bc_valor is not None and bc_valor >= 1
    bc_fondo = "linear-gradient(135deg, #123b6d 0%, #0b2747 100%)" if bc_ok else "linear-gradient(135deg, #6b1633 0%, #3f0b1d 100%)"
    bc_borde = "#0b2747" if bc_ok else "#3f0b1d"

    col_ind_1, col_ind_2, col_ind_3 = st.columns(3)

    with col_ind_1:
        st.markdown(
            f"""
            <div style="padding: 1rem 1.15rem; border-radius: 18px; background: {vpn_fondo}; border: 1px solid {vpn_borde}; box-shadow: 0 2px 10px rgba(18,52,77,0.18);">
                <div style="font-size: 0.82rem; font-weight: 700; color: #dce9f7; letter-spacing: 0.04em; margin-bottom: 0.35rem;">VALOR PRESENTE NETO</div>
                <div style="font-size: 1.7rem; font-weight: 800; color: #ffffff; margin-bottom: 0.35rem;">{vpn_valor:,.2f}</div>
                <div style="font-size: 0.82rem; color: #eef4ff;">Calculado con tasa de descuento del {tasa_descuento:.2f}%</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_ind_2:
        tir_texto = f"{tir_valor:,.2f}%" if tir_valor is not None else "No calculable"
        st.markdown(
            f"""
            <div style="padding: 1rem 1.15rem; border-radius: 18px; background: {tir_fondo}; border: 1px solid {tir_borde}; box-shadow: 0 2px 10px rgba(18,52,77,0.18);">
                <div style="font-size: 0.82rem; font-weight: 700; color: #dce9f7; letter-spacing: 0.04em; margin-bottom: 0.35rem;">TASA INTERNA DE RETORNO</div>
                <div style="font-size: 1.7rem; font-weight: 800; color: #ffffff; margin-bottom: 0.35rem;">{tir_texto}</div>
                <div style="font-size: 0.82rem; color: #eef4ff;">Calculada sobre el flujo neto de los años 0 a 10</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_ind_3:
        bc_texto = f"{bc_valor:,.4f}" if bc_valor is not None else "No calculable"
        st.markdown(
            f"""
            <div style="padding: 1rem 1.15rem; border-radius: 18px; background: {bc_fondo}; border: 1px solid {bc_borde}; box-shadow: 0 2px 10px rgba(18,52,77,0.18);">
                <div style="font-size: 0.82rem; font-weight: 700; color: #dce9f7; letter-spacing: 0.04em; margin-bottom: 0.35rem;">RAZÓN COSTO-BENEFICIO</div>
                <div style="font-size: 1.7rem; font-weight: 800; color: #ffffff; margin-bottom: 0.35rem;">{bc_texto}</div>
                <div style="font-size: 0.82rem; color: #eef4ff;">Suma de años 1 a 10 / valor absoluto del año 0</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if st.button("Guardar información", width="stretch"):
        _guardar_data(_normalizar_data(payload_nuevo))
        st.success("Información guardada correctamente.")
