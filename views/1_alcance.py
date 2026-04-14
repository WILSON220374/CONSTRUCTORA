import streamlit as st
import os
import uuid
import json
import pandas as pd
from streamlit_echarts import st_echarts
from supabase_state import cargar_estado
from supabase_state import guardar_estado as guardar_estado_bd

# --- ESCUDO SANITIZADOR (SOLUCIÓN AL APIError) ---
def guardar_estado(clave, datos):
    """
    Toma los datos de Streamlit, elimina los Proxies invisibles y envía un
    diccionario puro de Python a Supabase.
    """
    try:
        datos_puros = json.loads(json.dumps(datos))
    except Exception:
        def limpiar(obj):
            if isinstance(obj, dict) or hasattr(obj, 'items'):
                return {k: limpiar(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [limpiar(x) for x in obj]
            return obj
        datos_puros = limpiar(datos)
        
    guardar_estado_bd(clave, datos_puros)

# --- 1. CONFIGURACIÓN DE ALTURA DE TEXTO (REGLA: TEXTO + 2 LÍNEAS LIBRES) ---
def calcular_altura(texto, min_h=120):
    if not texto: return min_h
    texto_str = str(texto)
    # 1. Contamos saltos de línea (Enters) + la primera línea base
    lineas_reales = texto_str.count('\n') + 1 
    # 2. Red de seguridad muy baja (solo asume renglón extra si pasas 140 letras sin dar enter)
    lineas_por_ancho = len(texto_str) // 140 
    
    lineas_totales = lineas_reales + lineas_por_ancho
    
    # 3. La regla gerencial: Líneas totales del texto + 2 líneas libres garantizadas
    altura_calculada = (lineas_totales + 2) * 26 # 26 píxeles es el alto estándar de un renglón
    return max(min_h, altura_calculada)

# --- 2. INICIALIZACIÓN DE DATOS (ESTADO GLOBAL) ---
def inicializar_alcance():
    if "alcance_datos" not in st.session_state:
        st.session_state["alcance_datos"] = cargar_estado("alcance") or {}
    
    d = st.session_state["alcance_datos"]
    
    # --- CAMPOS INSTITUCIONALES ---
    if "entidad_formuladora" not in d: d["entidad_formuladora"] = ""
    if "division_dependencia" not in d: d["division_dependencia"] = ""
    if "lugar_presentacion" not in d: d["lugar_presentacion"] = ""
    if "anio_presentacion" not in d: d["anio_presentacion"] = ""
    
    if "nombre_proyecto" not in d: d["nombre_proyecto"] = ""
    if "descripcion_proyecto" not in d: d["descripcion_proyecto"] = ""
    if "alcance_definido" not in d: d["alcance_definido"] = ""
    if "objetivos" not in d: d["objetivos"] = []
    if "edt_data" not in d: d["edt_data"] = {}
    if "requiere_costos_indirectos" not in d: d["requiere_costos_indirectos"] = "No"
    if "otros_costos_indirectos_proyecto" not in d: d["otros_costos_indirectos_proyecto"] = []
    
    # --- NUEVO CAMPO: DESCRIPCIÓN DE LA EDT ---
    if "descripcion_edt" not in d: d["descripcion_edt"] = ""

    # --- MIGRACIÓN: PREPARAR TODOS LOS NIVELES PARA FICHAS TÉCNICAS (CON PROCEDIMIENTO) ---
    objetivos_con_id = []
    for obj in d["objetivos"]:
        nuevo_obj = {"id": str(uuid.uuid4()), "texto": obj} if isinstance(obj, str) else obj
        if "unidad" not in nuevo_obj: nuevo_obj["unidad"] = ""
        if "specs" not in nuevo_obj:
            nuevo_obj["specs"] = {"descripcion": "", "procedimiento": "", "materiales": "", "herramientas": "", "equipos": "", "medicion_pago": "", "no_conformidad": ""}
        elif "procedimiento" not in nuevo_obj["specs"]:
            nuevo_obj["specs"]["procedimiento"] = ""
        objetivos_con_id.append(nuevo_obj)
    d["objetivos"] = objetivos_con_id

    for oid, prods in d.get("edt_data", {}).items():
        for p in prods:
            if "unidad" not in p: p["unidad"] = ""
            if "specs" not in p: p["specs"] = {"descripcion": "", "procedimiento": "", "materiales": "", "herramientas": "", "equipos": "", "medicion_pago": "", "no_conformidad": ""}
            elif "procedimiento" not in p["specs"]: p["specs"]["procedimiento"] = ""
            for a in p.get("actividades", []):
                if "unidad" not in a: a["unidad"] = ""
                if "specs" not in a: a["specs"] = {"descripcion": "", "procedimiento": "", "materiales": "", "herramientas": "", "equipos": "", "medicion_pago": "", "no_conformidad": ""}
                elif "procedimiento" not in a["specs"]: a["specs"]["procedimiento"] = ""
                for pq in a.get("paquetes", []):
                    if "unidad" not in pq: pq["unidad"] = ""
                    if "specs" not in pq: pq["specs"] = {"descripcion": "", "procedimiento": "", "materiales": "", "herramientas": "", "equipos": "", "medicion_pago": "", "no_conformidad": ""}
                    elif "procedimiento" not in pq["specs"]: pq["specs"]["procedimiento"] = ""

inicializar_alcance()
datos = st.session_state["alcance_datos"]

datos_contrato_obra = st.session_state.get("contrato_obra_datos") or cargar_estado("contrato_obra") or {}
nombre_proyecto_contrato = str(datos_contrato_obra.get("objeto_general", "") or "").strip()

if nombre_proyecto_contrato and datos.get("nombre_proyecto", "") != nombre_proyecto_contrato:
    datos["nombre_proyecto"] = nombre_proyecto_contrato
    guardar_estado("alcance", datos)

if "zoom_edt" not in st.session_state:
    st.session_state["zoom_edt"] = 1.0

if "seccion_activa" not in st.session_state:
    st.session_state["seccion_activa"] = "📥 Datos de Entrada"

if "elemento_seleccionado_id" not in st.session_state: 
    st.session_state["elemento_seleccionado_id"] = None
if "modo_vista_specs" not in st.session_state:
    st.session_state["modo_vista_specs"] = "✏️ Edición"

# --- 3. DISEÑO CSS (TECNIC) ---
st.markdown("""
    <style>
    .titulo-seccion { font-size: 32px !important; font-weight: 800 !important; color: #145A32; }
    .subtitulo-gris { font-size: 16px !important; color: #666; margin-bottom: 15px; }
    div[data-testid="stProgress"] > div > div > div > div { background-color: #00FF7F !important; }
    section[data-testid="stSidebar"] { background-color: #f1f3f6; }
    .stButton > button { width: 100%; border-radius: 5px; height: 3em; font-weight: bold; }
    button[kind="primary"] { background-color: #2e7d32 !important; border-color: #2e7d32 !important; color: white !important; }
    button[kind="primary"]:hover { background-color: #1b5e20 !important; border-color: #1b5e20 !important; }
    button[kind="primary"]:focus:not(:active) { border-color: #1b5e20 !important; box-shadow: 0 0 0 0.2rem rgba(46, 125, 50, 0.5) !important; }
    </style>
""", unsafe_allow_html=True)

# --- 4. CABECERA ---
col_t, col_l = st.columns([4, 1], vertical_alignment="center")
with col_t:
    st.markdown('<div class="titulo-seccion">🎯 1. Alcance del Proyecto</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitulo-gris">Esta hoja solo conserva el nombre del proyecto, la EDT y los costos indirectos.</div>', unsafe_allow_html=True)
    campos_clave = [datos["nombre_proyecto"]]
    completos = sum([1 for x in campos_clave if x])
    st.progress(completos / 1, text=f"Progreso General: {int((completos/1)*100)}%")
with col_l:
    if os.path.exists("unnamed.jpg"):
        st.image("unnamed.jpg", use_container_width=True)
st.divider()

# --- 5. NAVEGACIÓN INTELIGENTE ---
c_nav1, c_nav2, c_nav3 = st.columns(3)
if c_nav1.button("📥 Datos de Entrada", use_container_width=True, type="primary" if st.session_state["seccion_activa"] == "📥 Datos de Entrada" else "secondary"):
    st.session_state["seccion_activa"] = "📥 Datos de Entrada"
if c_nav2.button("🗂️ EDT Gráfica", use_container_width=True, type="primary" if st.session_state["seccion_activa"] == "🗂️ EDT Gráfica" else "secondary"):
    st.session_state["seccion_activa"] = "🗂️ EDT Gráfica"
if c_nav3.button("📋 Especificaciones Técnicas", use_container_width=True, type="primary" if st.session_state["seccion_activa"] == "📋 Especificaciones Técnicas" else "secondary"):
    st.session_state["seccion_activa"] = "📋 Especificaciones Técnicas"

# --- 6. BARRA LATERAL (Panel de Gestión de EDT CONDICIONAL) ---
with st.sidebar:
    if st.session_state["seccion_activa"] == "🗂️ EDT Gráfica":
        st.header("🛠️ Gestión de EDT")
        st.markdown("Use este panel para añadir o eliminar elementos.")

        if not datos["nombre_proyecto"]:
            st.warning("⚠️ Primero diligencie el contrato de obra para que se cargue el nombre del proyecto.")
        else:
            with st.expander("🎯 Añadir Producto", expanded=False):
                with st.form("form_nuevo_objetivo_sidebar", clear_on_submit=True):
                    nuevo_txt = st.text_input("Escriba un nuevo producto:")
                    if st.form_submit_button("➕ Añadir Producto"):
                        if nuevo_txt.strip():
                            datos["objetivos"].append({
                                "id": str(uuid.uuid4()),
                                "texto": nuevo_txt.strip(),
                                "unidad": "",
                                "specs": {
                                    "descripcion": "",
                                    "procedimiento": "",
                                    "materiales": "",
                                    "herramientas": "",
                                    "equipos": "",
                                    "medicion_pago": "",
                                    "no_conformidad": ""
                                }
                            })
                            guardar_estado("alcance", datos)
                            st.rerun()
                            
            if not datos["objetivos"]:
                st.info("💡 Cree el primer objetivo para continuar configurando la EDT.")
            else:
                dict_obj = {}
                for i, obj in enumerate(datos["objetivos"]):
                    oid = obj["id"]
                    cod_obj = f"{i+1}"
                    dict_obj[oid] = f"{cod_obj}. {obj['texto']}"

                with st.expander("📦 Añadir Actividad"):
                    target_obj = st.selectbox(
                        "Producto Padre:",
                        options=list(dict_obj.keys()),
                        format_func=lambda x: dict_obj[x],
                        key="prod_obj_padre"
                    )
                    with st.form("form_sidebar_prod", clear_on_submit=True):
                        txt_p = st.text_input("Nombre de la Actividad:")
                        if st.form_submit_button("Guardar Actividad"):
                            if txt_p:
                                if target_obj not in datos["edt_data"]:
                                    datos["edt_data"][target_obj] = []

                                datos["edt_data"][target_obj].append({
                                    "id": str(uuid.uuid4()),
                                    "nombre": txt_p,
                                    "actividades": [],
                                    "unidad": "",
                                    "specs": {
                                        "descripcion": "",
                                        "procedimiento": "",
                                        "materiales": "",
                                        "herramientas": "",
                                        "equipos": "",
                                        "medicion_pago": "",
                                        "no_conformidad": ""
                                    }
                                })

                                guardar_estado("alcance", datos)
                                st.session_state["act_obj_padre"] = target_obj
                                st.session_state.pop("act_prod_padre", None)
                                st.session_state["paq_obj_padre"] = target_obj
                                st.session_state.pop("paq_prod_padre", None)
                                st.session_state.pop("paq_act_padre", None)
                                st.rerun()

                with st.expander("⚙️ Añadir Subactividad"):
                    target_obj_act = st.selectbox(
                        "Producto Padre:",
                        options=list(dict_obj.keys()),
                        format_func=lambda x: dict_obj[x],
                        key="act_obj_padre"
                    )

                    prod_list = datos["edt_data"].get(target_obj_act, [])
                    dict_prod_obj = {}

                    obj_idx = list(dict_obj.keys()).index(target_obj_act) + 1

                    for j, p in enumerate(prod_list):
                        pid = p["id"]
                        cod_prod = f"{obj_idx}.{j+1}"
                        dict_prod_obj[pid] = f"{cod_prod}. {p.get('nombre','')}"

                    if not dict_prod_obj:
                        st.info("Cree una actividad primero dentro de este producto.")
                    else:
                        target_prod = st.selectbox(
                            "Actividad Padre:",
                            options=list(dict_prod_obj.keys()),
                            format_func=lambda x: dict_prod_obj[x],
                            key="act_prod_padre"
                        )

                        with st.form("form_sidebar_act", clear_on_submit=True):
                            txt_a = st.text_input("Nombre de la Subactividad:")
                            if st.form_submit_button("Guardar Subactividad"):
                                if txt_a:
                                    for p in datos["edt_data"].get(target_obj_act, []):
                                        if p["id"] == target_prod:
                                            p.setdefault("actividades", [])
                                            p["actividades"].append({
                                                "id": str(uuid.uuid4()),
                                                "nombre": txt_a,
                                                "paquetes": [],
                                                "unidad": "",
                                                "specs": {
                                                    "descripcion": "",
                                                    "procedimiento": "",
                                                    "materiales": "",
                                                    "herramientas": "",
                                                    "equipos": "",
                                                    "medicion_pago": "",
                                                    "no_conformidad": ""
                                                }
                                            })
                                            break

                                    guardar_estado("alcance", datos)
                                    st.session_state["paq_obj_padre"] = target_obj_act
                                    st.session_state["paq_prod_padre"] = target_prod
                                    st.session_state.pop("paq_act_padre", None)
                                    st.rerun()

                with st.expander("🗑️ Eliminar Elemento", expanded=False):
                    filtro_tipo = st.radio("Filtre por categoría:", ["Producto", "Actividad", "Subactividad"], horizontal=True)
                    elementos_filtrados = {}
                    for i, obj in enumerate(datos["objetivos"]):
                        oid = obj["id"]; cod_obj = f"{i+1}"
                        for j, p in enumerate(datos["edt_data"].get(oid, [])):
                            cod_prod = f"{cod_obj}.{j+1}"
                            if filtro_tipo == "Producto":
                                elementos_filtrados[p["id"]] = {"nombre": f"{cod_prod}. {p['nombre']}", "tipo": "prod", "padre": oid}
                            for k, a in enumerate(p.get("actividades", [])):
                                cod_act = f"{cod_prod}.{k+1}"
                                if filtro_tipo == "Actividad":
                                    elementos_filtrados[a["id"]] = {"nombre": f"{cod_act}. {a['nombre']}", "tipo": "act", "padre": p["id"]}
                                for l, pq in enumerate(a.get("paquetes", [])):
                                    cod_paq = f"{cod_act}.{l+1}"
                                    if filtro_tipo == "Subactividad":
                                        elementos_filtrados[pq["id"]] = {"nombre": f"{cod_paq}. {pq['nombre']}", "tipo": "paq", "padre": a["id"]}

                    if not elementos_filtrados:
                        st.info(f"No hay elementos de la categoría '{filtro_tipo}' para eliminar.")
                    else:
                        with st.form("form_eliminar_nodo"):
                            target_del = st.selectbox(
                                f"Seleccione el {filtro_tipo}:",
                                options=list(elementos_filtrados.keys()),
                                format_func=lambda x: elementos_filtrados[x]["nombre"]
                            )
                            st.caption("⚠️ Al eliminar este elemento, también se borrarán sus dependencias.")
                            if st.form_submit_button("🗑️ Eliminar Definitivamente"):
                                if target_del:
                                    tipo = elementos_filtrados[target_del]["tipo"]
                                    padre_id = elementos_filtrados[target_del]["padre"]
                                    if tipo == "prod":
                                        if padre_id in datos["edt_data"]:
                                            p_borrar = next((p for p in datos["edt_data"][padre_id] if p["id"] == target_del), None)
                                            if p_borrar:
                                                datos["edt_data"][padre_id].remove(p_borrar)
                                    elif tipo == "act":
                                        for obj_list in datos["edt_data"].values():
                                            for p in obj_list:
                                                if p["id"] == padre_id:
                                                    a_borrar = next((a for a in p.get("actividades", []) if a["id"] == target_del), None)
                                                    if a_borrar:
                                                        p["actividades"].remove(a_borrar)
                                    elif tipo == "paq":
                                        for obj_list in datos["edt_data"].values():
                                            for p in obj_list:
                                                for a in p.get("actividades", []):
                                                    if a["id"] == padre_id:
                                                        pq_borrar = next((pq for pq in a.get("paquetes", []) if pq["id"] == target_del), None)
                                                        if pq_borrar:
                                                            a["paquetes"].remove(pq_borrar)
                                    guardar_estado("alcance", datos)
                                    
                                    st.rerun()
    else:
        st.info("💡 Navegue a '🗂️ EDT Gráfica' para gestionar la estructura.")


# ==========================================
# RENDERIZADO CONDICIONAL DE SECCIONES 
# ==========================================

if st.session_state["seccion_activa"] == "📥 Datos de Entrada":
    with st.container(border=True):
        st.markdown("#### 🏷️ Nombre del Proyecto")
        st.text_area(
            "Nombre del proyecto",
            value=datos["nombre_proyecto"],
            height=100,
            disabled=True,
            key="alcance_nombre_proyecto_desde_contrato"
        )
        st.caption("Este valor se toma automáticamente desde Contrato de obra → Sección 5 → Descripción general del objeto contractual.")

    with st.container(border=True):
        st.markdown("#### 💼 Costos indirectos del proyecto")
        requiere_costos_indirectos = st.selectbox(
            "¿El proyecto requiere costos indirectos?",
            options=["No", "Sí"],
            index=0 if datos.get("requiere_costos_indirectos", "No") == "No" else 1,
            key="alcance_requiere_costos_indirectos",
        )

        otros_costos_indirectos_proyecto = datos.get("otros_costos_indirectos_proyecto", []) or []

        if requiere_costos_indirectos == "Sí":
            with st.form("form_nuevo_costo_indirecto_proyecto", clear_on_submit=True):
                nuevo_costo_indirecto = st.text_input("Nombre del costo indirecto:")
                if st.form_submit_button("➕ Añadir costo indirecto"):
                    if nuevo_costo_indirecto.strip():
                        otros_costos_indirectos_proyecto.append(
                            {
                                "id": str(uuid.uuid4()),
                                "nombre": nuevo_costo_indirecto.strip(),
                            }
                        )
                        datos["otros_costos_indirectos_proyecto"] = otros_costos_indirectos_proyecto
                        datos["requiere_costos_indirectos"] = requiere_costos_indirectos
                        guardar_estado("alcance", datos)
                        st.rerun()

            for i, ci in enumerate(otros_costos_indirectos_proyecto):
                ci_id = ci.get("id", str(i))
                edit_key_ci = f"edit_ci_{ci_id}"
                txt_key_ci = f"txt_ci_{ci_id}"

                if edit_key_ci not in st.session_state:
                    st.session_state[edit_key_ci] = False
                if txt_key_ci not in st.session_state:
                    st.session_state[txt_key_ci] = ci.get("nombre", "")

                if st.session_state[edit_key_ci]:
                    c_ci1, c_ci2, c_ci3 = st.columns([0.75, 0.1, 0.1])
                    nuevo_nombre_ci = c_ci1.text_input(
                        f"Editar costo indirecto {i+1}",
                        value=st.session_state[txt_key_ci],
                        key=txt_key_ci,
                        label_visibility="collapsed",
                    )
                    if c_ci2.button("💾", key=f"save_ci_{ci_id}"):
                        datos["otros_costos_indirectos_proyecto"][i]["nombre"] = nuevo_nombre_ci
                        st.session_state[edit_key_ci] = False
                        datos["requiere_costos_indirectos"] = requiere_costos_indirectos
                        guardar_estado("alcance", datos)
                        st.rerun()
                    if c_ci3.button("✖", key=f"cancel_ci_{ci_id}"):
                        st.session_state[txt_key_ci] = ci.get("nombre", "")
                        st.session_state[edit_key_ci] = False
                        st.rerun()
                else:
                    c_ci1, c_ci2, c_ci3 = st.columns([0.8, 0.1, 0.1])
                    c_ci1.info(f"**{i+1}.** {ci.get('nombre', '')}")
                    if c_ci2.button("✏️", key=f"edit_ci_btn_{ci_id}"):
                        st.session_state[txt_key_ci] = ci.get("nombre", "")
                        st.session_state[edit_key_ci] = True
                        st.rerun()
                    if c_ci3.button("🗑️", key=f"del_ci_{ci_id}"):
                        ci_eliminado_id = str(ci.get("id", "") or "").strip()
                        if "costos_indirectos_proyecto_eliminados" not in datos or not isinstance(
                            datos.get("costos_indirectos_proyecto_eliminados"), list
                        ):
                            datos["costos_indirectos_proyecto_eliminados"] = []

                        if ci_eliminado_id:
                            if ci_eliminado_id not in datos["costos_indirectos_proyecto_eliminados"]:
                                datos["costos_indirectos_proyecto_eliminados"].append(ci_eliminado_id)

                        otros_costos_indirectos_proyecto.pop(i)
                        datos["otros_costos_indirectos_proyecto"] = otros_costos_indirectos_proyecto
                        datos["requiere_costos_indirectos"] = requiere_costos_indirectos
                        st.session_state.pop(edit_key_ci, None)
                        st.session_state.pop(txt_key_ci, None)
                        guardar_estado("alcance", datos)
                        st.rerun()

    if requiere_costos_indirectos != datos.get("requiere_costos_indirectos", "No"):
        datos["requiere_costos_indirectos"] = requiere_costos_indirectos
        guardar_estado("alcance", datos)
        st.rerun()

elif st.session_state["seccion_activa"] == "🗂️ EDT Gráfica":
    if not datos["nombre_proyecto"]:
        st.warning("⚠️ Debes diligenciar primero el contrato de obra para que se cargue el nombre del proyecto.")
    else:
        flat_table = []; nom_proy = str(datos["nombre_proyecto"]).upper()
        c_l0, c_l1, c_l2, c_l3, c_l4 = "#43A047", "#9370DB", "#C2185B", "#F57C00", "#00796B"
        g_l0, g_l1, g_l2, g_l3, g_l4 = "#E0E0E0", "#EBEBEB", "#F2F2F2", "#F7F7F7", "#FAFAFA"
        
        st.markdown("#### 🌳 ESTRUCTURA DE DESGLOSE DE TRABAJO DEL PROEYCTO")
        st.caption("💡 Utilice los botones para acercar o alejar. Pase el ratón sobre textos largos para leer todo.")
        
        col_btn1, col_btn2, _ = st.columns([0.15, 0.15, 0.7])
        if col_btn1.button("➕ Acercar"): st.session_state["zoom_edt"] = min(1.5, st.session_state["zoom_edt"] + 0.1)
        if col_btn2.button("➖ Alejar"): st.session_state["zoom_edt"] = max(0.5, st.session_state["zoom_edt"] - 0.1)
        
        zoom_factor = st.session_state["zoom_edt"]; nodos_terminales = 0; profundidad_maxima = 1
        
        if not datos["objetivos"]: nodos_terminales = 1
        else:
            profundidad_maxima = 2
            for obj in datos["objetivos"]:
                prods = datos["edt_data"].get(obj["id"], [])
                if not prods: nodos_terminales += 1
                else:
                    profundidad_maxima = max(profundidad_maxima, 3)
                    for p in prods:
                        acts = p.get("actividades", [])
                        if not acts: nodos_terminales += 1
                        else:
                            profundidad_maxima = max(profundidad_maxima, 4)
                            for a in acts:
                                paqs = a.get("paquetes", [])
                                if not paqs: nodos_terminales += 1
                                else:
                                    profundidad_maxima = max(profundidad_maxima, 5)
                                    nodos_terminales += len(paqs)
        
        altura_calculada = max(700, int(nodos_terminales * 160 * zoom_factor))
        altura_dinamica_str = f"{altura_calculada}px"
        ancho_calculado = max(1100, int(profundidad_maxima * 400 * zoom_factor))
        ancho_dinamico_str = f"{ancho_calculado}px"

        echarts_data = {"name": nom_proy, "itemStyle": {"color": c_l0}, "symbolSize": [int(280 * zoom_factor), int(85 * zoom_factor)], "children": []}
        flat_table.append({"Código": "0", "Nombre": nom_proy, "ColorBG": g_l0})

        for i, obj in enumerate(datos["objetivos"]):
            oid = obj["id"]; cod1 = f"{i+1}"
            node_l1 = {"name": f"{cod1}. {obj['texto']}", "itemStyle": {"color": c_l1}, "symbolSize": [int(270 * zoom_factor), int(80 * zoom_factor)], "children": []}
            flat_table.append({"Código": cod1, "Nombre": obj["texto"], "ColorBG": g_l1})
            
            if oid not in datos["edt_data"]: datos["edt_data"][oid] = []
            
            for j, prod in enumerate(datos["edt_data"][oid]):
                pid = prod["id"]; cod2 = f"{cod1}.{j+1}"
                node_l2 = {"name": f"{cod2}. {prod['nombre']}", "itemStyle": {"color": c_l2}, "symbolSize": [int(260 * zoom_factor), int(80 * zoom_factor)], "children": []}
                flat_table.append({"Código": cod2, "Nombre": prod["nombre"], "ColorBG": g_l2})
                
                for k, act in enumerate(prod.get("actividades", [])):
                    aid = act["id"]; cod3 = f"{cod2}.{k+1}"
                    node_l3 = {"name": f"{cod3}. {act['nombre']}", "itemStyle": {"color": c_l3}, "symbolSize": [int(250 * zoom_factor), int(75 * zoom_factor)], "children": []}
                    flat_table.append({"Código": cod3, "Nombre": act["nombre"], "ColorBG": g_l3})
                    
                    for l, paq in enumerate(act.get("paquetes", [])):
                        cod4 = f"{cod3}.{l+1}"
                        node_l3["children"].append({"name": f"{cod4}. {paq['nombre']}", "itemStyle": {"color": c_l4}, "symbolSize": [int(240 * zoom_factor), int(75 * zoom_factor)]})
                        flat_table.append({"Código": cod4, "Nombre": paq["nombre"], "ColorBG": g_l4})
                    
                    node_l2["children"].append(node_l3)
                node_l1["children"].append(node_l2)
            echarts_data["children"].append(node_l1)

        if datos.get("requiere_costos_indirectos", "No") == "Sí":
            costos_indirectos = datos.get("otros_costos_indirectos_proyecto", []) or []
            if costos_indirectos:
                cod_ci = f"{len(datos['objetivos']) + 1}"
                node_ci = {
                    "name": f"{cod_ci}. COSTOS INDIRECTOS DEL PROYECTO",
                    "itemStyle": {"color": c_l1},
                    "symbolSize": [int(270 * zoom_factor), int(80 * zoom_factor)],
                    "children": [],
                }
                flat_table.append({"Código": cod_ci, "Nombre": "COSTOS INDIRECTOS DEL PROYECTO", "ColorBG": g_l1})

                for j, ci in enumerate(costos_indirectos):
                    cod_ci_det = f"{cod_ci}.{j+1}"
                    nombre_ci = str(ci.get("nombre", "") or "").strip()
                    node_ci["children"].append(
                        {
                            "name": f"{cod_ci_det}. {nombre_ci}",
                            "itemStyle": {"color": c_l2},
                            "symbolSize": [int(260 * zoom_factor), int(80 * zoom_factor)],
                        }
                    )
                    flat_table.append({"Código": cod_ci_det, "Nombre": nombre_ci, "ColorBG": g_l2})

                echarts_data["children"].append(node_ci)

        options = {"tooltip": {"trigger": "item", "formatter": "{b}", "confine": True, "extraCssText": "white-space: normal; max-width: 350px; font-weight: bold; padding: 10px;"},
                   "series": [{"type": "tree", "data": [echarts_data], "top": "2%", "left": "10%", "bottom": "2%", "right": "15%", "symbol": "rect", "orient": "LR", "edgeShape": "polyline", "initialTreeDepth": -1, "roam": False, 
                               "label": {"position": "inside", "color": "white", "fontSize": int(13 * zoom_factor), "overflow": "break", "lineOverflow": "truncate", "width": int(230 * zoom_factor), "height": int(65 * zoom_factor), "lineHeight": int(16 * zoom_factor)},
                               "lineStyle": {"width": 2, "curveness": 0}, "expandAndCollapse": True, "animationDuration": 500}]}
        
        with st.container(): st_echarts(options, height=altura_dinamica_str, width=ancho_dinamico_str)

        st.divider(); st.markdown("#### 📊 Codificación")
        df = pd.DataFrame(flat_table)
        def aplicar_estilos_grises(row): return [f'background-color: {row["ColorBG"]}; color: black; font-weight: bold' for _ in row]
        st.dataframe(df.style.apply(aplicar_estilos_grises, axis=1), column_order=("Código", "Nombre"), use_container_width=True, hide_index=True, height=(len(df) * 36) + 40)

        # --- NUEVA SECCIÓN: DESCRIPCIÓN DE LA EDT (AUTO-AJUSTABLE Y GUARDADO INVISIBLE) ---
        st.divider()
        st.markdown("#### 📝 Descripción")
        st.info("💡 **Nota:** Haz clic fuera de la caja de texto tras escribir para que el tamaño se ajuste automáticamente y se guarde la información.")
        with st.container(border=True):
            k_desc_edt = "input_desc_edt"
            v_desc_edt = st.session_state.get(k_desc_edt, datos.get("descripcion_edt", ""))
            n_desc_edt = st.text_area("Descripción de la EDT", value=datos.get("descripcion_edt", ""), height=calcular_altura(v_desc_edt, 120), key=k_desc_edt, label_visibility="collapsed")
            
        if n_desc_edt != datos.get("descripcion_edt", ""):
            datos["descripcion_edt"] = n_desc_edt
            guardar_estado("alcance", datos)
            st.rerun()

# ==========================================
# SECCIÓN 3: ESPECIFICACIONES TÉCNICAS (NAVEGACIÓN MANUAL 100% SEGURA)
# ==========================================
elif st.session_state["seccion_activa"] == "📋 Especificaciones Técnicas":
    st.markdown("#### 📋 Especificaciones")
    
    # 1. SELECTOR DE NIVEL
    nivel_seleccionado = st.radio(
        "¿A qué nivel de la EDT desea registrar especificaciones?",
        ["Objetivos (Nivel 1)", "Productos (Nivel 2)", "Actividades (Nivel 3)", "Paquetes de Trabajo (Nivel 4)"],
        horizontal=True
    )
    
    # 2. RECOPILAR ELEMENTOS 
    lista_elementos = []
    if datos["objetivos"]:
        nom_proy_txt = datos["nombre_proyecto"] if datos["nombre_proyecto"] else "PROYECTO SIN NOMBRE"
        for i, obj in enumerate(datos["objetivos"]):
            cod_obj = f"{i+1}"
            nombre_capitulo = f"CAPÍTULO {cod_obj}. {obj['texto'].upper()}"
            if nivel_seleccionado == "Objetivos (Nivel 1)":
                lista_elementos.append({"id": obj["id"], "codigo": cod_obj, "nombre": obj["texto"], "capitulo": nombre_capitulo, "proyecto": nom_proy_txt, "data_ref": obj})
            for j, p in enumerate(datos["edt_data"].get(obj["id"], [])):
                cod_prod = f"{cod_obj}.{j+1}"
                if nivel_seleccionado == "Productos (Nivel 2)":
                    lista_elementos.append({"id": p["id"], "codigo": cod_prod, "nombre": p["nombre"], "capitulo": nombre_capitulo, "proyecto": nom_proy_txt, "data_ref": p})
                for k, a in enumerate(p.get("actividades", [])):
                    cod_act = f"{cod_prod}.{k+1}"
                    if nivel_seleccionado == "Actividades (Nivel 3)":
                        lista_elementos.append({"id": a["id"], "codigo": cod_act, "nombre": a["nombre"], "capitulo": nombre_capitulo, "proyecto": nom_proy_txt, "data_ref": a})
                    for l, pq in enumerate(a.get("paquetes", [])):
                        cod_paq = f"{cod_act}.{l+1}"
                        if nivel_seleccionado == "Paquetes de Trabajo (Nivel 4)":
                            lista_elementos.append({"id": pq["id"], "codigo": cod_paq, "nombre": pq["nombre"], "capitulo": nombre_capitulo, "proyecto": nom_proy_txt, "data_ref": pq})

    if datos.get("requiere_costos_indirectos", "No") == "Sí":
        costos_indirectos = datos.get("otros_costos_indirectos_proyecto", []) or []
        nom_proy_txt = datos["nombre_proyecto"] if datos["nombre_proyecto"] else "PROYECTO SIN NOMBRE"
        capitulo_ci = f"CAPÍTULO {len(datos['objetivos']) + 1}. COSTOS INDIRECTOS DEL PROYECTO"

        if nivel_seleccionado == "Objetivos (Nivel 1)" and costos_indirectos:
            lista_elementos.append({
                "id": "costos_indirectos_proyecto",
                "codigo": f"{len(datos['objetivos']) + 1}",
                "nombre": "COSTOS INDIRECTOS DEL PROYECTO",
                "capitulo": capitulo_ci,
                "proyecto": nom_proy_txt,
                "data_ref": datos.setdefault("costos_indirectos_specs", {"specs": {}})
            })

        if nivel_seleccionado == "Productos (Nivel 2)":
            for j, ci in enumerate(costos_indirectos):
                lista_elementos.append({
                    "id": ci["id"],
                    "codigo": f"{len(datos['objetivos']) + 1}.{j+1}",
                    "nombre": ci["nombre"],
                    "capitulo": capitulo_ci,
                    "proyecto": nom_proy_txt,
                    "data_ref": ci
                })

    if not lista_elementos:
        st.info(f"ℹ️ Aún no se han creado elementos para el nivel seleccionado: {nivel_seleccionado}.")
    else:
        # --- NUEVA LÓGICA: SEMÁFORO Y PROGRESO GERENCIAL ---
        completadas = 0
        opciones_selector = {}
        
        for elem in lista_elementos:
            specs = elem["data_ref"].get("specs", {})
            # Validamos si hay al menos un campo de texto con información en la ficha
            tiene_datos = any(str(v).strip() != "" for v in specs.values() if v is not None)
            
            if tiene_datos:
                completadas += 1
                etiqueta = f"🟢  {elem['codigo']} - {elem['nombre']}"
            else:
                etiqueta = f"🔴  {elem['codigo']} - {elem['nombre']}"
                
            opciones_selector[elem["id"]] = etiqueta
            
        total_elementos = len(lista_elementos)
        porcentaje = completadas / total_elementos if total_elementos > 0 else 0
        
        # Mostramos la barra de progreso
        st.markdown(f"**📊 Progreso de este nivel:** {completadas} de {total_elementos} Fichas Completadas ({int(porcentaje * 100)}%)")
        st.progress(porcentaje)
        st.markdown("<br>", unsafe_allow_html=True)
        # ---------------------------------------------------

        # 3. SELECTOR DE ELEMENTO E INTERRUPTOR DE MODO
        index_seleccion = 0
        if st.session_state.get("elemento_seleccionado_id") in opciones_selector:
            index_seleccion = list(opciones_selector.keys()).index(st.session_state["elemento_seleccionado_id"])

        c_sel1, c_sel2 = st.columns([7, 3])
        with c_sel1:
            # Selector nativo y seguro sin forzar keys externas
            seleccion_id = st.selectbox(
                "🔍 Seleccione el elemento a especificar:",
                options=list(opciones_selector.keys()),
                format_func=lambda x: opciones_selector[x],
                index=index_seleccion
            )
            st.session_state["elemento_seleccionado_id"] = seleccion_id
        
        with c_sel2:
            st.markdown("<br>", unsafe_allow_html=True) 
            modo_vista = st.radio("Modo de Interfaz:", ["✏️ Edición", "👁️ Lectura"], horizontal=True, label_visibility="collapsed")

        # 4. RENDERIZADO DE LA FICHA TÉCNICA
        if seleccion_id:
            elemento_actual = next((item for item in lista_elementos if item["id"] == seleccion_id), None)
            if elemento_actual:
                data_ref = elemento_actual["data_ref"] 
                specs_data = data_ref.get("specs", {})

                st.divider()

                # ==========================================
                # MODO EDICIÓN (Tarjetas Auto-ajustables con +2 Líneas)
                # ==========================================
                if modo_vista == "✏️ Edición":
                    st.markdown("##### 📝 Datos Básicos")
                    with st.container(border=True):
                        col_b1, col_b2, col_b3 = st.columns([1.5, 6, 2.5])
                        col_b1.text_input("Item", value=elemento_actual["codigo"], disabled=True)
                        col_b2.text_input("Nombre del Elemento", value=elemento_actual["nombre"], disabled=True)
                        nueva_unidad = col_b3.text_input("Unidad de Medida", value=data_ref.get("unidad", ""), key=f"u_{seleccion_id}")
                    
                    st.markdown("##### 🛠️ Especificaciones Técnicas")
                    st.info("💡 **Nota:** Haz clic fuera de la caja de texto tras escribir para que el tamaño se ajuste automáticamente.")
                    
                    with st.container(border=True):
                        k_desc = f"d_{seleccion_id}"
                        v_desc = st.session_state.get(k_desc, specs_data.get("descripcion", ""))
                        n_desc = st.text_area("📝 Descripción Detallada", value=specs_data.get("descripcion", ""), height=calcular_altura(v_desc, 120), key=k_desc)
                        
                        k_proc = f"p_{seleccion_id}"
                        v_proc = st.session_state.get(k_proc, specs_data.get("procedimiento", ""))
                        n_proc = st.text_area("⚙️ Procedimiento de Ejecución", value=specs_data.get("procedimiento", ""), height=calcular_altura(v_proc, 120), key=k_proc)
                        
                        col_m1, col_m2 = st.columns(2)
                        k_mat = f"m_{seleccion_id}"
                        v_mat = st.session_state.get(k_mat, specs_data.get("materiales", ""))
                        n_mat = col_m1.text_area("🧱 Materiales", value=specs_data.get("materiales", ""), height=calcular_altura(v_mat, 120), key=k_mat)
                        
                        k_herr = f"h_{seleccion_id}"
                        v_herr = st.session_state.get(k_herr, specs_data.get("herramientas", ""))
                        n_herr = col_m2.text_area("🛠️ Herramientas", value=specs_data.get("herramientas", ""), height=calcular_altura(v_herr, 120), key=k_herr)
                        
                        col_e1, col_e2 = st.columns(2)
                        k_eq = f"e_{seleccion_id}"
                        v_eq = st.session_state.get(k_eq, specs_data.get("equipos", ""))
                        n_equip = col_e1.text_area("🚜 Equipos", value=specs_data.get("equipos", ""), height=calcular_altura(v_eq, 120), key=k_eq)
                        
                        k_mp = f"mp_{seleccion_id}"
                        v_mp = st.session_state.get(k_mp, specs_data.get("medicion_pago", ""))
                        n_med = col_e2.text_area("📏 Medición y Forma de Pago", value=specs_data.get("medicion_pago", ""), height=calcular_altura(v_mp, 120), key=k_mp)
                        
                        k_nc = f"nc_{seleccion_id}"
                        v_nc = st.session_state.get(k_nc, specs_data.get("no_conformidad", ""))
                        n_noconf = st.text_area("⚠️ No Conformidad", value=specs_data.get("no_conformidad", ""), height=calcular_altura(v_nc, 100), key=k_nc)
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    # --- NAVEGACIÓN 100% MANUAL: UN SOLO BOTÓN ---
                    col_btn1, col_btn_vacia = st.columns([3, 7])
                    
                    if col_btn1.button("💾 Guardar Cambios", type="primary", use_container_width=True):
                        # Guardar en memoria
                        data_ref["unidad"] = nueva_unidad
                        specs_data["descripcion"] = n_desc
                        specs_data["procedimiento"] = n_proc
                        specs_data["materiales"] = n_mat
                        specs_data["herramientas"] = n_herr
                        specs_data["equipos"] = n_equip
                        specs_data["medicion_pago"] = n_med
                        specs_data["no_conformidad"] = n_noconf
                        
                        # Guardar en base de datos
                        guardar_estado("alcance", datos)
                        st.success("✅ Ficha guardada correctamente. Use el menú superior para cambiar de elemento.")
                        # Recargamos para que el semáforo y la barra de progreso se actualicen en vivo
                        st.rerun() 

                # ==========================================
                # MODO LECTURA (Dossier Ejecutivo Premium)
                # ==========================================
                else:
                    def formato_html(texto):
                        if not texto: return "<span style='color: #a1a1aa; font-style: italic;'>Sin información registrada...</span>"
                        return str(texto).replace('\n', '<br>')
                    
                    html_dossier = (
                        "<div style='background-color: #f8fafc; padding: 30px; border-radius: 12px; font-family: sans-serif;'>"
                        f"<div style='color: #64748b; font-size: 13px; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px;'>{formato_html(elemento_actual['proyecto'])} &nbsp;&rsaquo;&nbsp; {formato_html(elemento_actual['capitulo'])}</div>"
                        f"<h2 style='color: #0f172a; margin: 0 0 15px 0; font-size: 26px; font-weight: 700;'>{formato_html(elemento_actual['nombre'])}</h2>"
                        "<div style='margin-bottom: 30px;'>"
                        f"<span style='background-color: #e2e8f0; color: #334155; padding: 6px 12px; border-radius: 16px; font-size: 13px; font-weight: 600; margin-right: 12px; display: inline-block;'>ID: {formato_html(elemento_actual['codigo'])}</span>"
                        f"<span style='background-color: #dcfce7; color: #065f46; padding: 6px 12px; border-radius: 16px; font-size: 13px; font-weight: 600; display: inline-block;'>UNIDAD: {formato_html(data_ref.get('unidad', '-'))}</span>"
                        "</div>"
                        "<div style='background-color: #ffffff; padding: 35px; border-radius: 10px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);'>"
                    )
                    
                    def bloque_lectura(icono, titulo, clave):
                        valor = formato_html(specs_data.get(clave, ""))
                        return (
                            "<div style='margin-bottom: 28px;'>"
                            f"<h4 style='color: #166534; font-size: 16px; margin: 0 0 10px 0; font-weight: 700; display: flex; align-items: center;'><span style='margin-right: 8px; font-size: 18px;'>{icono}</span> {titulo}</h4>"
                            f"<div style='border-left: 3px solid #e2e8f0; padding-left: 18px; color: #334155; font-size: 15px; line-height: 1.6;'>{valor}</div>"
                            "</div>"
                        )
                        
                    html_dossier += bloque_lectura("📝", "Descripción Detallada", "descripcion")
                    html_dossier += bloque_lectura("⚙️", "Procedimiento de Ejecución", "procedimiento")
                    html_dossier += bloque_lectura("🧱", "Materiales Requeridos", "materiales")
                    html_dossier += bloque_lectura("🛠️", "Herramientas", "herramientas")
                    html_dossier += bloque_lectura("🚜", "Equipos Necesarios", "equipos")
                    html_dossier += bloque_lectura("📏", "Medición y Forma de Pago", "medicion_pago")
                    html_dossier += bloque_lectura("⚠️", "Condiciones de No Conformidad", "no_conformidad")
                    
                    html_dossier += "</div></div>"
                    
                    st.markdown(html_dossier, unsafe_allow_html=True)
