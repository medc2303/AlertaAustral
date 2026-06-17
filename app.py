import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import folium
from streamlit_folium import st_folium

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="🗺️ Mapa Interactivo 📍", page_icon="🗺️", layout="centered")

# --- ENLACE A TU GOOGLE SHEET ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/11mPB_wV3ogbxgExGj5E7BI_L1uL3tzUxnwDh2NlHn4Q/edit"

# --- INICIALIZACIÓN DEL ESTADO DE MEMORIA (Caché de calles inundadas) ---
if "zonas_inundadas" not in st.session_state:
    st.session_state.zonas_inundadas = []

# --- CSS: MODO OSCURO FORZADO ---
st.markdown('''
    <style>
    .stApp {
        background-color: #1a1a1a; 
        color: white !important;
    }
    h1, h2, h3, h4, h5, h6, p, div, span, label, li, small, strong {
        color: #FFFFFF !important;
    }
    .stTextInput input, .stTextArea textarea {
        background-color: #333333 !important; 
        color: white !important;
        border: 1px solid #555 !important;
    }
    div[data-baseweb="select"] > div {
        background-color: #333333 !important;
        color: white !important;
        border-color: #555 !important;
    }
    div[data-baseweb="select"] span { color: white !important; }
    div[data-baseweb="select"] svg { fill: white !important; }
    div[data-baseweb="popover"], div[data-baseweb="menu"], ul { background-color: #222222 !important; }
    li[id^="bui-"] { color: white !important; }
    li[aria-selected="false"]:hover { background-color: #444444 !important; }
    
    .status-card {
        background-color: #2b2b2b !important;
        border: 1px solid #444;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        border-left: 5px solid #1D6F42;
        color: white !important;
    }
    .danger-card {
        background-color: #2b2b2b !important;
        border: 1px solid #444;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        border-left: 5px solid #d9534f;
        color: white !important;
    }
    .main-header {
        font-family: 'Helvetica Neue', sans-serif; 
        color: #FFFFFF !important; 
        text-align: center; 
        font-size: 3em; 
        font-weight: bold;
        text-shadow: 2px 2px 4px #000000;
        padding-bottom: 20px;
        margin-bottom: 20px;
        border-bottom: 2px dashed #FFFFFF;
    }
    </style>
    <div class="main-header">🗺️ Monitoreo Geográfico Interactivo 📍</div>
    ''', unsafe_allow_html=True)

# --- FUNCIÓN DE CARGA INTELIGENTE ---
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
    st.error("⚠️ No se pudieron recuperar los datos. Asegúrate de que la hoja de cálculo de Google esté configurada con acceso general como 'Cualquier persona con el enlace' en modo Lector.")
else:
    # --- DETECCIÓN AUTOMÁTICA DE COLUMNAS ---
    col_lat = next((c for c in df.columns if 'lat' in c.lower()), None)
    col_lon = next((c for c in df.columns if 'lon' in c.lower() or 'lng' in c.lower()), None)
    col_name = next((c for c in df.columns if any(k in c.lower() for k in ['nom', 'lug', 'sens', 'id', 'part'])), df.columns[0])

    if col_lat and col_lon:
        df[col_lat] = pd.to_numeric(df[col_lat], errors='coerce')
        df[col_lon] = pd.to_numeric(df[col_lon], errors='coerce')
        df = df.dropna(subset=[col_lat, col_lon])
        
        lista_lugares = df[col_name].unique().tolist()

        st.markdown("<h3 style='text-align: center;'>🔍 Selector de Ubicación</h3>", unsafe_allow_html=True)
        seleccion = st.selectbox("👇 Elige un punto específico para centrar el mapa:", ["Mostrar vista general"] + lista_lugares)
        st.caption("💡 *Tip informático: Haz clic directo en cualquier parte del mapa para reportar una calle inundada.*")
        st.write("")

        # Determinar coordenadas de centrado
        if seleccion != "Mostrar vista general" and not df[df[col_name] == seleccion].empty:
            fila_sel = df[df[col_name] == seleccion].iloc[0]
            centro_lat, centro_lon = float(fila_sel[col_lat]), float(fila_sel[col_lon])
            zoom_inicial = 14
        else:
            centro_lat, centro_lon = float(df[col_lat].mean()), float(df[col_lon].mean())
            zoom_inicial = 13

        # Inicializar mapa base
        mapa = folium.Map(location=[centro_lat, centro_lon], zoom_start=zoom_inicial, tiles="OpenStreetMap")
        
        # 1. Renderizar puntos base de Google Sheets
        for _, fila in df.iterrows():
            popup_info = "".join([f"<b>{col}:</b> {fila[col]}<br>" for col in df.columns if col not in [col_lat, col_lon]])
            folium.Marker(
                location=[float(fila[col_lat]), float(fila[col_lon])],
                popup=folium.Popup(popup_info, max_width=280),
                tooltip=str(fila[col_name])
            ).add_to(mapa)
        
        # 2. Renderizar capas poligonales/circulares de Alerta (Calles Inundadas)
        for zona in st.session_state.zonas_inundadas:
            folium.Circle(
                location=[zona["lat"], zona["lon"]],
                radius=60,  # Radio de cobertura en metros para simular el área de la calle
                color="#d9534f",
                fill=True,
                fill_color="#d9534f",
                fill_opacity=0.45,
                popup=folium.Popup(f"⚠️ <b>ZONA INUNDADA:</b><br>{zona['calle']}", max_width=200)
            ).add_to(mapa)
        
        # Renderizar el mapa capturando la salida de eventos
        # Es fundamental definir un 'key' fijo para preservar el estado del iframe
        mapa_salida = st_folium(mapa, width=700, height=480, key="mapa_monitoreo")

        # --- LÓGICA DE CAPTURA DE EVENTO CLICK ---
        last_clicked = mapa_salida.get("last_clicked") if mapa_salida else None
        
        if last_clicked:
            click_lat = last_clicked["lat"]
            click_lon = last_clicked["lng"]
            
            st.write("---")
            st.markdown("### 🚨 Reportar Emergencia Vial")
            
            # Usamos un formulario para controlar el buffer del rerun y evitar falsos positivos
            with st.form("registro_inundacion", clear_on_submit=True):
                st.markdown(f"📍 **Coordenadas seleccionadas:** `{click_lat:.5f}, {click_lon:.5f}`")
                nombre_calle = st.text_input("Nombre de la calle o punto de referencia afectado:", placeholder="Ej: Av. Angelmó esquina Miraflores")
                boton_reportar = st.form_submit_button("🚨 Declarar Área Inundada / Peligro")
                
                if boton_reportar:
                    if nombre_calle.strip() == "":
                        st.error("Por favor, ingresa una referencia o calle antes de guardar.")
                    else:
                        # Append al estado de la aplicación
                        st.session_state.zonas_inundadas.append({
                            "lat": click_lat,
                            "lon": click_lon,
                            "calle": nombre_calle
                        })
                        st.success(f"Alerta registrada para {nombre_calle}. Actualizando capas espaciales...")
                        time_sleep = 0.5
                        st.rerun()

        # --- SECCIÓN INFERIOR: TARJETAS DE ESTADO Y ALERTA ---
        st.write("---")
        st.subheader("📊 Panel de Estado e Incidencias Críticas")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 🟢 Puntos de Monitoreo Base")
            for _, fila in df.iterrows():
                st.markdown(f"""
                <div class="status-card">
                    <strong>{fila[col_name]}</strong><br>
                    <span style="font-size: 0.85em; color: #ccc !important;">{fila.get('Descripcion', 'Estación activa')}</span>
                </div>
                """, unsafe_allow_html=True)
                
        with col2:
            st.markdown("#### 🔴 Alertas de Inundación Activas")
            if not st.session_state.zonas_inundadas:
                st.info("No se registran calles inundadas en este cuadrante actualmente.")
            else:
                for zona in st.session_state.zonas_inundadas:
                    st.markdown(f"""
                    <div class="danger-card">
                        <strong>⚠️ {zona['calle']}</strong><br>
                        <span style="font-size: 0.85em; color: #ff9999 !important;">Área de Peligro (Radio: 60m)</span>
                    </div>
                    """, unsafe_allow_html=True)
            
    else:
        st.error(f"❌ Error de esquema: No se encontraron las columnas de coordenadas. Columnas en tu archivo: {list(df.columns)}")
