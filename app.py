import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from zoneinfo import ZoneInfo

# --- CONFIGURACIÓN DE PÁGINA RESPONSIVA ---
st.set_page_config(page_title="🗺️ Alerta Austral 📍", page_icon="🗺️", layout="centered")

# Tu hoja original
SHEET_URL = "https://docs.google.com/spreadsheets/d/11mPB_wV3ogbxgExGj5E7BI_L1uL3tzUxnwDh2NlHn4Q/edit"

# --- INICIALIZACIÓN DE ESTADO PERSISTENTE ---
if "ultimo_click_procesado" not in st.session_state:
    st.session_state.ultimo_click_procesado = None
if "ultimo_objeto_clickeado" not in st.session_state:
    st.session_state.ultimo_objeto_clickeado = None

# --- CONEXIÓN CON GOOGLE SHEETS VIA BOT ---
@st.cache_resource
def init_gspread():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )
    client = gspread.authorize(credentials)
    return client

# --- FUNCIONES DE LIMPIEZA MATEMÁTICA ---
def limpiar_dataframe(df):
    if df.empty:
        return df
    df.columns = df.columns.str.strip()
    if "Latitud" in df.columns and "Longitud" in df.columns:
        df["Latitud"] = df["Latitud"].astype(str).str.replace(',', '.')
        df["Longitud"] = df["Longitud"].astype(str).str.replace(',', '.')
        df["Latitud"] = pd.to_numeric(df["Latitud"], errors='coerce')
        df["Longitud"] = pd.to_numeric(df["Longitud"], errors='coerce')
        df.loc[df["Latitud"] < -90, "Latitud"] = df["Latitud"] / 10000
        df.loc[df["Longitud"] < -180, "Longitud"] = df["Longitud"] / 10000
        df = df.dropna(subset=["Latitud", "Longitud"])
    if "Estado" in df.columns:
        df["Estado_clean"] = df["Estado"].astype(str).str.strip().str.lower()
    return df

# --- LECTURAS INDEPENDIENTES DE PESTAÑAS (CON CACHÉ ANTI-429) ---
@st.cache_data(ttl=30)
def obtener_calles():
    try:
        gc = init_gspread()
        sheet = gc.open_by_url(SHEET_URL).sheet1  # Pestaña Principal (Calles)
        return limpiar_dataframe(pd.DataFrame(sheet.get_all_records()))
    except Exception as e:
        st.error(f"Error cargando calles: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=30)
def obtener_paraderos():
    try:
        gc = init_gspread()
        sheet = gc.open_by_url(SHEET_URL).worksheet("Hoja 2") # Pestaña Paraderos
        return limpiar_dataframe(pd.DataFrame(sheet.get_all_records()))
    except Exception as e:
        st.error(f"Error cargando paraderos (Hoja 2): {e}")
        return pd.DataFrame()

# --- FUNCIÓN CENTRALIZADA DE ACTUALIZACIÓN ---
def actualizar_estado_db(fila_ref, nuevo_estado, nombre_pestana="sheet1"):
    try:
        with st.spinner("Actualizando base de datos..."):
            gc = init_gspread()
            doc = gc.open_by_url(SHEET_URL)
            sheet = doc.sheet1 if nombre_pestana == "sheet1" else doc.worksheet(nombre_pestana)
            
            valores_crudos = sheet.get_all_values()
            fila_a_modificar = None

            for i, r in enumerate(valores_crudos[1:], start=2):
                try:
                    r_lat = float(str(r[1]).replace(',', '.'))
                    r_lon = float(str(r[2]).replace(',', '.'))
                    if abs(r_lat - fila_ref["Latitud"]) < 1e-4 and abs(r_lon - fila_ref["Longitud"]) < 1e-4 and str(r[4]).strip() == fila_ref["Estado"]:
                        fila_a_modificar = i
                        break
                except:
                    continue

            if fila_a_modificar:
                sheet.update_cell(fila_a_modificar, 5, nuevo_estado)
                
                # Ajuste de hora para Chile (Santiago/Puerto Montt)
                hora_actual = datetime.now(ZoneInfo("America/Santiago")).strftime("%H:%M (%d/%m)")
                
                # Intentamos actualizar la hora si la columna existe (índice 6)
                if len(r) >= 6 or sheet.col_count >= 6:
                    sheet.update_cell(fila_a_modificar, 6, hora_actual)
                
                # Purgamos ambos cachés para forzar actualización visual
                obtener_calles.clear()
                obtener_paraderos.clear()
                st.success("¡Base de datos sincronizada!")
                st.session_state.ultimo_click_procesado = None
                st.session_state.ultimo_objeto_clickeado = None
                st.rerun()
            else:
                st.error("No se encontró el registro físico en las celdas.")
    except Exception as e:
        st.error(f"Error: {e}")

# --- DEFINICIÓN DE VENTANAS EMERGENTES (MODALS) ---
@st.dialog("🚨 Registrar Nueva Calle Inundada")
def modal_nueva_alerta(lat, lon):
    with st.spinner("Localizando nombre de la vía..."):
        try:
            geolocator = Nominatim(user_agent="alerta_austral_bot")
            location = geolocator.reverse((lat, lon), timeout=3)
            calle_detectada = location.raw['address']['road'] if location and 'road' in location.raw['address'] else "Punto Registrado"
        except Exception:
            calle_detectada = "Punto Registrado"

    st.info("📍 Coordenadas capturadas correctamente en la calle.")
    calle_final = st.text_input("Confirmar nombre de la calle:", value=calle_detectada)
    descripcion_incidente = st.text_input("Detalle del incidente:", value="Agua acumulada en calzada")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("❌ Cancelar", use_container_width=True):
            st.session_state.ultimo_click_procesado = None
            st.session_state.ultimo_objeto_clickeado = None
            st.rerun()
    with col2:
        if st.button("🚨 Guardar Alerta", type="primary", use_container_width=True):
            # Ajuste de hora para Chile
            hora_reporte = datetime.now(ZoneInfo("America/Santiago")).strftime("%H:%M (%d/%m)")
            nueva_fila = [calle_final, str(lat), str(lon), descripcion_incidente, "Inundado", hora_reporte]
            try:
                gc = init_gspread()
                sheet = gc.open_by_url(SHEET_URL).sheet1
                sheet.insert_row(nueva_fila, index=2)
                obtener_calles.clear()
                st.success("¡Alerta registrada!")
                st.session_state.ultimo_click_procesado = None
                st.session_state.ultimo_objeto_clickeado = None
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

@st.dialog("🔄 Gestionar Calle Inundada")
def modal_eliminar_alerta(alerta):
    st.info(f"📍 **Calle:** {alerta.get('Lugar')}\n\n🕒 **Reportado a las:** {alerta.get('Hora', 'Sin Registro')}\n\n📝 **Detalle:** {alerta.get('Descripcion')}")
    st.markdown("<p style='text-align: center; font-weight: bold;'>¿El tránsito volvió a la normalidad?</p>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("❌ Cancelar", use_container_width=True):
            st.session_state.ultimo_click_procesado = None
            st.session_state.ultimo_objeto_clickeado = None
            st.rerun()
    with col2:
        if st.button("✅ Despejar Calle", type="primary", use_container_width=True):
            actualizar_estado_db(alerta, "Historial", "sheet1")

@st.dialog("🚏 Gestionar Paradero")
def modal_gestionar_paradero(paradero):
    st.info(f"📍 **Paradero:** {paradero.get('Lugar')}\n\n📝 **Detalle:** {paradero.get('Descripcion')}")
    estado_limpio = paradero.get("Estado_clean")

    if estado_limpio == "paradero normal":
        st.markdown("<p style='text-align: center; font-weight: bold;'>¿Qué problema presenta este paradero?</p>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🌊 Inundado", use_container_width=True):
                actualizar_estado_db(paradero, "Paradero Inundado", "Hoja 2")
        with col2:
            if st.button("⚠️ Mal Estado", use_container_width=True):
                actualizar_estado_db(paradero, "Paradero Mal Estado", "Hoja 2")
    else:
        st.markdown("<p style='text-align: center; font-weight: bold;'>¿Este paradero ya fue reparado o despejado?</p>", unsafe_allow_html=True)
        if st.button("✅ Volver a la Normalidad", type="primary", use_container_width=True):
            actualizar_estado_db(paradero, "Paradero Normal", "Hoja 2")

    if st.button("❌ Cerrar menú", use_container_width=True):
        st.session_state.ultimo_click_procesado = None
        st.session_state.ultimo_objeto_clickeado = None
        st.rerun()

# --- CSS MODO OSCURO MÓVIL ---
st.markdown('''
    <style>
    .stApp { background-color: #1a1a1a; color: white !important; }
    h1, h2, h3, h4, h5, h6, p, div, span, label, li, small, strong { color: #FFFFFF !important; }
    .stTextInput input { background-color: #333333 !important; color: white !important; border: 1px solid #555 !important; padding: 12px !important; }
    div[data-testid="stDialog"] div[role="dialog"] { background-color: #222 !important; border: 1px solid #555; border-radius: 12px; }
    .status-card, .danger-card, .warning-card { background-color: #2b2b2b !important; border: 1px solid #444; padding: 15px; border-radius: 10px; margin-bottom: 12px; color: white !important; }
    .danger-card { border-left: 5px solid #d9534f; }
    .warning-card { border-left: 5px solid #f0ad4e; }
    .main-header { font-family: 'Helvetica Neue', sans-serif; color: #FFFFFF !important; text-align: center; font-size: 2.2em; font-weight: bold; padding-bottom: 10px; margin-bottom: 15px; border-bottom: 2px dashed #FFFFFF; }
    </style>
    <div class="main-header">🚨 Alerta Austral 📱</div>
    ''', unsafe_allow_html=True)

# --- CARGA DE DATOS SEPARADOS ---
df_calles = obtener_calles()
df_paraderos = obtener_paraderos()

# Procesamiento segmentado
calles_inundadas = df_calles[df_calles["Estado_clean"] == "inundado"] if not df_calles.empty else pd.DataFrame()
paraderos_activos = df_paraderos if not df_paraderos.empty else pd.DataFrame()

# Construir panel inferior (Combinando reportes críticos)
lista_emergencias = []
if not calles_inundadas.empty:
    lista_emergencias.append(calles_inundadas)
if not paraderos_activos.empty:
    paraderos_con_problemas = paraderos_activos[paraderos_activos["Estado_clean"].isin(["paradero inundado", "paradero mal estado"])]
    if not paraderos_con_problemas.empty:
        lista_emergencias.append(paraderos_con_problemas)

emergencias_activas = pd.concat(lista_emergencias, ignore_index=True) if lista_emergencias else pd.DataFrame()

# --- RENDERIZADO DEL MAPA ---
centro_lat_pm = -41.4693
centro_lon_pm = -72.9423
zoom_inicial = 14

st.caption("📱 *Toca una calle para reportar, o toca un Paradero (🚏) para administrarlo.*")

mapa = folium.Map(location=[centro_lat_pm, centro_lon_pm], zoom_start=zoom_inicial, tiles="OpenStreetMap")

# 1. Pintar Calles Inundadas
if not calles_inundadas.empty:
    for _, fila in calles_inundadas.iterrows():
        folium.Circle(
            location=[float(fila["Latitud"]), float(fila["Longitud"])],
            radius=50, color="#d9534f", fill=True, fill_color="#d9534f", fill_opacity=0.5,
            tooltip="Calle Inundada (Toca para administrar)"
        ).add_to(mapa)

# 2. Pintar Paraderos (SOLO dibujamos el ícono del bus con su color respectivo)
if not paraderos_activos.empty:
    for _, p in paraderos_activos.iterrows():
        estado_p = p["Estado_clean"]
        lat = float(p["Latitud"])
        lon = float(p["Longitud"])
        
        if estado_p == "paradero normal":
            folium.Marker(
                location=[lat, lon],
                icon=folium.Icon(color="blue", icon="bus", prefix="fa"),
                tooltip="🚏 Paradero Normal (Toca para reportar)"
            ).add_to(mapa)
            
        elif estado_p == "paradero inundado":
            # Marcador rojo sin círculo
            folium.Marker(
                location=[lat, lon],
                icon=folium.Icon(color="red", icon="bus", prefix="fa"),
                tooltip="🚨 Paradero Inundado (Toca para despejar)"
            ).add_to(mapa)
            
        elif estado_p == "paradero mal estado":
            # Marcador naranjo sin círculo
            folium.Marker(
                location=[lat, lon],
                icon=folium.Icon(color="orange", icon="bus", prefix="fa"),
                tooltip="⚠️ Paradero en Mal Estado (Toca para despejar)"
            ).add_to(mapa)

mapa_salida = st_folium(mapa, width="100%", height=400, key="mapa_movil_pm")

# --- PROCESAMIENTO INTELIGENTE DE CLICKS (MAPA Y MARCADORES) ---
click_mapa = mapa_salida.get("last_clicked")
click_objeto = mapa_salida.get("last_object_clicked")

click_a_procesar = None

# Priorizamos si se tocó directamente el marcador (ícono de bus)
if click_objeto and click_objeto != st.session_state.ultimo_objeto_clickeado:
    st.session_state.ultimo_objeto_clickeado = click_objeto
    click_a_procesar = click_objeto

# Si no tocó marcador, revisamos si tocó una parte del mapa (calle o zona cercana)
elif click_mapa and click_mapa != st.session_state.ultimo_click_procesado:
    st.session_state.ultimo_click_procesado = click_mapa
    click_a_procesar = click_mapa

# Si hay un toque válido registrado
if click_a_procesar:
    lat_actual = click_a_procesar["lat"]
    lon_actual = click_a_procesar["lng"]

    # 1. Comprobar si tocó un Paradero (Hoja 2)
    paradero_coincidente = None
    if not paraderos_activos.empty:
        for _, p in paraderos_activos.iterrows():
            if abs(p["Latitud"] - lat_actual) < 0.0008 and abs(p["Longitud"] - lon_actual) < 0.0008:
                paradero_coincidente = p
                break

    # 2. Comprobar si tocó una Calle Inundada (Pestaña principal)
    alerta_coincidente = None
    if paradero_coincidente is None and not calles_inundadas.empty:
        for _, fila_activa in calles_inundadas.iterrows():
            if abs(fila_activa["Latitud"] - lat_actual) < 0.0008 and abs(fila_activa["Longitud"] - lon_actual) < 0.0008:
                alerta_coincidente = fila_activa
                break

    # 3. Lanzar Modal según el tipo de elemento
    if paradero_coincidente is not None:
        modal_gestionar_paradero(paradero_coincidente)
    elif alerta_coincidente is not None:
        modal_eliminar_alerta(alerta_coincidente)
    else:
        modal_nueva_alerta(lat_actual, lon_actual)

# --- PANEL DE MONITOREO EN VIVO ---
st.write("---")
cantidad_alertas = len(emergencias_activas) if not emergencias_activas.empty else 0
st.markdown(f"### 📊 Emergencias Activas ({cantidad_alertas})")

if emergencias_activas.empty:
    st.info("La ciudad no registra emergencias en calles ni paraderos actualmente.")
else:
    for _, alerta in emergencias_activas.iterrows():
        hora_display = alerta.get('Hora', '---') if pd.notna(alerta.get('Hora')) and alerta.get('Hora') != "" else "---"
        estado_alerta = alerta.get('Estado_clean', '')
        
        clase_css = "warning-card" if estado_alerta == "paradero mal estado" else "danger-card"
        icono = "⚠️" if estado_alerta == "paradero mal estado" else "🚨"

        st.markdown(f"""
        <div class="{clase_css}">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <strong>{icono} {alerta.get('Lugar', 'Punto Registrado')}</strong>
                <span style="font-size: 0.85em; color: #aaaaaa !important; font-weight: bold; background-color: #333; padding: 2px 8px; border-radius: 5px;">🕒 {hora_display}</span>
            </div>
            <div style="margin-top: 5px;">
                <span style="font-size: 0.85em; color: #ffcccc !important;">{alerta.get('Descripcion', '')}</span><br>
                <span style="font-size: 0.8em; color: #aaa !important;">Coord: {alerta.get('Latitud', 0):.4f}, {alerta.get('Longitud', 0):.4f}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
