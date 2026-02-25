import streamlit as st
from datetime import datetime
from modules import data_loader, business_logic, ui_components

st.set_page_config(page_title="Dashboard Operacional", page_icon="🚛", layout="wide", initial_sidebar_state="expanded")

ui_components.load_css()

with st.sidebar:
    st.markdown("### 🚛 Painel de Controle")
    if st.button("🔄 Atualizar Dados", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

try:
    df_raw = data_loader.get_raw_data()
except Exception as e:
    st.error(f"Erro: {e}")
    st.stop()

df_processed = business_logic.process_data(df_raw)
df_filtered, end_date = ui_components.render_sidebar_filters(df_processed)
df_metas = business_logic.calculate_meta_logic(df_filtered, end_date)

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

# --- VISUALIZAÇÃO ---
ui_components.render_header()

c1, c2, c3, c4 = st.columns(4)
with c1: st.metric("Total Registros", f"{total_bruto}")
with c2: st.metric("Atendimentos Reais", f"{total_liquido}", "Produtividade")
with c3: st.metric("Taxa Duplicidade", f"{taxa_duplicidade:.1f}%", "-Alvo <15%", delta_color="inverse")
with c4:
    media_meta = (perc_sac + perc_pend) / 2
    st.metric("Meta Global", f"{media_meta:.1f}%", "Média Setores")

st.markdown("<br>", unsafe_allow_html=True)

col_main_1, col_main_2 = st.columns([2, 1])
with col_main_1:
    ui_components.render_main_bar_chart(df_filtered)
with col_main_2:
    ui_components.render_gauges(perc_sac, perc_pend)

ui_components.render_capacity_scatter(df_filtered)

col_ev1, col_ev2 = st.columns(2)
with col_ev1:
    ui_components.render_evolution_chart(df_filtered)
with col_ev2:
    ui_components.render_heatmap_clean(df_filtered)
