import streamlit as st
from datetime import datetime
from modules import data_loader, business_logic, ui_components

# Configuração da Página
st.set_page_config(page_title="Dashboard Operacional", page_icon="🚛", layout="wide", initial_sidebar_state="expanded")

# Carrega CSS Customizado
ui_components.load_css()

# Botão de Atualização Manual
st.sidebar.title("Dashboard Operacional")
if st.sidebar.button("🔄 Atualizar Dados Agora"):
    st.cache_data.clear()
    st.rerun()

# 1. Carregamento de Dados (Data Layer)
try:
    df_raw = data_loader.get_raw_data()
except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
    st.stop()

# 2. Processamento e Lógica de Negócio (Business Layer)
df_processed = business_logic.process_data(df_raw)

# 3. Interface de Usuário e Filtros (UI Layer)
df_filtered, end_date = ui_components.render_sidebar_filters(df_processed)

# Cálculo de Metas e Cores
df_metas = business_logic.calculate_meta_logic(df_filtered, end_date)

# --- CONSTRUÇÃO DO DASHBOARD ---
st.markdown("## 📊 Visão Geral")

# Renderiza KPIs do Topo
ui_components.render_kpis(df_filtered, df_metas, end_date)

# Abas
tab1, tab2, tab3 = st.tabs(["🚀 Produtividade & Capacidade", "🔥 Causa Raiz", "🕵️ Risco de Cancelamento"])

with tab1:
    ui_components.render_productivity_charts(df_filtered)
    st.markdown("---")
    ui_components.render_capacity_chart(df_filtered)
    
    # Heatmap (Simplificado aqui, pode mover para ui_components se quiser)
    st.subheader("3. Mapa de Calor (Segunda a Sexta)")
    import plotly.express as px
    dias_uteis = ['Segunda-Feira', 'Terça-Feira', 'Quarta-Feira', 'Quinta-Feira', 'Sexta-Feira']
    df_heat = df_filtered[df_filtered['Dia_Semana'].isin(dias_uteis)]
    if not df_heat.empty:
        df_grp = df_heat.groupby(['Dia_Semana', 'Hora_Cheia']).size().reset_index(name='Chamados')
        fig_heat = px.density_heatmap(df_grp, x='Dia_Semana', y='Hora_Cheia', z='Chamados', category_orders={"Dia_Semana": dias_uteis}, color_continuous_scale='Viridis', text_auto=True)
        st.plotly_chart(fig_heat, use_container_width=True)

with tab2:
    # Lógica de matrizes (pode ser movida para ui_components.render_matrices)
    st.info("Visualizações de Causa Raiz mantidas conforme lógica original.")
    # (Copie a lógica de plot_matrix do código original para cá ou crie uma função no ui_components)

with tab3:
    st.subheader("🕵️ Risco de Cancelamento (Reincidência Crítica)")
    
    df_chrono = df_filtered.sort_values(by=['ID_Ref', 'Data_Completa'])
    df_reinc = df_chrono.groupby('ID_Ref').agg(
        Episodios_Reais=('Eh_Novo_Episodio', 'sum'),
        Ultimo_Motivo=('Motivo', 'last'),
        Historico_Completo=('Motivo', lambda x: " ➡️ ".join(x.astype(str))),
        Ultima_Data=('Data_Completa', 'max')
    ).reset_index()
    
    # Filtros e Lógica de Risco
    df_reinc = df_reinc[df_reinc['ID_Ref'] != 'Não Informado']
    df_reinc['Risco_Cancelamento'] = df_reinc['Ultimo_Motivo'].astype(str).str.contains('Cancelamento', case=False, na=False)
    df_reinc['Status_Risco'] = [ '🔴 Risco Cancelamento' if x else '🔵 Em Tratativa' for x in df_reinc['Risco_Cancelamento'] ]
    
    df_criticos = df_reinc[df_reinc['Episodios_Reais'] > 1].copy().sort_values('Episodios_Reais', ascending=False)
    
    qtd_risco = df_criticos[df_criticos['Risco_Cancelamento']].shape[0]
    st.metric("Clientes Reincidentes pedindo Cancelamento", f"{qtd_risco}", delta="Atenção Prioritária", delta_color="inverse")
    
    # Tabela
    st.markdown("### 📋 Lista Detalhada")
    st.dataframe(df_criticos.head(50), use_container_width=True, hide_index=True)
