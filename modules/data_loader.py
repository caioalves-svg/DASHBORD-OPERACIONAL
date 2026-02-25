import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

@st.cache_data(ttl=600)
def get_raw_data():
    """Conecta ao Google Sheets e retorna o DataFrame bruto."""
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df = conn.read(worksheet="Página1")
    except:
        df = conn.read()
    return df
