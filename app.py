import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA RESPONSIVA ---
st.set_page_config(page_title="🗺️ Alerta Austral 📍", page_icon="🗺️", layout="centered")

SHEET_URL = "https://docs.google.com/spreadsheets/d/11mPB_wV3ogbxgExGj5E7BI_L1uL3tzUxnwDh2NlHn4Q/edit"

# --- INICIALIZACIÓN DE ESTADO PERSISTENTE ---
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
    
    /* Variación de botón verde para solucionar/despejar calles */
    div.stForm [data-testid="stFormSubmitButton"] button {
        background-color: #d9534f !important;
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

    # Filtrar únicamente las que siguen marcadas estrictamente como "Inundado"
    if "Estado" in df.columns:
        alertas_activas = df[df["Estado"].astype(str).str.strip().str.lower() == "inundado"]
    else:
        alertas_activas = df

# --- CONFIGURACIÓN DEL MAPA EN PUERTO MONTT ---
centro_lat_pm = -41.4693
centro_lon_pm = -72.9423
zoom_inicial = 14

st.caption("📱 *Toca una zona vacía para reportar, o toca un círculo rojo existente para remover la alerta si la calle se despejó.*")

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
            popup=folium.Popup(f"⚠️ <b>{fila.get('Lugar', 'Punto Registrado')}</b><br>🕒 {fila.get('Hora', '---')}<br><i>{fila.get('Descripcion', '')}</i>", max_width=200)
        ).add_to(mapa)

mapa_salida = st_folium(mapa, width="100%", height=400, key="mapa_movil_pm")

# --- CAPTURA PERSISTENTE DEL CLICK ---
if mapa_salida and mapa_salida.get("last_clicked"):
    st.session_state.click_lat = mapa_salida["last_clicked"]["lat"]
    st.session_state.click_lon = mapa_salida["last_clicked"]["lng"]

# Si hay coordenadas en memoria, evaluamos qué tipo de acción ejecutar
if st.session_state.click_lat is not None and st.session_state.click_lon is not None:
    lat_actual = st.session_state.click_lat
    lon_actual = st.session_state.click_lon

    # Verificar si el click está encima o extremadamente cerca de una alerta existente (tolerancia de rango táctil)
    alerta_coincidente = None
    if not alertas_activas.empty:
        for idx, fila_activa in alertas_activas.iterrows():
            if abs(fila_activa["Latitud"] - lat_actual) < 0.0007 and abs(fila_activa["Longitud"] - lon_actual) < 0.0007:
                alerta_coincidente = fila_activa
                break

    st.write("---")

    # CASO A: EL USUARIO TOCÓ UNA ALERTA EXISTENTE -> MENÚ PARA ELIMINAR / ARCHIVAR
    if alerta_coincidente is not None:
        st.markdown("### 🔄 Gestionar Emergencia Existente")
        st.info(f"📍 **Calle:** {alerta_coincidente.get('Lugar')}\n\n🕒 **Reportado a las:** {alerta_coincidente.get('Hora', 'Sin Registro')}\n\n📝 **Detalle:** {alerta_coincidente.get('Descripcion')}")
        
        with st.form("eliminar_emergencia_form", clear_on_submit=True):
            st.markdown("<p style='color: #ffcccc !important; font-weight: bold;'>¿Esta calle ya no se encuentra inundada y el tránsito volvió a la normalidad?</p>", unsafe_allow_html=True)
            boton_despejar = st.form_submit_button("✅ SÍ, LA CALLE YA NO ESTÁ INUNDADA (Mover a Historial)")

            if boton_despejar:
                try:
                    with st.spinner("Actualizando base de datos..."):
                        # Descargar todos los registros planos para encontrar el número de fila física en el Sheet
                        valores_crudos = sheet.get_all_values()
                        fila_a_modificar = None

                        for i, r in enumerate(valores_crudos[1:], start=2):
                            try:
                                r_lat = float(str(r[1]).replace(',', '.'))
                                r_lon = float(str(r[2]).replace(',', '.'))
                                # Validamos coincidencia exacta por posición y que siga "Inundado"
                                if abs(r_lat - alerta_coincidente["Latitud"]) < 1e-4 and abs(r_lon - alerta_coincidente["Longitud"]) < 1e-4 and r[4] == "Inundado":
                                    fila_a_modificar = i
                                    break
                            except:
                                continue

                        if fila_a_modificar:
                            # Columna E es la 5 (Estado). Cambiamos "Inundado" por "Historial"
                            sheet.update_cell(fila_a_modificar, 5, "Historial")
                            st.success("¡Perfecto! Alerta movida con éxito al historial de emergencias antiguas.")
                            
                            # Limpiar la memoria del click y refrescar
                            st.session_state.click_lat = None
                            st.session_state.click_lon = None
                            st.rerun()
                        else:
                            st.error("No se pudo enlazar el marcador con la fila correspondiente en la planilla.")
                except Exception as e:
                    st.error(f"Error al conectar con la base de datos: {e}")

    # CASO B: EL USUARIO TOCÓ UN LUGAR VACÍO -> FORMULARIO DE NUEVO REPORTE
    else:
        st.markdown("### 🚨 Confirmar y Enviar Alerta Nueva")
        with st.spinner("Localizando nombre de la vía..."):
            try:
                geolocator = Nominatim(user_agent="alerta_austral_bot")
                location = geolocator.reverse((lat_actual, lon_actual), timeout=3)
                calle_detectada = location.raw['address']['road'] if location and 'road' in location.raw['address'] else "Punto Registrado"
            except Exception:
                calle_detectada = "Punto Registrado"

        with st.form("registro_inundacion_db", clear_on_submit=True):
            st.info(f"📍 Coordenadas capturadas correctamente en la vía.")
            calle_final = st.text_input("Confirmar nombre de la calle:", value=calle_detectada)
            descripcion_incidente = st.text_input("Detalle del incidente:", value="Agua acumulada en calzada")

            boton_reportar = st.form_submit_button("🚨 REGISTRAR CALLE INUNDADA")

            if boton_reportar:
                # Capturamos el tiempo local en formato legible
                hora_reporte = datetime.now().strftime("%H:%M (%d/%m)")
                
                # REQUISITO DE COLUMNAS EN TU HOJA:
                # A: Lugar | B: Latitud | C: Longitud | D: Descripcion | E: Estado | F: Hora
                nueva_fila = [calle_final, str(lat_actual), str(lon_actual), descripcion_incidente, "Inundado", hora_reporte]
                
                try:
                    sheet.insert_row(nueva_fila, index=2)
                    st.success("¡Alerta registrada exitosamente en el sistema!")
                    
                    st.session_state.click_lat = None
                    st.session_state.click_lon = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Fallo al guardar en la base de datos: {e}")

# --- PANEL DE MONITOREO EN VIVO ---
st.write("---")
cantidad_alertas = len(alertas_activas) if not alertas_activas.empty else 0
st.markdown(f"### 📊 Emergencias Activas ({cantidad_alertas})")

if alertas_activas.empty:
    st.info("La base de datos no registra calles inundadas actualmente.")
else:
    for _, alerta in alertas_activas.iterrows():
        # Extracción segura de la hora con fallback si es un registro antiguo
        hora_display = alerta.get('Hora', '---') if pd.notna(alerta.get('Hora')) and alerta.get('Hora') != "" else "---"
        
        st.markdown(f"""
        <div class="danger-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <strong>⚠️ {alerta.get('Lugar', 'Alerta Registrada')}</strong>
                <span style="font-size: 0.85em; color: #aaaaaa !important; font-weight: bold; background-color: #333; padding: 2px 8px; border-radius: 5px;">🕒 {hora_display}</span>
            </div>
            <div style="margin-top: 5px;">
                <span style="font-size: 0.85em; color: #ffcccc !important;">{alerta.get('Descripcion', '')}</span><br>
                <span style="font-size: 0.8em; color: #aaa !important;">Coord: {alerta.get('Latitud', 0):.4f}, {alerta.get('Longitud', 0):.4f}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
