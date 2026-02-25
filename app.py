import streamlit as st
from datetime import datetime
from modules import data_loader, business_logic, ui_components

# Configuração Full Width
st.set_page_config(page_title="Dashboard Operacional", page_icon="🚛", layout="wide", initial_sidebar_state="expanded")

# Carrega Estilos
ui_components.load_css()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### 🚛 Painel de Controle")
    if st.button("🔄 Atualizar Dados", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# --- DATA LAYER ---
try:
    df_raw = data_loader.get_raw_data()
except Exception as e:
    st.error(f"Erro ao conectar: {e}")
    st.stop()

# --- BUSINESS LAYER ---
df_processed = business_logic.process_data(df_raw)
df_filtered, end_date = ui_components.render_sidebar_filters(df_processed)
df_metas = business_logic.calculate_meta_logic(df_filtered, end_date)

# --- CÁLCULOS KPI RAPIDOS ---
total_bruto = df_filtered.shape[0]
total_liquido = df_filtered['Eh_Novo_Episodio'].sum()
taxa_duplicidade = ((total_bruto - total_liquido) / total_bruto * 100) if total_bruto > 0 else 0

# --- CÁLCULOS DE META ---
meta_total_sac = df_metas['Meta_SAC'].sum()
meta_total_pend = df_metas['Meta_PEND'].sum()

realizado_sac = 0; realizado_pend = 0
if 'Setor' in df_filtered.columns:
    realizado_sac = df_filtered[df_filtered['Setor'].str.contains('SAC', case=False, na=False)]['Eh_Novo_Episodio'].sum()
    realizado_pend = df_filtered[df_filtered['Setor'].str.contains('Pend', case=False, na=False)]['Eh_Novo_Episodio'].sum()

perc_sac = (realizado_sac / meta_total_sac * 100) if meta_total_sac > 0 else 0
perc_pend = (realizado_pend / meta_total_pend * 100) if meta_total_pend > 0 else 0

# ==============================================================================
# LAYOUT DO DASHBOARD (GRID SYSTEM)
# ==============================================================================

# 1. Header Visual
ui_components.render_header()

# 2. Linha de KPIs (Cards Flutuantes)
c1, c2, c3, c4 = st.columns(4)
with c1: ui_components.kpi_card_new("Total Registros", f"{total_bruto}", icon="📦")
with c2: ui_components.kpi_card_new("Atendimentos Reais", f"{total_liquido}", delta="Produtividade", delta_type="positive", icon="✅")
with c3: 
    cor_dup = "positive" if taxa_duplicidade < 15 else "negative"
    ui_components.kpi_card_new("Taxa Duplicidade", f"{taxa_duplicidade:.1f}%", delta="Alvo: <15%", delta_type=cor_dup, icon="♻️")
with c4:
    # Card Resumo das Metas
    media_meta = (perc_sac + perc_pend) / 2
    cor_meta = "positive" if media_meta >= 100 else "neutral"
    ui_components.kpi_card_new("Meta Global", f"{media_meta:.1f}%", delta="Média Setores", delta_type=cor_meta, icon="🎯")

st.markdown("<br>", unsafe_allow_html=True)

# 3. Bloco Principal: Gráfico de Barras + Gauges de Meta
col_main_1, col_main_2 = st.columns([2, 1])

with col_main_1:
    st.markdown("### 📊 Performance Individual")
    ui_components.render_main_bar_chart(df_filtered)

with col_main_2:
    st.markdown("### 🎯 Acompanhamento de Metas")
    # Container visual para os gauges
    with st.container():
        st.markdown("<div style='background:white; padding:15px; border-radius:12px; border:1px solid #e5e7eb;'>", unsafe_allow_html=True)
        ui_components.render_gauges(perc_sac, perc_pend)
        st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# 4. Bloco Secundário: Capacidade (Largo)
st.markdown("### ⚡ Capacidade vs Realizado (TMA)")
with st.container():
    st.markdown("<div style='background:white; padding:15px; border-radius:12px; border:1px solid #e5e7eb;'>", unsafe_allow_html=True)
    ui_components.render_capacity_scatter(df_filtered)
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# 5. Bloco Terciário: Evolução e Heatmap (Lado a Lado)
col_ev1, col_ev2 = st.columns(2)

with col_ev1:
    # Gráfico de Evolução (Novo!)
    st.markdown("<div style='background:white; padding:20px; border-radius:12px; border:1px solid #e5e7eb; height:100%;'>", unsafe_allow_html=True)
    ui_components.render_evolution_chart(df_filtered)
    st.markdown("</div>", unsafe_allow_html=True)

with col_ev2:
    # Heatmap
    st.markdown("<div style='background:white; padding:20px; border-radius:12px; border:1px solid #e5e7eb; height:100%;'>", unsafe_allow_html=True)
    ui_components.render_heatmap_clean(df_filtered)
    st.markdown("</div>", unsafe_allow_html=True)
