import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim

# --- CONFIGURACIÓN DE PÁGINA RESPONSIVA ---
st.set_page_config(page_title="🗺️ Alerta Móvil GSheets 📍", page_icon="🗺️", layout="centered")

# --- ENLACE A TU GOOGLE SHEET ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/11mPB_wV3ogbxgExGj5E7BI_L1uL3tzUxnwDh2NlHn4Q/edit"

# --- CSS: MODO OSCURO OPTIMIZADO PARA MÓVILES ---
st.markdown('''
    <style>
    .stApp { background-color: #1a1a1a; color: white !important; }
    h1, h2, h3, h4, h5, h6, p, div, span, label, li, small, strong { color: #FFFFFF !important; }
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

# --- INICIALIZACIÓN DEL CONECTOR ---
conn = st.connection("gsheets", type=GSheetsConnection)

# Inicializar un registro de errores en la sesión para diagnóstico técnico
if "historial_errores" not in st.session_state:
    st.session_state.historial_errores = ""

def cargar_datos():
    registro = []
    try:
        csv_url = SHEET_URL.replace("/edit", "/export?format=csv")
        return pd.read_csv(csv_url)
    except Exception as e_csv:
        registro.append(f"Fallo lectura directa CSV: {e_csv}")
        try:
            return conn.read(spreadsheet=SHEET_URL, worksheet="Hoja 1", ttl=0)
        except Exception as e_sheet1:
            registro.append(f"Fallo conexión Bot ('Hoja 1'): {e_sheet1}")
            try:
                return conn.read(spreadsheet=SHEET_URL, worksheet="Hoja1", ttl=0)
            except Exception as e_sheet2:
                registro.append(f"Fallo conexión Bot ('Hoja1'): {e_sheet2}")
                st.session_state.historial_errores = "\n".join(registro)
                return pd.DataFrame()

df = cargar_datos()

if df.empty:
    st.error("⚠️ Error de autenticación del Bot. Verifica tus Secrets en Streamlit Cloud y que la planilla esté compartida con el correo del bot.")
    if st.session_state.historial_errores:
        with st.expander("🛠️ Ver reporte técnico de la falla"):
            st.code(st.session_state.historial_errores, language="text")
else:
    df["Latitud"] = pd.to_numeric(df["Latitud"], errors='coerce')
    df["Longitud"] = pd.to_numeric(df["Longitud"], errors='coerce')
    df = df.dropna(subset=["Latitud", "Longitud"])

    puntos_base = df[df["Estado"].str.lower() != "inundado"]
    alertas_usuario = df[df["Estado"].str.lower() == "inundado"]

    lista_estaciones = puntos_base["Lugar"].unique().tolist()
    seleccion = st.selectbox("📍 Centrar mapa en estación:", ["Vista General"] + lista_estaciones)
    st.caption("📱 *Instrucción móvil: Toca cualquier calle en el mapa para reportar una inundación.*")

    if seleccion != "Vista General":
        fila_sel = puntos_base[puntos_base["Lugar"] == seleccion].iloc[0]
        centro_lat, centro_lon = float(fila_sel["Latitud"]), float(fila_sel["Longitud"])
        zoom_inicial = 15
    else:
        centro_lat, centro_lon = float(df["Latitud"].mean()), float(df["Longitud"].mean())
        zoom_inicial = 14

    mapa = folium.Map(location=[centro_lat, centro_lon], zoom_start=zoom_inicial, tiles="OpenStreetMap")

    for _, fila in puntos_base.iterrows():
        folium.Marker(
            location=[float(fila["Latitud"]), float(fila["Longitud"])],
            popup=folium.Popup(f"<b>Estación:</b> {fila['Lugar']}<br>{fila['Descripcion']}", max_width=200),
            tooltip=str(fila["Lugar"])
        ).add_to(mapa)

    for _, fila in alertas_usuario.iterrows():
        folium.Circle(
            location=[float(fila["Latitud"]), float(fila["Longitud"])],
            radius=50,
            color="#d9534f",
            fill=True,
            fill_color="#d9534f",
            fill_opacity=0.5,
            popup=folium.Popup(f"⚠️ <b>Calle Inundada:</b><br>{fila['Lugar']}<br><i>{fila['Descripcion']}</i>", max_width=200)
        ).add_to(mapa)

    mapa_salida = st_folium(mapa, width="100%", height=400, key="mapa_gsheets_movil")

    last_clicked = mapa_salida.get("last_clicked") if mapa_salida else None

    if last_clicked:
        click_lat = last_clicked["lat"]
        click_lon = last_clicked["lng"]

        with st.spinner("Bot analizando la calle..."):
            try:
                geolocator = Nominatim(user_agent="alerta_austral_geo")
                location = geolocator.reverse((click_lat, click_lon), timeout=3)
                calle_detectada = location.raw['address']['road'] if location and 'road' in location.raw['address'] else "Punto Registrado"
            except Exception:
                calle_detectada = "Punto Registrado"

        st.write("---")
        st.markdown("### 🚨 Confirmar Reporte de Emergencia")

        with st.form("registro_inundacion", clear_on_submit=True):
            st.info(f"📍 Calle detectada por el Bot: **{calle_detectada}**")
            calle_final = st.text_input("Confirmar nombre de la vía:", value=calle_detectada)
            descripcion_incidente = st.text_input("Detalle del incidente:", value="Agua acumulada en calzada")

            boton_reportar = st.form_submit_button("🚨 GUARDAR ALERTA EN GOOGLE SHEETS")

            if boton_reportar:
                nuevo_registro = pd.DataFrame([{
                    "Lugar": calle_final,
                    "Latitud": click_lat,
                    "Longitud": click_lon,
                    "Descripcion": descripcion_incidente,
                    "Estado": "Inundado"
                }])

                df_actualizado = pd.concat([df, nuevo_registro], ignore_index=True)
                
                with st.spinner("El Bot está escribiendo en Google Sheets..."):
                    try:
                        conn.update(spreadsheet=SHEET_URL, worksheet="Hoja 1", data=df_actualizado)
                    except Exception:
                        conn.update(spreadsheet=SHEET_URL, worksheet="Hoja1", data=df_actualizado)
                
                st.success("¡Datos guardados por el Bot en la nube con éxito!")
                st.rerun()

    st.write("---")
    st.markdown("### 📊 Emergencias Activas en la Base de Datos")

    if alertas_usuario.empty:
        st.info("No se registran calles inundadas guardadas en la planilla actualmente.")
    else:
        for _, fila in alertas_usuario.iterrows():
            st.markdown(f"""
            <div class="danger-card">
                <strong>⚠️ {fila['Lugar']}</strong><br>
                <span style="font-size: 0.85em; color: #ffcccc !important;">{fila['Descripcion']}</span><br>
                <span style="font-size: 0.8em; color: #aaa !important;">Coordenadas: {fila['Latitud']:.4f}, {fila['Longitud']:.4f}</span>
            </div>
            """, unsafe_allow_html=True)
