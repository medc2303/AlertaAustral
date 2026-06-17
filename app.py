import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim

# --- CONFIGURACIÓN DE PÁGINA RESPONSIVA ---
st.set_page_config(page_title="🗺️ Alerta Móvil 📍", page_icon="🗺️", layout="centered")

# --- ENLACE A TU GOOGLE SHEET ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/11mPB_wV3ogbxgExGj5E7BI_L1uL3tzUxnwDh2NlHn4Q/edit"

# --- MEMORIA CACHÉ DE EMERGENCIAS ---
if "zonas_inundadas" not in st.session_state:
    st.session_state.zonas_inundadas = []

# --- CSS: OPTIMIZADO PARA PANTALLAS MÓVILES Y MODO OSCURO ---
st.markdown('''
    <style>
    /* Forzar diseño adaptable en móviles */
    .stApp {
        background-color: #1a1a1a; 
        color: white !important;
    }
    h1, h2, h3, h4, h5, h6, p, div, span, label, li, small, strong {
        color: #FFFFFF !important;
    }
    
    /* Inputs más grandes para pantallas táctiles */
    .stTextInput input {
        background-color: #333333 !important; 
        color: white !important;
        border: 1px solid #555 !important;
        padding: 12px !important;
        font-size: 16px !important;
    }

    /* Selectores táctiles */
    div[data-baseweb="select"] > div {
        background-color: #333333 !important;
        color: white !important;
        border-color: #555 !important;
        min-height: 45px !important;
    }
    div[data-baseweb="select"] span { color: white !important; }
    div[data-baseweb="select"] svg { fill: white !important; }
    div[data-baseweb="popover"], div[data-baseweb="menu"], ul { background-color: #222222 !important; }
    li[id^="bui-"] { color: white !important; padding: 12px !important; }
    
    /* Botón gigante para el pulgar */
    .stButton button {
        background-color: #d9534f !important;
        color: white !important;
        border: 1px solid white !important;
        width: 100% !important;
        padding: 15px !important;
        font-size: 18px !important;
        font-weight: bold !important;
        border-radius: 8px !important;
    }
    
    .status-card, .danger-card {
        background-color: #2b2b2b !important;
        border: 1px solid #444;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 12px;
        color: white !important;
    }
    .status-card { border-left: 5px solid #1D6F42; }
    .danger-card { border-left: 5px solid #d9534f; }
    
    .main-header {
        font-family: 'Helvetica Neue', sans-serif; 
        color: #FFFFFF !important; 
        text-align: center; 
        font-size: 2.2em; 
        font-weight: bold;
        text-shadow: 2px 2px 4px #000000;
        padding-bottom: 10px;
        margin-bottom: 15px;
        border-bottom: 2px dashed #FFFFFF;
    }
    </style>
    <div class="main-header">🚨 Alerta Vial Puerto Montt 📱</div>
    ''', unsafe_allow_html=True)

# --- CARGA DE DATOS ---
def cargar_datos():
    try:
        csv_url = SHEET_URL.replace("/edit", "/export?format=csv")
        return pd.read_csv(csv_url)
    except Exception:
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            return conn.read(spreadsheet=SHEET_URL, ttl=0)
        except Exception:
            return pd.DataFrame()

df = cargar_datos()

if df.empty:
    st.error("⚠️ Error de conexión con la base de datos.")
else:
    col_lat = next((c for c in df.columns if 'lat' in c.lower()), None)
    col_lon = next((c for c in df.columns if 'lon' in c.lower() or 'lng' in c.lower()), None)
    col_name = next((c for c in df.columns if any(k in c.lower() for k in ['nom', 'lug', 'sens', 'id', 'part'])), df.columns[0])

    if col_lat and col_lon:
        df[col_lat] = pd.to_numeric(df[col_lat], errors='coerce')
        df[col_lon] = pd.to_numeric(df[col_lon], errors='coerce')
        df = df.dropna(subset=[col_lat, col_lon])
        
        lista_lugares = df[col_name].unique().tolist()

        # Selector enfocado a UX móvil
        seleccion = st.selectbox("📍 Centrar mapa en estación:", ["Vista General"] + lista_lugares)
        st.caption("📱 *Instrucción: Toca cualquier calle en el mapa para reportar inundación.*")

        if seleccion != "Vista General" and not df[df[col_name] == seleccion].empty:
            fila_sel = df[df[col_name] == seleccion].iloc[0]
            centro_lat, centro_lon = float(fila_sel[col_lat]), float(fila_sel[col_lon])
            zoom_inicial = 15
        else:
            centro_lat, centro_lon = float(df[col_lat].mean()), float(df[col_lon].mean())
            zoom_inicial = 14

        # Construcción del mapa
        mapa = folium.Map(location=[centro_lat, centro_lon], zoom_start=zoom_inicial, tiles="OpenStreetMap")
        
        # Marcadores Base
        for _, fila in df.iterrows():
            folium.Marker(
                location=[float(fila[col_lat]), float(fila[col_lon])],
                tooltip=str(fila[col_name])
            ).add_to(mapa)
        
        # Dibujar áreas rojas translúcidas en las calles inundadas
        for zona in st.session_state.zonas_inundadas:
            folium.Circle(
                location=[zona["lat"], zona["lon"]],
                radius=50,  # Metros de cobertura sobre la calle
                color="#d9534f",
                fill=True,
                fill_color="#d9534f",
                fill_opacity=0.5,
                popup=folium.Popup(f"⚠️ <b>Calle Inundada:</b><br>{zona['calle']}", max_width=200)
            ).add_to(mapa)
        
        # --- RENDERIZADO AJUSTADO A ANCHO MÓVIL (100%) ---
        mapa_salida = st_folium(mapa, width="100%", height=400, key="mapa_movil")

        # Captura del toque táctil en el celular
        last_clicked = mapa_salida.get("last_clicked") if mapa_salida else None
        
        if last_clicked:
            click_lat = last_clicked["lat"]
            click_lon = last_clicked["lng"]
            
            # --- ALGORITMO DE DETECCIÓN AUTOMÁTICA DE CALLE (Geocoding) ---
            with st.spinner("Detectando nombre de la calle..."):
                try:
                    geolocator = Nominatim(user_agent="alerta_austral_mobile")
                    location = geolocator.reverse((click_lat, click_lon), timeout=3)
                    if location and 'road' in location.raw['address']:
                        calle_detectada = location.raw['address']['road']
                    elif location:
                        calle_detectada = location.address.split(",")[0]
                    else:
                        calle_detectada = "Calle desconocida"
                except Exception:
                    calle_detectada = "Punto seleccionado"

            st.write("---")
            st.markdown("### 🚨 Confirmar Reporte de Inundación")
            
            # Formulario optimizado para enviar con un solo toque
            with st.form("registro_inundacion", clear_on_submit=True):
                st.info(f"📍 Calle detectada: **{calle_detectada}**")
                
                # Queda el campo por si el usuario móvil quiere refinar el nombre de la calle
                calle_final = st.text_input("Confirmar o editar nombre de la vía:", value=calle_detectada)
                
                boton_reportar = st.form_submit_button("🚨 REGISTRAR CALLE INUNDADA")
                
                if boton_reportar:
                    st.session_state.zonas_inundadas.append({
                        "lat": click_lat,
                        "lon": click_lon,
                        "calle": calle_final
                    })
                    st.success("¡Alerta registrada con éxito!")
                    st.rerun()

        # --- SECCIÓN INFERIOR COMPACTA PARA MÓVILES ---
        st.write("---")
        st.markdown("### 📊 Emergencias Activas")
        
        if not st.session_state.zonas_inundadas:
            st.info("No hay reportes de calles inundadas en este sector.")
        else:
            for zona in st.session_state.zonas_inundadas:
                st.markdown(f"""
                <div class="danger-card">
                    <strong>⚠️ {zona['calle']}</strong><br>
                    <span style="font-size: 0.8em; color: #ffcccc !important;">Inundación detectada vía celular</span>
                </div>
                """, unsafe_allow_html=True)
            
    else:
        st.error("❌ Error en las columnas de la planilla.")
