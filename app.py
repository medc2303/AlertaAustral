import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURACIÓN DE PÁGINA RESPONSIVA ---
st.set_page_config(page_title="🗺️ Alerta Austral 📍", page_icon="🗺️", layout="centered")

SHEET_URL = "https://docs.google.com/spreadsheets/d/11mPB_wV3ogbxgExGj5E7BI_L1uL3tzUxnwDh2NlHn4Q/edit"

# --- INICIALIZACIÓN DE ESTADO PERSISTENTE (Solución de Coordenadas) ---
if "click_lat" not in st.session_state:
    st.session_state.click_lat = None
if "click_lon" not in st.session_state:
    st.session_state.click_lon = None

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

# --- CSS MODO OSCURO MÓVIL ---
st.markdown('''
    <style>
    .stApp { background-color: #1a1a1a; color: white !important; }
    h1, h2, h3, h4, h5, h6, p, div, span, label, li, small, strong { color: #FFFFFF !important; }
    
    .stTextInput input {
        background-color: #333333 !important; color: white !important; border: 1px solid #555 !important;
        padding: 12px !important; font-size: 16px !important;
    }
    
    .stButton button {
        background-color: #d9534f !important; color: white !important; border: 1px solid white !important;
        width: 100% !important; padding: 15px !important; font-size: 18px !important; font-weight: bold !important; border-radius: 8px !important;
    }
    
    .status-card, .danger-card {
        background-color: #2b2b2b !important; border: 1px solid #444; padding: 15px; border-radius: 10px; margin-bottom: 12px; color: white !important;
    }
    .danger-card { border-left: 5px solid #d9534f; }
    
    .main-header {
        font-family: 'Helvetica Neue', sans-serif; color: #FFFFFF !important; text-align: center; font-size: 2.2em; font-weight: bold; text-shadow: 2px 2px 4px #000000; padding-bottom: 10px; margin-bottom: 15px; border-bottom: 2px dashed #FFFFFF;
    }
    </style>
    <div class="main-header">🚨 Alerta Austral 📱</div>
    ''', unsafe_allow_html=True)

# --- FLUJO PRINCIPAL Y LIMPIEZA DE DATOS ---
try:
    gc = init_gspread()
    sheet = gc.open_by_url(SHEET_URL).sheet1
    datos = sheet.get_all_records()
    df = pd.DataFrame(datos)
    
except Exception as e:
    st.error(f"Error crítico conectando con Google Sheets: {e}")
    df = pd.DataFrame()

if df.empty:
    alertas_activas = pd.DataFrame()
else:
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
        alertas_activas = df[df["Estado"].astype(str).str.strip().str.lower() == "inundado"]
    else:
        alertas_activas = df

# --- CONFIGURACIÓN DEL MAPA ---
centro_lat_pm = -41.4693
centro_lon_pm = -72.9423
zoom_inicial = 14

st.caption("📱 *Toca cualquier calle en el mapa para reportar una inundación a la base de datos.*")

mapa = folium.Map(location=[centro_lat_pm, centro_lon_pm], zoom_start=zoom_inicial, tiles="OpenStreetMap")

# Pintar alertas en el mapa
if not alertas_activas.empty:
    for _, fila in alertas_activas.iterrows():
        folium.Circle(
            location=[float(fila["Latitud"]), float(fila["Longitud"])],
            radius=50,
            color="#d9534f",
            fill=True,
            fill_color="#d9534f",
            fill_opacity=0.5,
            popup=folium.Popup(f"⚠️ <b>{fila.get('Lugar', 'Punto Registrado')}</b><br><i>{fila.get('Descripcion', '')}</i>", max_width=200)
        ).add_to(mapa)

mapa_salida = st_folium(mapa, width="100%", height=400, key="mapa_movil_pm")

# --- CAPTURA PERSISTENTE DEL CLICK ---
if mapa_salida and mapa_salida.get("last_clicked"):
    # Guardamos en memoria solo si el click es un evento nuevo
    st.session_state.click_lat = mapa_salida["last_clicked"]["lat"]
    st.session_state.click_lon = mapa_salida["last_clicked"]["lng"]

# Si hay coordenadas en memoria, desplegamos el formulario
if st.session_state.click_lat is not None and st.session_state.click_lon is not None:
    # Bloqueamos las variables de lectura usando la memoria del servidor
    lat_actual = st.session_state.click_lat
    lon_actual = st.session_state.click_lon

    with st.spinner("Localizando..."):
        try:
            geolocator = Nominatim(user_agent="alerta_austral_bot")
            location = geolocator.reverse((lat_actual, lon_actual), timeout=3)
            calle_detectada = location.raw['address']['road'] if location and 'road' in location.raw['address'] else "Punto Registrado"
        except Exception:
            calle_detectada = "Punto Registrado"

    st.write("---")
    st.markdown("### 🚨 Confirmar y Enviar Alerta")

    with st.form("registro_inundacion_db", clear_on_submit=True):
        st.info(f"📍 Calle detectada: **{calle_detectada}**")
        calle_final = st.text_input("Nombre de la vía:", value=calle_detectada)
        descripcion_incidente = st.text_input("Detalle del incidente:", value="Agua acumulada en calzada")

        boton_reportar = st.form_submit_button("🚨 GUARDAR REPORTE")

        if boton_reportar:
            nueva_fila = [calle_final, str(lat_actual), str(lon_actual), descripcion_incidente, "Inundado"]
            
            try:
                sheet.insert_row(nueva_fila, index=2)
                st.success("¡Alerta registrada exitosamente en Google Sheets!")
                
                # PURGA DE ESTADO: Limpiamos la memoria tras la inserción exitosa
                st.session_state.click_lat = None
                st.session_state.click_lon = None
                
                # Forzamos un rerun para limpiar la UI y actualizar el mapa
                st.rerun()
            except Exception as e:
                st.error(f"Fallo al guardar en la base de datos: {e}")

# --- PANEL DE MONITOREO ---
st.write("---")
cantidad_alertas = len(alertas_activas) if not alertas_activas.empty else 0
st.markdown(f"### 📊 Emergencias Activas ({cantidad_alertas})")

if alertas_activas.empty:
    st.info("La base de datos no registra calles inundadas actualmente.")
else:
    for _, alerta in alertas_activas.iterrows():
        st.markdown(f"""
        <div class="danger-card">
            <strong>⚠️ {alerta.get('Lugar', 'Alerta Registrada')}</strong><br>
            <span style="font-size: 0.85em; color: #ffcccc !important;">{alerta.get('Descripcion', '')}</span><br>
            <span style="font-size: 0.8em; color: #aaa !important;">Coord: {alerta.get('Latitud', 0):.4f}, {alerta.get('Longitud', 0):.4f}</span>
        </div>
        """, unsafe_allow_html=True)
