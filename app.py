import streamlit as st
from datetime import datetime
# Importa os módulos criados (certifique-se de que a pasta 'modules' existe com os arquivos dentro)
from modules import data_loader, business_logic, ui_components

# Configuração da Página (Título e ícone)
st.set_page_config(page_title="Dashboard Operacional", page_icon="🚛", layout="wide", initial_sidebar_state="expanded")

# 1. Carrega o CSS Premium
ui_components.load_css()

# Sidebar: Título e Botão de Refresh
st.sidebar.markdown("## 🚛 Logística & SAC")
if st.sidebar.button("🔄 Atualizar Dados Agora", type="primary"):
    st.cache_data.clear()
    st.rerun()

# 2. Carregamento de Dados (Backend)
try:
    df_raw = data_loader.get_raw_data()
except Exception as e:
    st.error(f"Erro de conexão: {e}")
    st.stop()

# 3. Processamento de Regras de Negócio (Duplicidade SAC, TMA, etc.)
df_processed = business_logic.process_data(df_raw)

# 4. Interface e Filtros (Frontend)
df_filtered, end_date = ui_components.render_sidebar_filters(df_processed)

# 5. Cálculo das Metas Dinâmicas (Regra 07:30 - 17:18)
# Precisamos calcular as porcentagens e cores para passar para o UI
df_metas = business_logic.calculate_meta_logic(df_filtered, end_date)

# Agregações para os Cards de Meta
meta_total_sac = df_metas['Meta_SAC'].sum()
meta_total_pend = df_metas['Meta_PEND'].sum()

realizado_sac = 0
realizado_pend = 0
if 'Setor' in df_filtered.columns:
    realizado_sac = df_filtered[df_filtered['Setor'].astype(str).str.contains('SAC', case=False, na=False)]['Eh_Novo_Episodio'].sum()
    realizado_pend = df_filtered[df_filtered['Setor'].astype(str).str.contains('Pend', case=False, na=False)]['Eh_Novo_Episodio'].sum()

# Lógica de Cor da Meta
def get_cor(realizado, meta, tma_target, ativos):
    # (Lógica simplificada da projeção movida para cá ou mantida no business_logic se preferir)
    # Replicando a lógica do código anterior para garantir funcionalidade:
    if meta == 0: return "off"
    is_today = end_date == datetime.today().date()
    if is_today:
        agora = datetime.now()
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

# Abas
tab1, tab2, tab3 = st.tabs(["🚀 Produtividade & Metas", "🔥 Causa Raiz", "🕵️ Risco de Cancelamento"])

with tab1:
    ui_components.render_productivity_charts(df_filtered)
    ui_components.render_capacity_chart(
        df_filtered, df_metas, 
        perc_sac, realizado_sac, meta_total_sac, cor_sac,
        perc_pend, realizado_pend, meta_total_pend, cor_pend
    )
    st.markdown("---")
    ui_components.render_heatmap(df_filtered)

with tab2:
    # Mantendo a lógica de matrizes aqui ou movendo para UI Componentes
    st.subheader("Matrizes de Risco")
    
    # Matriz 1
    if not df_filtered.empty:
        ui_components.plot_matrix(df_filtered, 'Motivo', 'Portal', 'Matriz: Portal x Motivo') # Precisa adicionar no ui_components se quiser modularizar
        st.markdown("<br>", unsafe_allow_html=True)
        # Matriz 2
        df_clean_transp = df_filtered[df_filtered['Transportadora'] != '-']
        ui_components.plot_matrix(df_clean_transp, 'Motivo', 'Transportadora', 'Matriz: Transportadora x Motivo')
    else:
        st.warning("Sem dados para matrizes.")

with tab3:
    st.subheader("🕵️ Análise de Reincidência e Risco")
    
    # Lógica de Reincidência (Cronologia)
    df_chrono = df_filtered.sort_values(by=['ID_Ref', 'Data_Completa'])
    df_reinc = df_chrono.groupby('ID_Ref').agg(
        Episodios_Reais=('Eh_Novo_Episodio', 'sum'),
        Ultimo_Motivo=('Motivo', 'last'),
        Historico_Completo=('Motivo', lambda x: " ➡️ ".join(x.astype(str))),
        Motivos_Unicos=('Motivo', lambda x: list(set(x))),
        Ultima_Data=('Data_Completa', 'max')
    ).reset_index()
    
    df_reinc = df_reinc[df_reinc['ID_Ref'] != 'Não Informado']
    df_reinc['Risco_Cancelamento'] = df_reinc['Ultimo_Motivo'].astype(str).str.contains('Cancelamento', case=False, na=False)
    df_reinc['Status_Risco'] = [ '🔴 Risco Cancelamento' if x else '🔵 Em Tratativa' for x in df_reinc['Risco_Cancelamento'] ]
    
    df_criticos = df_reinc[df_reinc['Episodios_Reais'] > 1].copy().sort_values('Episodios_Reais', ascending=False)
    
    # KPI de Risco
    qtd_risco = df_criticos[df_criticos['Risco_Cancelamento']].shape[0]
    st.metric("Pedidos com Risco de Cancelamento", f"{qtd_risco}", delta="Atenção Imediata", delta_color="inverse")
    
    st.markdown("---")
    
    # Gráfico e Tabela
    ui_components.render_reincidencia_charts(df_criticos)
    
    st.dataframe(
        df_criticos[['ID_Ref', 'Episodios_Reais', 'Status_Risco', 'Historico_Completo', 'Ultima_Data']].head(100),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Historico_Completo": st.column_config.TextColumn("Evolução do Caso", width="large"),
            "Ultima_Data": st.column_config.DatetimeColumn("Última Interação", format="DD/MM HH:mm"),
        }
    )
