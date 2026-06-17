import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import folium
from streamlit_folium import st_folium

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="🗺️ Mapa Interactivo 📍", page_icon="🗺️", layout="centered")

# --- ENLACE A TU GOOGLE SHEET ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/11mPB_wV3ogbxgExGj5E7BI_L1uL3tzUxnwDh2NlHn4Q/edit"

# --- CSS: MODO OSCURO FORZADO ---
st.markdown('''
    <style>
    /* 1. FORZAR FONDO Y TEXTO GLOBAL */
    .stApp {
        background-color: #1a1a1a; 
        color: white !important;
    }
    
    /* 2. FORZAR TODOS LOS TEXTOS A BLANCO */
    h1, h2, h3, h4, h5, h6, p, div, span, label, li, small, strong {
        color: #FFFFFF !important;
    }
    
    /* 3. INPUTS Y TEXTAREAS */
    .stTextInput input, .stTextArea textarea {
        background-color: #333333 !important; 
        color: white !important;
        border: 1px solid #555 !important;
    }

    /* 4. SELECTBOX (Menú desplegable) */
    div[data-baseweb="select"] > div {
        background-color: #333333 !important;
        color: white !important;
        border-color: #555 !important;
    }
    div[data-baseweb="select"] span {
        color: white !important;
    }
    div[data-baseweb="select"] svg {
        fill: white !important;
    }
    
    /* EL MENÚ DESPLEGABLE FLOTANTE */
    div[data-baseweb="popover"], div[data-baseweb="menu"], ul {
        background-color: #222222 !important;
    }
    li[id^="bui-"] {
        color: white !important; 
    }
    li[aria-selected="false"]:hover {
        background-color: #444444 !important;
    }
    
    /* 5. TARJETAS PERSONALIZADAS */
    .status-card {
        background-color: #2b2b2b !important;
        border: 1px solid #444;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        border-left: 5px solid #1D6F42;
        color: white !important;
    }
    
    /* CABECERA */
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
        # Asegurar casteo numérico limpio
        df[col_lat] = pd.to_numeric(df[col_lat], errors='coerce')
        df[col_lon] = pd.to_numeric(df[col_lon], errors='coerce')
        df = df.dropna(subset=[col_lat, col_lon])
        
        lista_lugares = df[col_name].unique().tolist()

        # Selector en el entorno nativo oscuro de la app
        st.markdown("<h3 style='text-align: center;'>🔍 Selector de Ubicación</h3>", unsafe_allow_html=True)
        seleccion = st.selectbox("👇 Elige un punto específico para centrar el mapa:", ["Mostrar vista general"] + lista_lugares)
        st.write("")

        # Determinar coordenadas de centrado válidas
        if seleccion != "Mostrar vista general" and not df[df[col_name] == seleccion].empty:
            fila_sel = df[df[col_name] == seleccion].iloc[0]
            centro_lat = float(fila_sel[col_lat])
            centro_lon = float(fila_sel[col_lon])
            zoom_inicial = 13
        else:
            centro_lat = float(df[col_lat].mean())
            centro_lon = float(df[col_lon].mean())
            zoom_inicial = 4  # Escala amplia para abarcar los puntos de prueba

        # Crear mapa base de Folium de forma segura fuera de bloques HTML inyectados
        mapa = folium.Map(
            location=[centro_lat, centro_lon], 
            zoom_start=zoom_inicial,
            tiles="OpenStreetMap",
            control_scale=True
        )
        
        # Marcadores dinámicos
        for _, fila in df.iterrows():
            popup_info = "".join([f"<b>{col}:</b> {fila[col]}<br>" for col in df.columns if col not in [col_lat, col_lon]])
            
            folium.Marker(
                location=[float(fila[col_lat]), float(fila[col_lon])],
                popup=folium.Popup(popup_info, max_width=280),
                tooltip=str(fila[col_name])
            ).add_to(mapa)
        
        # Renderizar mapa interactivo de forma nativa
        st_folium(mapa, width=700, height=480, returned_objects=[])

        # --- SECCIÓN INFERIOR: TARJETAS ---
        st.write("---")
        st.subheader("📊 Puntos Registrados")
        
        col1, col2, col3 = st.columns(3)
        listado_columnas = [col1, col2, col3]
        
        for i, (_, fila) in enumerate(df.iterrows()):
            c = listado_columnas[i % 3]
            c.markdown(f"""
            <div class="status-card">
                <strong>{fila[col_name]}</strong><br>
                <span style="font-size: 0.85em; color: #ccc !important;">Coordenadas: {fila[col_lat]}, {fila[col_lon]}</span>
            </div>
            """, unsafe_allow_html=True)
            
    else:
        st.error(f"❌ Error de esquema: No se encontraron las columnas de coordenadas. Columnas en tu archivo: {list(df.columns)}")
