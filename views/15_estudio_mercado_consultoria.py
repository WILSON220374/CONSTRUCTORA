import uuid
import pandas as pd
import streamlit as st
from supabase_state import cargar_estado, guardar_estado

st.title("ESTUDIO DE MERCADO CONSULTORIA")

cronograma_datos = st.session_state.get("cronograma_datos", {}) or {}
tipo_presupuesto_proyecto = str(cronograma_datos.get("tipo_presupuesto_proyecto", "Obra") or "Obra").strip()

if tipo_presupuesto_proyecto != "Consultoría":
    st.warning("Este proyecto está clasificado como Obra. La hoja Estudio de Mercado Consultoría aplica solo para proyectos de Consultoría.")
    st.stop()

alcance = st.session_state.get("alcance_datos", {}) or {}
nombre_proyecto = alcance.get("nombre_proyecto", "") or "SIN NOMBRE DEFINIDO"
st.markdown(f"## {nombre_proyecto}")
# -----------------------------
# Carga de estados
# -----------------------------
try:
    apus_consultoria_datos = cargar_estado("apus_consultoria") or {}
except Exception:
    apus_consultoria_datos = {}

st.session_state["apus_consultoria_datos"] = apus_consultoria_datos

try:
    estudio_mercado_consultoria_datos = cargar_estado("estudio_mercado_consultoria") or {}
except Exception:
    estudio_mercado_consultoria_datos = {}

key_items = "em_items_data"
key_cot = "em_cotizaciones_data"

if "em_num_cotizaciones" not in st.session_state:
    st.session_state["em_num_cotizaciones"] = int(
        estudio_mercado_consultoria_datos.get("num_cotizaciones", 3) or 3
    )

ITEMS_COLUMNS = [
    "ID",
    "TIPO",
    "SUBTIPO",
    "NOMBRE",
    "CARACTERISTICAS",
    "UNIDAD",
    "IVA_PCT",
    "ACTIVO",
    "APU_CONSULTORIA_ORIGEN_ID",
    "APU_CONSULTORIA_ORIGEN_NOMBRE",
]

COT_COLUMNS = [
    "ID",
    "ITEM_ID",
    "PROVEEDOR",
    "VALOR_SIN_IVA",
]



def _normalizar_items(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in ITEMS_COLUMNS:
        if col not in df.columns:
            if col == "IVA_PCT":
                df[col] = 19.0
            elif col == "ACTIVO":
                df[col] = True
            else:
                df[col] = ""

    df = df[ITEMS_COLUMNS].copy()

    for col in [
        "ID",
        "TIPO",
        "SUBTIPO",
        "NOMBRE",
        "CARACTERISTICAS",
        "UNIDAD",
        "APU_CONSULTORIA_ORIGEN_ID",
        "APU_CONSULTORIA_ORIGEN_NOMBRE",
    ]:
        df[col] = df[col].fillna("").astype(str)

    df["IVA_PCT"] = pd.to_numeric(df["IVA_PCT"], errors="coerce").fillna(0.0)
    df["ACTIVO"] = df["ACTIVO"].fillna(False).astype(bool)

    for i in df.index:
        if not str(df.at[i, "ID"]).strip():
            df.at[i, "ID"] = f"MANUAL|{uuid.uuid4().hex[:12]}"
        if str(df.at[i, "TIPO"]).strip().upper() == "PERSONAL":
            df.at[i, "IVA_PCT"] = 0.0

    return df


def _normalizar_cotizaciones(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in COT_COLUMNS:
        if col not in df.columns:
            df[col] = "" if col != "VALOR_SIN_IVA" else 0.0

    df = df[COT_COLUMNS].copy()

    for col in ["ID", "ITEM_ID", "PROVEEDOR"]:
        df[col] = df[col].fillna("").astype(str)

    df["VALOR_SIN_IVA"] = pd.to_numeric(df["VALOR_SIN_IVA"], errors="coerce").fillna(0.0)

    for i in df.index:
        if not str(df.at[i, "ID"]).strip():
            df.at[i, "ID"] = f"COT|{uuid.uuid4().hex[:12]}"

    return df


def _ids_apu_vigentes() -> set[str]:
    grupos_vigentes = st.session_state.get("pc_grupos_origen", []) or []
    ids = {
        str(grupo.get("group_id", "") or "").strip()
        for grupo in grupos_vigentes
        if str(grupo.get("group_id", "") or "").strip()
    }

    if ids:
        return ids

    return {
        str(apu_id).strip()
        for apu_id in (apus_consultoria_datos.get("registros_por_oci", {}) or {}).keys()
        if str(apu_id).strip()
    }

def _extraer_items_apu_consultoria(datos: dict) -> list[dict]:
    items = []

    registros_por_oci = datos.get("registros_por_oci", {}) or {}
    ids_costos_indirectos_vigentes = _ids_apu_vigentes()

    for oci_id, registro in registros_por_oci.items():
        oci_id = str(oci_id or "").strip()
        if not oci_id or oci_id not in ids_costos_indirectos_vigentes:
            continue
            
        personales = [
            ("PERSONAL", registro.get("personal_profesional", []), "PERFIL / ACTIVIDAD"),
            ("PERSONAL", registro.get("personal_tecnico", []), "PERFIL / ACTIVIDAD"),
            ("PERSONAL", registro.get("otro_personal", []), "PERFIL / ACTIVIDAD"),
        ]

        for tipo, filas, campo_nombre in personales:
            for fila in filas or []:
                fuente = str(fila.get("FUENTE", "")).strip()
                nombre = str(fila.get(campo_nombre, "")).strip()
                if fuente != "Cotización" or not nombre:
                    continue
                items.append(
                    {
                        "ID": str(fila.get("ID", "") or "").strip(),
                        "TIPO": tipo,
                        "NOMBRE": nombre,
                        "APU_CONSULTORIA_ORIGEN_ID": oci_id,
                    }
                )

        bloques_bs = [
            ("BIENES", registro.get("bienes", []), "BIEN / ACTIVIDAD"),
            ("SERVICIOS", registro.get("servicios", []), "BIEN / ACTIVIDAD"),
        ]

        for tipo, filas, campo_nombre in bloques_bs:
            for fila in filas or []:
                fuente = str(fila.get("FUENTE", "")).strip()
                nombre = str(fila.get(campo_nombre, "")).strip()
                if fuente != "Cotización" or not nombre:
                    continue
                items.append(
                    {
                        "ID": str(fila.get("ID", "") or "").strip(),
                        "TIPO": tipo,
                        "NOMBRE": nombre,
                        "APU_CONSULTORIA_ORIGEN_ID": oci_id,
                    }
                )

    items_unicos = []
    ids_vistos = set()

    for item in items:
        item_id = str(item.get("ID", "") or "").strip()
        if not item_id or item_id in ids_vistos:
            continue
        ids_vistos.add(item_id)
        items_unicos.append(item)

    return items_unicos


def _fusionar_items(items_base: list[dict], items_actuales_hoja10: list[dict]) -> list[dict]:
    guardados_df = _normalizar_items(pd.DataFrame(items_base or []))
    actuales_df = _normalizar_items(pd.DataFrame(items_actuales_hoja10 or []))

    if actuales_df.empty:
        return []

    guardados_map = {
        str(row["ID"]).strip(): row.to_dict()
        for _, row in guardados_df.iterrows()
        if str(row["ID"]).strip()
    }

    filas = []
    for _, row in actuales_df.iterrows():
        item_id = str(row["ID"]).strip()
        base = row.to_dict()

        if item_id in guardados_map:
            guardado = guardados_map[item_id]
            base["CARACTERISTICAS"] = str(guardado.get("CARACTERISTICAS", "") or "").strip()
            if str(guardado.get("UNIDAD", "")).strip():
                base["UNIDAD"] = str(guardado.get("UNIDAD", "")).strip()
            if str(base["TIPO"]).strip().upper() != "PERSONAL":
                base["IVA_PCT"] = float(
                    pd.to_numeric(guardado.get("IVA_PCT", base["IVA_PCT"]), errors="coerce") or base["IVA_PCT"]
                )
            else:
                base["IVA_PCT"] = 0.0

        base["ACTIVO"] = True
        filas.append(base)

    resultado = pd.DataFrame(filas)
    resultado = _normalizar_items(resultado)
    resultado = resultado.sort_values(
        by=["TIPO", "NOMBRE", "ID"],
        ascending=[True, True, True],
        kind="stable",
    ).reset_index(drop=True)

    return resultado.to_dict(orient="records")


def _asegurar_cotizaciones_base(items_df: pd.DataFrame, cot_df: pd.DataFrame) -> pd.DataFrame:
    items_df = _normalizar_items(items_df)
    cot_df = _normalizar_cotizaciones(cot_df)

    ids_validos = set(items_df["ID"].astype(str).str.strip().tolist())
    cot_df = cot_df[cot_df["ITEM_ID"].astype(str).str.strip().isin(ids_validos)].reset_index(drop=True)

    cantidad_objetivo = max(1, int(st.session_state.get("em_num_cotizaciones", 3) or 3))

    nuevas = []
    recortadas = []

    for _, row in items_df.iterrows():
        item_id = str(row["ID"]).strip()
        if not item_id:
            continue

        actuales_item = cot_df[cot_df["ITEM_ID"].astype(str).eq(item_id)].copy().reset_index(drop=True)

        if len(actuales_item) > cantidad_objetivo:
            actuales_item = actuales_item.iloc[:cantidad_objetivo].copy()

        recortadas.append(actuales_item)

        faltantes = max(0, cantidad_objetivo - len(actuales_item))
        for _ in range(faltantes):
            nuevas.append(
                {
                    "ID": f"COT|{uuid.uuid4().hex[:12]}",
                    "ITEM_ID": item_id,
                    "PROVEEDOR": "",
                    "VALOR_SIN_IVA": 0.0,
                }
            )

    cot_df = pd.concat(
        recortadas + [pd.DataFrame(nuevas)],
        ignore_index=True,
    ) if (recortadas or nuevas) else pd.DataFrame(columns=["ID", "ITEM_ID", "PROVEEDOR", "VALOR_SIN_IVA"])

    return _normalizar_cotizaciones(cot_df)


def _estado_canonico(items_origen: list[dict], items_editables: list[dict], cotizaciones_editables: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    items_df = _normalizar_items(pd.DataFrame(_fusionar_items(items_editables, items_origen)))
    cot_df = _normalizar_cotizaciones(pd.DataFrame(cotizaciones_editables or []))
    cot_df = _asegurar_cotizaciones_base(items_df, cot_df)
    return items_df, cot_df


def _sincronizar_estado_con_hoja_10(guardar: bool = False):
    global apus_consultoria_datos, estudio_mercado_consultoria_datos

    ids_vigentes = _ids_apu_vigentes()
    registros = apus_consultoria_datos.get("registros_por_oci", {}) or {}
    registros_filtrados = {
        str(oci_id): registro
        for oci_id, registro in registros.items()
        if str(oci_id).strip() in ids_vigentes
    }
    if registros_filtrados != (apus_consultoria_datos.get("registros_por_oci", {}) or {}):
        apus_consultoria_datos["registros_por_oci"] = registros_filtrados
        st.session_state["apus_consultoria_datos"] = apus_consultoria_datos
        if guardar:
            guardar_estado("apus_consultoria", apus_consultoria_datos)

    items_origen = _extraer_items_apu_consultoria(apus_consultoria_datos)

    items_base = st.session_state.get(key_items, estudio_mercado_consultoria_datos.get("items", []))
    cot_base = st.session_state.get(key_cot, estudio_mercado_consultoria_datos.get("cotizaciones", []))

    items_df, cot_df = _estado_canonico(items_origen, items_base, cot_base)

    st.session_state[key_items] = items_df.to_dict(orient="records")
    st.session_state[key_cot] = cot_df.to_dict(orient="records")

    estudio_limpio = {
        "items": items_df.to_dict(orient="records"),
        "cotizaciones": cot_df.to_dict(orient="records"),
    }

    if guardar or estudio_limpio != {
        "items": estudio_mercado_consultoria_datos.get("items", []),
        "cotizaciones": estudio_mercado_consultoria_datos.get("cotizaciones", []),
    }:
        estudio_mercado_consultoria_datos = estudio_limpio
        if guardar:
            guardar_estado("estudio_mercado_consultoria", estudio_mercado_consultoria_datos)

    for tipo_sync in ["PERSONAL", "BIENES", "SERVICIOS"]:
        pending_items_tipo = items_df[items_df["TIPO"].astype(str).str.upper() == tipo_sync].copy()
        pending_cot_tipo = cot_df[cot_df["ITEM_ID"].astype(str).isin(pending_items_tipo["ID"].astype(str))].copy()

        st.session_state[f"em_pending_items_{tipo_sync}"] = pending_items_tipo.to_dict(orient="records")
        st.session_state[f"em_pending_cot_{tipo_sync}"] = pending_cot_tipo.to_dict(orient="records")

    return items_df, cot_df


def _guardar_estudio_mercado():
    try:
        items_actuales_hoja10 = _extraer_items_apu_consultoria(apus_consultoria_datos)

        items_base = st.session_state.get(key_items, [])
        cot_base = st.session_state.get(key_cot, [])

        for tipo in ["PERSONAL", "BIENES", "SERVICIOS"]:
            pending_items_key = f"em_pending_items_{tipo}"
            pending_cot_key = f"em_pending_cot_{tipo}"

            pending_items_df = _normalizar_items(pd.DataFrame(st.session_state.get(pending_items_key, [])))
            pending_cot_df = _normalizar_cotizaciones(pd.DataFrame(st.session_state.get(pending_cot_key, [])))

            if not pending_items_df.empty:
                items_otros = _normalizar_items(pd.DataFrame(items_base))
                items_otros = items_otros[items_otros["TIPO"].astype(str).str.upper() != tipo].copy()
                items_base = pd.concat([items_otros, pending_items_df], ignore_index=True).to_dict(orient="records")

            if not pending_cot_df.empty:
                cot_otros = _normalizar_cotizaciones(pd.DataFrame(cot_base))
                ids_tipo = set(pending_items_df["ID"].astype(str).tolist())
                cot_otros = cot_otros[~cot_otros["ITEM_ID"].astype(str).isin(ids_tipo)].copy()
                cot_base = pd.concat([cot_otros, pending_cot_df], ignore_index=True).to_dict(orient="records")

        items_df, cot_df = _estado_canonico(items_actuales_hoja10, items_base, cot_base)

        st.session_state[key_items] = items_df.to_dict(orient="records")
        st.session_state[key_cot] = cot_df.to_dict(orient="records")

        guardar_estado(
            "estudio_mercado_consultoria",
            {
                "items": items_df.to_dict(orient="records"),
                "cotizaciones": cot_df.to_dict(orient="records"),
                "num_cotizaciones": int(st.session_state.get("em_num_cotizaciones", 3) or 3),
            },
        )
        return True
    except RuntimeError:
        st.error("La sesión expiró. Inicia sesión de nuevo para guardar el estudio de mercado.")
        return False


def _resumen_calculos(items_df: pd.DataFrame, cot_df: pd.DataFrame) -> pd.DataFrame:
    items_df = _normalizar_items(items_df)
    cot_df = _normalizar_cotizaciones(cot_df)

    if cot_df.empty:
        proms = pd.DataFrame(columns=["ITEM_ID", "PROMEDIO", "CANT_COT"])
    else:
        cot_validas = cot_df.copy()
        cot_validas["VALOR_SIN_IVA"] = pd.to_numeric(cot_validas["VALOR_SIN_IVA"], errors="coerce")
        cot_validas = cot_validas[cot_validas["ITEM_ID"].astype(str).str.strip() != ""].copy()
        cot_validas = cot_validas[cot_validas["VALOR_SIN_IVA"].notna()].copy()
        cot_validas = cot_validas[cot_validas["VALOR_SIN_IVA"] > 0].copy()

        proms = (
            cot_validas.groupby("ITEM_ID", dropna=False)["VALOR_SIN_IVA"]
            .agg(["mean", "count"])
            .reset_index()
            .rename(columns={"mean": "PROMEDIO", "count": "CANT_COT"})
        )

    resumen = items_df.merge(proms, how="left", left_on="ID", right_on="ITEM_ID")
    resumen["PROMEDIO"] = pd.to_numeric(resumen["PROMEDIO"], errors="coerce").fillna(0.0)
    resumen["CANT_COT"] = pd.to_numeric(resumen["CANT_COT"], errors="coerce").fillna(0).astype(int)
    resumen["TOTAL"] = resumen["PROMEDIO"]

    mask_no_personal = resumen["TIPO"].astype(str).str.upper().ne("PERSONAL")
    resumen.loc[mask_no_personal, "TOTAL"] = resumen.loc[mask_no_personal, "PROMEDIO"] * (
        1 + (pd.to_numeric(resumen.loc[mask_no_personal, "IVA_PCT"], errors="coerce").fillna(0.0) / 100.0)
    )

    return resumen


def _aplicar_a_hoja_10():
    try:
        items_df = _normalizar_items(pd.DataFrame(st.session_state.get(key_items, [])))
        cot_df = _normalizar_cotizaciones(pd.DataFrame(st.session_state.get(key_cot, [])))
        resumen = _resumen_calculos(items_df, cot_df)

        mapa_promedio = {}
        for _, row in resumen.iterrows():
            item_id = str(row["ID"]).strip()
            if item_id:
                mapa_promedio[item_id] = {
                    "promedio": float(pd.to_numeric(row["PROMEDIO"], errors="coerce") or 0.0),
                    "unidad": str(row["UNIDAD"]).strip(),
                }

        try:
            costos = cargar_estado("apus_consultoria") or {}
        except Exception:
            costos = {}

        ids_vigentes = _ids_apu_vigentes()
        registros = costos.get("registros_por_oci", {}) or {}
        registros_filtrados = {
            str(oci_id): registro
            for oci_id, registro in registros.items()
            if str(oci_id).strip() in ids_vigentes
        }

        def _actualizar_personal(lista_filas, oci_id, subtipo):
            nuevas = []
            for fila in lista_filas or []:
                fila2 = dict(fila)
                if str(fila2.get("FUENTE", "")).strip() == "Cotización":
                    nombre = str(fila2.get("PERFIL / ACTIVIDAD", "")).strip()
                    item_id = str(fila2.get("ID", "") or "").strip()
                    ref = mapa_promedio.get(item_id)
                    if ref:
                        fila2["UNIDAD"] = ref["unidad"]
                        fila2["VR UNITARIO"] = ref["promedio"]
                        fila2["VR TOTAL"] = (
                            float(pd.to_numeric(fila2.get("CANT", 0.0), errors="coerce") or 0.0)
                            * float(pd.to_numeric(fila2.get("REND", 0.0), errors="coerce") or 0.0)
                            * float(ref["promedio"])
                        )
                nuevas.append(fila2)
            return nuevas

        def _actualizar_bs(lista_filas, oci_id, tipo, subtipo):
            nuevas = []
            for fila in lista_filas or []:
                fila2 = dict(fila)
                if str(fila2.get("FUENTE", "")).strip() == "Cotización":
                    nombre = str(fila2.get("BIEN / ACTIVIDAD", "")).strip()
                    item_id = str(fila2.get("ID", "") or "").strip()
                    ref = mapa_promedio.get(item_id)
                    if ref:
                        fila2["UNIDAD"] = ref["unidad"]
                        fila2["VR UNITARIO SIN IVA"] = ref["promedio"]
                        fila2["VR TOTAL"] = (
                            float(pd.to_numeric(fila2.get("CANT", 0.0), errors="coerce") or 0.0)
                            * float(ref["promedio"])
                        )
                nuevas.append(fila2)
            return nuevas

        for oci_id, registro in registros_filtrados.items():
            oci_id = str(oci_id).strip()
            registro["personal_profesional"] = _actualizar_personal(
                registro.get("personal_profesional", []),
                oci_id,
                "1 Personal profesional y especializado",
            )
            registro["personal_tecnico"] = _actualizar_personal(
                registro.get("personal_tecnico", []),
                oci_id,
                "2 Personal técnico",
            )
            registro["otro_personal"] = _actualizar_personal(
                registro.get("otro_personal", []),
                oci_id,
                "3 Otro personal",
            )
            registro["bienes"] = _actualizar_bs(
                registro.get("bienes", []),
                oci_id,
                "BIENES",
                "4. BIENES",
            )
            registro["servicios"] = _actualizar_bs(
                registro.get("servicios", []),
                oci_id,
                "SERVICIOS",
                "5. SERVICIOS",
            )

        costos["registros_por_oci"] = registros_filtrados

        guardar_estado("apus_consultoria", costos)
        st.session_state["apus_consultoria_datos"] = costos
        st.success("Promedios aplicados a APU consultoría correctamente.")
        return True

    except Exception:
        st.error("No fue posible aplicar los promedios a APU consultoría.")
        return False


# -----------------------------
# Inicialización y limpieza integral
# -----------------------------
items_df, cot_df = _sincronizar_estado_con_hoja_10(guardar=False)

# -----------------------------
# Helpers de render y guardado
# -----------------------------
def _columnas_cotizacion_desde_estado(cot_df_base: pd.DataFrame, items_df_base: pd.DataFrame) -> int:
    cantidad = int(st.session_state.get("em_num_cotizaciones", 3) or 3)
    cantidad = max(1, cantidad)
    st.session_state["em_num_cotizaciones"] = cantidad
    return cantidad


def _construir_render_desde_estado(items_df_base: pd.DataFrame, cot_df_base: pd.DataFrame, num_cotizaciones: int) -> pd.DataFrame:
    resumen_df_base = _resumen_calculos(items_df_base, cot_df_base)
    filas_render = []

    for _, row in resumen_df_base.iterrows():
        item_id = str(row["ID"]).strip()
        cot_item = (
            cot_df_base[cot_df_base["ITEM_ID"].astype(str).eq(item_id)]
            .reset_index(drop=True)
            .copy()
        )

        fila = {
            "ID": item_id,
            "TIPO": str(row["TIPO"]),
            "SUBTIPO": str(row["SUBTIPO"]),
            "NOMBRE": str(row["NOMBRE"]),
            "CARACTERISTICAS": str(row["CARACTERISTICAS"]),
            "UNIDAD": str(row["UNIDAD"]),
            "IVA_PCT": float(pd.to_numeric(row["IVA_PCT"], errors="coerce") or 0.0),
            "APU_CONSULTORIA_ORIGEN_ID": str(row.get("APU_CONSULTORIA_ORIGEN_ID", "") or ""),
            "APU_CONSULTORIA_ORIGEN_NOMBRE": str(row.get("APU_CONSULTORIA_ORIGEN_NOMBRE", "") or ""),
            "CANT_COT": int(pd.to_numeric(row.get("CANT_COT", 0), errors="coerce") or 0),
            "PROMEDIO": float(pd.to_numeric(row.get("PROMEDIO", 0.0), errors="coerce") or 0.0),
            "TOTAL": float(pd.to_numeric(row.get("TOTAL", 0.0), errors="coerce") or 0.0),
        }

        for idx in range(num_cotizaciones):
            if idx < len(cot_item):
                fila[f"PROVEEDOR_{idx + 1}"] = str(cot_item.iloc[idx].get("PROVEEDOR", "") or "")
                fila[f"VALOR_{idx + 1}"] = float(
                    pd.to_numeric(cot_item.iloc[idx].get("VALOR_SIN_IVA", 0.0), errors="coerce") or 0.0
                )
                fila[f"COT_ID_{idx + 1}"] = str(cot_item.iloc[idx].get("ID", "") or f"COT|{uuid.uuid4().hex[:12]}")
            else:
                fila[f"PROVEEDOR_{idx + 1}"] = ""
                fila[f"VALOR_{idx + 1}"] = 0.0
                fila[f"COT_ID_{idx + 1}"] = f"COT|{uuid.uuid4().hex[:12]}"

        filas_render.append(fila)

    return pd.DataFrame(filas_render)


def _reconstruir_estado_desde_editores(num_cotizaciones: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    items_acumulados = []
    cot_acumuladas = []

    for tipo_editor in ["PERSONAL", "BIENES", "SERVICIOS"]:
        editor_cache_key = f"em_editor_df_{tipo_editor}"
        if editor_cache_key not in st.session_state:
            continue

        editor_df = pd.DataFrame(st.session_state[editor_cache_key]).copy()
        if editor_df.empty:
            continue

        col_nombre = "PERFIL / ACTIVIDAD" if tipo_editor == "PERSONAL" else "BIEN / ACTIVIDAD"
        if col_nombre in editor_df.columns:
            editor_df = editor_df.rename(columns={col_nombre: "NOMBRE"})

        for _, row in editor_df.iterrows():
            items_acumulados.append(
                {
                    "ID": str(row.get("ID", "") or ""),
                    "TIPO": str(row.get("TIPO", "") or ""),
                    "SUBTIPO": str(row.get("SUBTIPO", "") or ""),
                    "NOMBRE": str(row.get("NOMBRE", "") or ""),
                    "CARACTERISTICAS": str(row.get("CARACTERISTICAS", "") or ""),
                    "UNIDAD": str(row.get("UNIDAD", "") or ""),
                    "IVA_PCT": 0.0 if tipo_editor == "PERSONAL" else float(
                        pd.to_numeric(row.get("IVA_PCT", 19.0), errors="coerce") or 19.0
                    ),
                    "ACTIVO": True,
                    "APU_CONSULTORIA_ORIGEN_ID": str(row.get("APU_CONSULTORIA_ORIGEN_ID", "") or ""),
                    "APU_CONSULTORIA_ORIGEN_NOMBRE": str(row.get("APU_CONSULTORIA_ORIGEN_NOMBRE", "") or ""),
                }
            )

            for idx in range(num_cotizaciones):
                cot_acumuladas.append(
                    {
                        "ID": str(row.get(f"COT_ID_{idx + 1}", "") or f"COT|{uuid.uuid4().hex[:12]}"),
                        "ITEM_ID": str(row.get("ID", "") or ""),
                        "PROVEEDOR": str(row.get(f"PROVEEDOR_{idx + 1}", "") or ""),
                        "VALOR_SIN_IVA": float(
                            pd.to_numeric(row.get(f"VALOR_{idx + 1}", 0.0), errors="coerce") or 0.0
                        ),
                    }
                )

    items_df_local = _normalizar_items(pd.DataFrame(items_acumulados))
    cot_df_local = _normalizar_cotizaciones(pd.DataFrame(cot_acumuladas))

    ids_validos = set(items_df_local["ID"].astype(str).str.strip().tolist())
    cot_df_local = cot_df_local[
        cot_df_local["ITEM_ID"].astype(str).str.strip().isin(ids_validos)
    ].copy()

    cot_df_local = cot_df_local[
        ~(
            cot_df_local["PROVEEDOR"].astype(str).str.strip().eq("")
            & pd.to_numeric(cot_df_local["VALOR_SIN_IVA"], errors="coerce").fillna(0.0).eq(0.0)
        )
    ].copy()

    cot_df_local = _normalizar_cotizaciones(cot_df_local)

    return items_df_local, cot_df_local

def _guardar_desde_editores(num_cotizaciones: int) -> bool:
    global apus_consultoria_datos, estudio_mercado_consultoria_datos

    try:
        try:
            apus_consultoria_datos = cargar_estado("apus_consultoria") or {}
        except Exception:
            apus_consultoria_datos = {}

        items_actuales_hoja10 = _extraer_items_apu_consultoria(apus_consultoria_datos)
        items_editados_df, cot_editadas_df = _reconstruir_estado_desde_editores(num_cotizaciones)

        items_df_final, cot_df_final = _estado_canonico(
            items_actuales_hoja10,
            items_editados_df.to_dict(orient="records"),
            cot_editadas_df.to_dict(orient="records"),
        )

        st.session_state[key_items] = items_df_final.to_dict(orient="records")
        st.session_state[key_cot] = cot_df_final.to_dict(orient="records")

        for tipo_sync in ["PERSONAL", "BIENES", "SERVICIOS"]:
            pending_items_tipo = items_df_final[items_df_final["TIPO"].astype(str).str.upper() == tipo_sync].copy()
            pending_cot_tipo = cot_df_final[cot_df_final["ITEM_ID"].astype(str).isin(pending_items_tipo["ID"].astype(str))].copy()

            st.session_state[f"em_pending_items_{tipo_sync}"] = pending_items_tipo.to_dict(orient="records")
            st.session_state[f"em_pending_cot_{tipo_sync}"] = pending_cot_tipo.to_dict(orient="records")

        estudio_mercado_consultoria_datos = {
            "items": items_df_final.to_dict(orient="records"),
            "cotizaciones": cot_df_final.to_dict(orient="records"),
            "num_cotizaciones": int(st.session_state.get("em_num_cotizaciones", 3) or 3),
        }
        guardar_estado("estudio_mercado_consultoria", estudio_mercado_consultoria_datos)
        return True

    except RuntimeError:
        st.error("La sesión expiró. Inicia sesión de nuevo para guardar el estudio de mercado.")
        return False


# -----------------------------
# Render por bloque
# -----------------------------
orden_tipos = [
    ("PERSONAL", "SALARIOS"),
    ("BIENES", "BIENES"),
    ("SERVICIOS", "SERVICIOS"),
]

items_df = _normalizar_items(pd.DataFrame(st.session_state.get(key_items, [])))
cot_df = _normalizar_cotizaciones(pd.DataFrame(st.session_state.get(key_cot, [])))

num_cotizaciones = _columnas_cotizacion_desde_estado(cot_df, items_df)

ctrl_1, ctrl_2, ctrl_3 = st.columns([1, 1, 2])
with ctrl_1:
    if st.button("Agregar cotización", width="stretch"):
        st.session_state["em_num_cotizaciones"] = int(st.session_state.get("em_num_cotizaciones", 3) or 3) + 1
        st.rerun()

with ctrl_2:
    if st.button("Quitar cotización", width="stretch"):
        actual = int(st.session_state.get("em_num_cotizaciones", 3) or 3)
        st.session_state["em_num_cotizaciones"] = max(1, actual - 1)
        st.rerun()

with ctrl_3:
    st.caption(f"Cotizaciones visibles por item: {int(st.session_state.get('em_num_cotizaciones', 3) or 3)}")

st.divider()

for tipo, titulo in orden_tipos:
    st.markdown(f"## {titulo}")

    items_sec = items_df[items_df["TIPO"].astype(str).str.upper() == tipo].copy()
    cot_sec = cot_df[cot_df["ITEM_ID"].astype(str).isin(items_sec["ID"].astype(str))].copy()

    if items_sec.empty:
        st.info(f"No hay registros de {titulo.lower()} con fuente Cotización en APU consultoría.")
        st.divider()
        continue

    render_df = _construir_render_desde_estado(items_sec, cot_sec, int(st.session_state.get("em_num_cotizaciones", 3) or 3))

    col_nombre = "PERFIL / ACTIVIDAD" if tipo == "PERSONAL" else "BIEN / ACTIVIDAD"
    render_df = render_df.rename(columns={"NOMBRE": col_nombre})

    column_order = [col_nombre, "CARACTERISTICAS", "UNIDAD"]
    column_config = {
        col_nombre: st.column_config.TextColumn(col_nombre, disabled=True),
        "CARACTERISTICAS": st.column_config.TextColumn("CARACTERISTICAS"),
        "UNIDAD": st.column_config.TextColumn("UNIDAD"),
    }

    for idx in range(int(st.session_state.get("em_num_cotizaciones", 3) or 3)):
        column_order.extend([f"PROVEEDOR_{idx + 1}", f"VALOR_{idx + 1}"])
        column_config[f"PROVEEDOR_{idx + 1}"] = st.column_config.TextColumn(f"PROVEEDOR {idx + 1}")
        column_config[f"VALOR_{idx + 1}"] = st.column_config.NumberColumn(
            f"VALOR {idx + 1}",
            min_value=0.0,
            step=0.01,
            format="$ %.2f",
        )

    column_order.append("PROMEDIO")
    column_config["PROMEDIO"] = st.column_config.NumberColumn("PROMEDIO", disabled=True, format="$ %.2f")

    if tipo in ["BIENES", "SERVICIOS"]:
        column_order.extend(["IVA_PCT", "TOTAL"])
        column_config["IVA_PCT"] = st.column_config.NumberColumn("IVA %", min_value=0.0, step=0.01, format="%.2f")
        column_config["TOTAL"] = st.column_config.NumberColumn("TOTAL", disabled=True, format="$ %.2f")

    edited_df = st.data_editor(
        render_df,
        hide_index=True,
        width="stretch",
        num_rows="fixed",
        key=f"em_items_{tipo}",
        column_order=column_order,
        column_config=column_config,
        disabled=[col_nombre, "PROMEDIO", "TOTAL"],
    )

    st.session_state[f"em_editor_df_{tipo}"] = edited_df.to_dict(orient="records")

    st.divider()

# -----------------------------
# Guardado y aplicación
# -----------------------------
b1, b2 = st.columns(2)

with b1:
    if st.button("Guardar estudio de mercado", width="stretch"):
        ok_guardado = _guardar_desde_editores(int(st.session_state.get("em_num_cotizaciones", 3) or 3))
        if ok_guardado:
            st.success("Estudio de mercado guardado correctamente.")
            st.rerun()

with b2:
    if st.button("Asignar costos a APU consultoría", width="stretch"):
        ok_guardado = _guardar_desde_editores(int(st.session_state.get("em_num_cotizaciones", 3) or 3))
        if ok_guardado:
            _aplicar_a_hoja_10()
            st.rerun()
