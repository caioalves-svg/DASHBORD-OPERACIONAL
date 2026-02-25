import streamlit as st
from datetime import datetime
# Importa os módulos
from modules import data_loader, business_logic, ui_components

# Configuração da Página
st.set_page_config(page_title="Dashboard Operacional", page_icon="🚛", layout="wide", initial_sidebar_state="expanded")

# 1. Carrega o CSS Premium
ui_components.load_css()

# Sidebar
st.sidebar.markdown("## 🚛 Logística & SAC")
if st.sidebar.button("🔄 Atualizar Dados Agora", type="primary"):
    st.cache_data.clear()
    st.rerun()

# 2. Carregamento de Dados
try:
    df_raw = data_loader.get_raw_data()
except Exception as e:
    st.error(f"Erro de conexão: {e}")
    st.stop()

# 3. Processamento
df_processed = business_logic.process_data(df_raw)

# 4. Filtros
df_filtered, end_date = ui_components.render_sidebar_filters(df_processed)

# 5. Cálculo das Metas Dinâmicas
df_metas = business_logic.calculate_meta_logic(df_filtered, end_date)

# Agregações para os Cards de Meta
meta_total_sac = df_metas['Meta_SAC'].sum()
meta_total_pend = df_metas['Meta_PEND'].sum()

realizado_sac = 0
realizado_pend = 0
if 'Setor' in df_filtered.columns:
    realizado_sac = df_filtered[df_filtered['Setor'].astype(str).str.contains('SAC', case=False, na=False)]['Eh_Novo_Episodio'].sum()
    realizado_pend = df_filtered[df_filtered['Setor'].astype(str).str.contains('Pend', case=False, na=False)]['Eh_Novo_Episodio'].sum()

# Lógica de Cor da Meta (Simplificada para exibição)
def get_cor(realizado, meta, tma_target, ativos):
    if meta == 0: return "off"
    is_today = end_date == datetime.today().date()
    if is_today:
        agora = datetime.now()
        # Ajuste do horário fim jornada 17.3 (17:18)
        horas_rest = max(0, 17.3 - (agora.hour + agora.minute/60))
        projecao = realizado + ((ativos * horas_rest * 60 * 0.70) / tma_target)
        return "normal" if projecao >= meta else "inverse"
    return "normal" if realizado >= meta else "inverse"

# Contagem de ativos
qtd_sac = df_metas[df_metas['Meta_SAC'] > 0].shape[0]
qtd_pend = df_metas[df_metas['Meta_PEND'] > 0].shape[0]

cor_sac = get_cor(realizado_sac, meta_total_sac, 5.383, qtd_sac)
cor_pend = get_cor(realizado_pend, meta_total_pend, 5.133, qtd_pend)

perc_sac = (realizado_sac / meta_total_sac * 100) if meta_total_sac > 0 else 0
perc_pend = (realizado_pend / meta_total_pend * 100) if meta_total_pend > 0 else 0

# --- CONSTRUÇÃO DO DASHBOARD ---
st.markdown("## 📊 Visão Geral da Operação")

# Renderiza KPIs do Topo
ui_components.render_kpis(df_filtered, df_metas, end_date)

st.markdown("---")

# Seção Principal (Produtividade e Metas) - Agora sem abas, direto na tela
ui_components.render_productivity_charts(df_filtered)

ui_components.render_capacity_chart(
    df_filtered, df_metas, 
    perc_sac, realizado_sac, meta_total_sac, cor_sac,
    perc_pend, realizado_pend, meta_total_pend, cor_pend
)

st.markdown("---")

# Mapa de Calor
ui_components.render_heatmap(df_filtered)
