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
    st.error(f"Erro ao conectar: {e}")
    st.stop()

df_processed = business_logic.process_data(df_raw)
df_filtered, end_date = ui_components.render_sidebar_filters(df_processed)
df_metas = business_logic.calculate_meta_logic(df_filtered, end_date)

total_bruto = df_filtered.shape[0]
total_liquido = df_filtered['Eh_Novo_Episodio'].sum()
taxa_duplicidade = ((total_bruto - total_liquido) / total_bruto * 100) if total_bruto > 0 else 0

meta_total_sac = df_metas['Meta_SAC'].sum()
meta_total_pend = df_metas['Meta_PEND'].sum()

realizado_sac = 0; realizado_pend = 0
if 'Setor' in df_filtered.columns:
    realizado_sac = df_filtered[df_filtered['Setor'].str.contains('SAC', case=False, na=False)]['Eh_Novo_Episodio'].sum()
    realizado_pend = df_filtered[df_filtered['Setor'].str.contains('Pend', case=False, na=False)]['Eh_Novo_Episodio'].sum()

perc_sac = (realizado_sac / meta_total_sac * 100) if meta_total_sac > 0 else 0
perc_pend = (realizado_pend / meta_total_pend * 100) if meta_total_pend > 0 else 0

def get_cor(realizado, meta, tma_target, ativos):
    if meta == 0: return "off"
    is_today = end_date == datetime.today().date()
    if is_today:
        agora = datetime.now()
        horas_rest = max(0, 17.3 - (agora.hour + agora.minute/60))
        projecao = realizado + ((ativos * horas_rest * 60 * 0.70) / tma_target)
        return "normal" if projecao >= meta else "inverse"
    return "normal" if realizado >= meta else "inverse"

qtd_sac = df_metas[df_metas['Meta_SAC'] > 0].shape[0]
qtd_pend = df_metas[df_metas['Meta_PEND'] > 0].shape[0]
cor_sac = get_cor(realizado_sac, meta_total_sac, 5.383, qtd_sac)
cor_pend = get_cor(realizado_pend, meta_total_pend, 5.133, qtd_pend)

# --- LAYOUT ---
ui_components.render_header()

c1, c2, c3, c4 = st.columns(4)
with c1: ui_components.kpi_card_new("Total Registros", f"{total_bruto}", icon="📦")
with c2: ui_components.kpi_card_new("Atendimentos Reais", f"{total_liquido}", delta="Produtividade", delta_type="positive", icon="✅")
with c3: 
    cor_dup = "positive" if taxa_duplicidade < 15 else "negative"
    ui_components.kpi_card_new("Taxa Duplicidade", f"{taxa_duplicidade:.1f}%", delta="Alvo: <15%", delta_type=cor_dup, icon="♻️")
with c4:
    media_meta = (perc_sac + perc_pend) / 2
    cor_meta = "positive" if media_meta >= 100 else "neutral"
    ui_components.kpi_card_new("Meta Global", f"{media_meta:.1f}%", delta="Média Setores", delta_type=cor_meta, icon="🎯")

st.markdown("<br>", unsafe_allow_html=True)

col_main_1, col_main_2 = st.columns([2, 1])
with col_main_1:
    st.markdown("### 📊 Performance Individual")
    ui_components.render_main_bar_chart(df_filtered)
with col_main_2:
    st.markdown("### 🎯 Acompanhamento de Metas")
    ui_components.render_gauges(perc_sac, perc_pend)

st.markdown("<br>", unsafe_allow_html=True)

st.markdown("### ⚡ Capacidade vs Realizado (TMA)")
ui_components.render_capacity_scatter(df_filtered)

st.markdown("<br>", unsafe_allow_html=True)

col_ev1, col_ev2 = st.columns(2)
with col_ev1:
    ui_components.render_evolution_chart(df_filtered)
with col_ev2:
    ui_components.render_heatmap_clean(df_filtered)
