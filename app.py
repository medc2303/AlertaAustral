import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim

# --- CONFIGURACIÓN DE PÁGINA RESPONSIVA ---
st.set_page_config(page_title="🗺️ Alerta Vial Puerto Montt 📍", page_icon="🗺️", layout="centered")

# Enlace público de tu Google Sheet (Modo Lector para cualquier persona con el enlace)
SHEET_URL = "https://docs.google.com/spreadsheets/d/11mPB_wV3ogbxgExGj5E7BI_L1uL3tzUxnwDh2NlHn4Q/edit"

# --- INICIALIZACIÓN DE MEMORIA VOLÁTIL (Caché local de incidencias) ---
if "zonas_inundadas" not in st.session_state:
    st.session_state.zonas_inundadas = []

# --- CSS: MAQUETACIÓN MODO OSCURO PARA CELULARES ---
st.markdown('''
    <style>
    .stApp { background-color: #1a1a1a; color: white !important; }
    h1, h2, h3, h4, h5, h6, p, div, span, label, li, small, strong { color: #FFFFFF !important; }
    
    /* Inputs adaptados para pulsación táctil móvil */
    .stTextInput input {
        background-color: #333333 !important; 
        color: white !important; 
        border: 1px solid #555 !important;
        padding: 12px !important;
        font-size: 16px !important;
    }
    
    div[data-baseweb="select"] > div {
        background-color: #333333 !important; color: white !important; border-color: #555 !important; min-height: 45px !important;
    }
    div[data-baseweb="select"] span { color: white !important; }
    div[data-baseweb="select"] svg { fill: white !important; }
    div[data-baseweb="popover"], div[data-baseweb="menu"], ul { background-color: #222222 !important; }
    li[id^="bui-"] { color: white !important; padding: 12px !important; }
    
    /* Botón gigante diseñado para uso con el pulgar */
    .stButton button {
        background-color: #d9534f !important; color: white !important; border: 1px solid white !important;
        width: 100% !important; padding: 15px !important; font-size: 18px !important; font-weight: bold !important; border-radius: 8px !important;
    }
    
    .status-card, .danger-card {
        background-color: #2b2b2b !important; border: 1px solid #444; padding: 15px; border-radius: 10px; margin-bottom: 12px; color: white !important;
    }
    .status-card { border-left: 5px solid #1D6F42; }
    .danger-card { border-left: 5px solid #d9534f; }
    
    .main-header {
        font-family: 'Helvetica Neue', sans-serif; color: #FFFFFF !important; text-align: center; font-size: 2.2em; font-weight: bold; text-shadow: 2px 2px 4px #000000; padding-bottom: 10px; margin-bottom: 15px; border-bottom: 2px dashed #FFFFFF;
    }
    </style>
    <div class="main-header">🚨 Alerta Vial Puerto Montt 📱</div>
    ''', unsafe_allow_html=True)

# --- CARGA DE DATOS POR BYPASS CSV PÚBLICO (Inmune a fallos de API) ---
def cargar_datos_base():
    try:
        # Forzamos la descarga del dataset crudo mapeando el endpoint de exportación
        csv_url = SHEET_URL.replace("/edit", "/export?format=csv")
        return pd.read_csv(csv_url)
    except Exception as e:
        st.error(f"Error al conectar con el dataset público de Google: {e}")
        return pd.DataFrame()

df = cargar_datos_base()

if df.empty:
    st.error("⚠️ No se pudieron recuperar los puntos geográficos base de la planilla.")
else:
    # Sanitización y casteo de tipos para la API de Folium
    df["Latitud"] = pd.to_numeric(df["Latitud"], errors='coerce')
    df["Longitud"] = pd.to_numeric(df["Longitud"], errors='coerce')
    df = df.dropna(subset=["Latitud", "Longitud"])

    puntos_base = df[df["Estado"].str.lower() != "inundado"]

    # Selector de ubicación móvil
    lista_estaciones = puntos_base["Lugar"].unique().tolist()
    seleccion = st.selectbox("📍 Centrar mapa en estación:", ["Vista General"] + lista_estaciones)
    st.caption("📱 *Instrucción móvil: Toca cualquier calle en el mapa para reportar una inundación en tiempo real.*")

    if seleccion != "Vista General":
        fila_sel = puntos_base[puntos_base["Lugar"] == seleccion].iloc[0]
        centro_lat, centro_lon = float(fila_sel["Latitud"]), float(fila_sel["Longitud"])
        zoom_inicial = 15
    else:
        centro_lat, centro_lon = float(df["Latitud"].mean()), float(df["Longitud"].mean())
        zoom_inicial = 14

    # Instanciar el mapa base
    mapa = folium.Map(location=[centro_lat, centro_lon], zoom_start=zoom_inicial, tiles="OpenStreetMap")

    # 1. Pintar marcadores de las estaciones fijas (Datos de GSheets)
    for _, fila in puntos_base.iterrows():
        folium.Marker(
            location=[float(fila["Latitud"]), float(fila["Longitud"])],
            popup=folium.Popup(f"<b>Estación:</b> {fila['Lugar']}<br>{fila['Descripcion']}", max_width=200),
            tooltip=str(fila["Lugar"])
        ).add_to(mapa)

    # 2. Pintar áreas circulares rojas translúcidas guardadas localmente en memoria
    for zona in st.session_state.zonas_inundadas:
        folium.Circle(
            location=[zona["lat"], zona["lon"]],
            radius=50,  # Radio de cobertura perimetral en metros sobre la calle
            color="#d9534f",
            fill=True,
            fill_color="#d9534f",
            fill_opacity=0.5,
            popup=folium.Popup(f"⚠️ <b>Calle Inundada:</b><br>{zona['lugar']}<br><i>{zona['descripcion']}</i>", max_width=200)
        ).add_to(mapa)

    # Renderizado adaptable al 100% de la pantalla del dispositivo móvil
    mapa_salida = st_folium(mapa, width="100%", height=400, key="mapa_memoria_movil")

    # Capturar coordenadas del evento táctil del celular
    last_clicked = mapa_salida.get("last_clicked") if mapa_salida else None

    if last_clicked:
        click_lat = last_clicked["lat"]
        click_lon = last_clicked["lng"]

        # Algoritmo de geocodificación inversa para evitar el tipeo manual en celulares
        with st.spinner("Localizando nombre de la vía..."):
            try:
                geolocator = Nominatim(user_agent="alerta_austral_bypass_v1")
                location = geolocator.reverse((click_lat, click_lon), timeout=3)
                calle_detectada = location.raw['address']['road'] if location and 'road' in location.raw['address'] else "Punto Registrado"
            except Exception:
                calle_detectada = "Punto Registrado"

        st.write("---")
        st.markdown("### 🚨 Confirmar Reporte de Emergencia")

        with st.form("registro_inundacion", clear_on_submit=True):
            st.info(f"📍 Calle detectada: **{calle_detectada}**")
            calle_final = st.text_input("Confirmar nombre de la vía:", value=calle_detectada)
            descripcion_incidente = st.text_input("Detalle del incidente:", value="Agua acumulada en calzada")

            boton_reportar = st.form_submit_button("🚨 REGISTRAR CALLE INUNDADA (TEMPORAL)")

            if boton_reportar:
                # Almacenar de forma atómica en la estructura del session_state local
                st.session_state.zonas_inundadas.append({
                    "lugar": calle_final,
                    "lat": click_lat,
                    "lon": click_lon,
                    "descripcion": descripcion_incidente
                })
                st.success("¡Alerta de inundación registrada localmente con éxito!")
                st.rerun()

    # --- PANEL INFERIOR DE MONITOREO ---
    st.write("---")
    st.markdown("### 📊 Emergencias Activas (Sesión Actual)")

    if not st.session_state.zonas_inundadas:
        st.info("No se registran calles inundadas en esta sesión actualmente.")
    else:
        for zona in st.session_state.zonas_inundadas:
            st.markdown(f"""
            <div class="danger-card">
                <strong>⚠️ {zona['lugar']}</strong><br>
                <span style="font-size: 0.85em; color: #ffcccc !important;">{zona['descripcion']}</span><br>
                <span style="font-size: 0.8em; color: #aaa !important;">Coordenadas: {zona['lat']:.4f}, {zona['lon']:.4f}</span>
            </div>
            """, unsafe_allow_html=True)
