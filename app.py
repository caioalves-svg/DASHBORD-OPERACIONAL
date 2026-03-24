import streamlit as st
from datetime import datetime
from modules import data_loader, business_logic, ui_components

st.set_page_config(page_title="Dashboard Operacional v6", page_icon="🏆", layout="wide", initial_sidebar_state="expanded")
ui_components.load_css()

# Força sidebar sempre visível
st.markdown("""
    <style>
        [data-testid="collapsedControl"] { display: none; }
        section[data-testid="stSidebar"] { display: block !important; visibility: visible !important; }
    </style>
""", unsafe_allow_html=True)

try:
    df_raw = data_loader.get_raw_data()
except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
    st.stop()

# Processamento e Filtros
df_processed = business_logic.process_data(df_raw)
df_filtered, end_date = ui_components.render_sidebar_filters(df_processed)
df_metas = business_logic.calculate_meta_logic(df_filtered, end_date)

# Cálculos de KPI
total_bruto = df_filtered.shape[0]
total_liquido = df_filtered['Eh_Novo_Episodio'].sum()
taxa_duplicidade = ((total_bruto - total_liquido) / total_bruto * 100) if total_bruto > 0 else 0

meta_total_sac = df_metas['Meta_SAC'].sum()
meta_total_pend = df_metas['Meta_PEND'].sum()

if 'Setor' in df_filtered.columns:
    realizado_sac = df_filtered[df_filtered['Setor'].str.contains('SAC', case=False, na=False)]['Eh_Novo_Episodio'].sum()
    realizado_pend = df_filtered[df_filtered['Setor'].str.contains('Pend', case=False, na=False)]['Eh_Novo_Episodio'].sum()
else:
    realizado_sac = realizado_pend = 0

perc_sac = (realizado_sac / meta_total_sac * 100) if meta_total_sac > 0 else 0
perc_pend = (realizado_pend / meta_total_pend * 100) if meta_total_pend > 0 else 0
media_meta = (perc_sac + perc_pend) / 2

# --- RENDERIZAÇÃO DA INTERFACE ---
ui_components.render_header()
ui_components.render_kpi_cards(total_bruto, total_liquido, taxa_duplicidade, media_meta)
ui_components.render_gauges(perc_sac, perc_pend, realizado_sac, meta_total_sac, realizado_pend, meta_total_pend)

# Ranking / Pódio
ui_components.render_ranking_section(df_filtered)

# Gráficos Principais
ui_components.render_main_charts(df_filtered)

# Capacidade
ui_components.render_capacity_analysis(df_filtered)

# Mapa de Calor
ui_components.render_heatmap(df_filtered)
