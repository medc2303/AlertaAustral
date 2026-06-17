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
st.markdown("""
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

    /* 6. BOTONES */
    .stButton button {
        background-color: #1D6F42 !important;
        color: white !important;
        border: 1px solid white !important;
    }
    
    /* CABECERA */
    .main-header {
