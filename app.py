import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(
    page_title="Dashboard de Eficiência Logística",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo CSS customizado
st.markdown("""
<style>
    .metric-card { background-color: #f0f2f6; border-radius: 10px; padding: 15px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); }
    [data-testid="stMetricValue"] { font-size: 24px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 1. CONEXÃO E TRATAMENTO DE DADOS
# ==============================================================================
@st.cache_data(ttl=600) # Cache de 10 minutos para performance
def load_and_clean_data():
    # --- CONEXÃO COM GOOGLE SHEETS ---
    # Cria a conexão usando os segredos configurados
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Lê a aba correta. Substitua 'Página1' pelo nome da sua aba se for diferente
    # O usecols ajuda a puxar só o necessário e evitar erros de colunas vazias
    try:
        df = conn.read(worksheet="Página1") 
    except Exception as e:
        st.error(f"Erro ao ler a planilha: {e}")
        st.stop()

    # --- INÍCIO DO TRATAMENTO (Igual à especificação) ---
    
    # Garantir que datas são datetime
    df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
    df = df.dropna(subset=['Data']) # Remove linhas sem data (lixo)

    # 1. Padronização do Dia da Semana
    dias_pt = {
        'Monday': 'Segunda-Feira', 'Tuesday': 'Terça-Feira', 'Wednesday': 'Quarta-Feira',
        'Thursday': 'Quinta-Feira', 'Friday': 'Sexta-Feira', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
    }
    df['Dia_Semana'] = df['Data'].dt.day_name().map(dias_pt)
    
    # 2. Hora Cheia (Se a coluna Data tiver hora, extrai. Se não, assume 00:00 ou tenta buscar coluna Hora)
    # Assumindo que a coluna 'Data' no Sheets tem data e hora ou existe uma coluna 'Hora' separada
    if 'Hora' in df.columns:
         # Se tiver coluna Hora separada, combine ou use ela. 
         # Simplificação: Extraindo da Data se tiver timestamp, senão 00:00
         df['Hora_Cheia'] = df['Data'].dt.hour.astype(str).str.zfill(2) + ":00"
    else:
         df['Hora_Cheia'] = df['Data'].dt.hour.astype(str).str.zfill(2) + ":00"

    # 3. Tratamento de Nulos
    df['Numero_Pedido'] = df['Numero_Pedido'].fillna("Não Informado").astype(str).replace("nan", "Não Informado")
    df['Nota_Fiscal'] = df['Nota_Fiscal'].fillna("Não Informado").astype(str).replace("nan", "Não Informado")
    
    # Preencher colunas categóricas vazias para evitar erros nos gráficos
    cols_texto = ['Colaborador', 'Portal', 'Transportadora', 'Motivo', 'Motivo_CRM']
    for col in cols_texto:
        if col in df.columns:
            df[col] = df[col].fillna("Não Informado")

    # 4. Lógica de Unicidade (O "Pulo do Gato")
    df['ID_Ref'] = np.where(
        df['Numero_Pedido'] != "Não Informado", 
        df['Numero_Pedido'], 
        df['Nota_Fiscal']
    )
    
    df['Data_Str'] = df['Data'].dt.strftime('%Y-%m-%d')
    df['Chave_Unica'] = df['Data_Str'] + "_" + df['Colaborador'] + "_" + df['ID_Ref']
    
    return df

# Carregar dados reais
df_raw = load_and_clean_data()

# ==============================================================================
# 2. FILTROS GLOBAIS (SIDEBAR)
# ==============================================================================
st.sidebar.header("🔍 Filtros Globais")
st.sidebar.markdown("---")

# Filtro de Data
min_date = df_raw['Data'].min().date()
max_date = df_raw['Data'].max().date()

start_date, end_date = st.sidebar.date_input(
    "Intervalo de Data",
    [min_date, max_date],
    min_value=min_date,
    max_value=max_date
)

# Filtros Categóricos
colaboradores = st.sidebar.multiselect("Colaborador", options=df_raw['Colaborador'].unique())
portais = st.sidebar.multiselect("Portal", options=df_raw['Portal'].unique())
transportadoras = st.sidebar.multiselect("Transportadora", options=df_raw['Transportadora'].unique())

# --- APLICAÇÃO DOS FILTROS ---
df_filtered = df_raw.copy()
df_filtered = df_filtered[(df_filtered['Data'].dt.date >= start_date) & (df_filtered['Data'].dt.date <= end_date)]

if colaboradores:
    df_filtered = df_filtered[df_filtered['Colaborador'].isin(colaboradores)]
if portais:
    df_filtered = df_filtered[df_filtered['Portal'].isin(portais)]
if transportadoras:
    df_filtered = df_filtered[df_filtered['Transportadora'].isin(transportadoras)]

# ==============================================================================
# 3. INDICADORES PRINCIPAIS (KPIs)
# ==============================================================================
st.title("📊 Dashboard de Performance e Qualidade")
st.markdown("---")

total_bruto = df_filtered.shape[0]
total_liquido = df_filtered['Chave_Unica'].nunique()
taxa_duplicidade = ((total_bruto - total_liquido) / total_bruto * 100) if total_bruto > 0 else 0
crm_ok = df_filtered[df_filtered['Motivo_CRM'] != "SEM ABERTURA DE CRM"].shape[0]
aderencia_crm = (crm_ok / total_bruto * 100) if total_bruto > 0 else 0

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("📦 Total Registros (Bruto)", f"{total_bruto}")
kpi2.metric("✅ Atendimentos Reais (Líquido)", f"{total_liquido}")
kpi3.metric("⚠️ Taxa de Duplicidade", f"{taxa_duplicidade:.1f}%", delta_color="inverse")
kpi4.metric("🛡️ Aderência ao CRM", f"{aderencia_crm:.1f}%")

st.markdown("---")

# ==============================================================================
# 4. VISÕES DO DASHBOARD (GRÁFICOS)
# ==============================================================================

# A. Visão de Gestão
st.subheader("👥 Gestão de Produtividade & Qualidade")
col_a1, col_a2 = st.columns([2, 1])

with col_a1:
    df_prod = df_filtered.groupby('Colaborador').agg(
        Bruto=('Chave_Unica', 'count'),
        Liquido=('Chave_Unica', 'nunique')
    ).reset_index()
    df_prod_melted = df_prod.melt(id_vars='Colaborador', value_vars=['Bruto', 'Liquido'], var_name='Tipo', value_name='Volume')
    
    fig_prod = px.bar(df_prod_melted, x='Volume', y='Colaborador', color='Tipo', barmode='group', orientation='h',
                      title="Produtividade: Bruto vs Líquido", color_discrete_map={'Bruto': '#ff7f0e', 'Liquido': '#1f77b4'}, text_auto=True)
    st.plotly_chart(fig_prod, use_container_width=True)

with col_a2:
    df_prod['Tx_Duplicidade'] = (df_prod['Bruto'] - df_prod['Liquido']) / df_prod['Bruto'] * 100
    df_prod = df_prod.sort_values('Tx_Duplicidade', ascending=False)
    fig_rank = px.bar(df_prod, x='Tx_Duplicidade', y='Colaborador', orientation='h', title="Ranking de Duplicidade (%)",
                      text=df_prod['Tx_Duplicidade'].apply(lambda x: f'{x:.1f}%'), color='Tx_Duplicidade', color_continuous_scale='Reds')
    fig_rank.update_layout(coloraxis_showscale=False)
    st.plotly_chart(fig_rank, use_container_width=True)

# B. Causa Raiz
st.markdown("---")
st.subheader("🔍 Causa Raiz e Processos")
col_b1, col_b2 = st.columns(2)

with col_b1:
    df_pareto = df_filtered['Motivo'].value_counts().reset_index()
    df_pareto.columns = ['Motivo', 'Contagem']
    df_pareto['Acumulado'] = df_pareto['Contagem'].cumsum()
    df_pareto['Perc_Acumulado'] = 100 * df_pareto['Acumulado'] / df_pareto['Contagem'].sum()
    
    fig_pareto = go.Figure()
    fig_pareto.add_trace(go.Bar(x=df_pareto['Motivo'], y=df_pareto['Contagem'], name='Volume', marker_color='rgb(55, 83, 109)'))
    fig_pareto.add_trace(go.Scatter(x=df_pareto['Motivo'], y=df_pareto['Perc_Acumulado'], name='% Acumulado', yaxis='y2', mode='lines+markers', marker=dict(color='rgb(219, 64, 82)')))
    fig_pareto.update_layout(title='Pareto de Motivos (80/20)', yaxis=dict(title='Volume'), yaxis2=dict(title='% Acumulado', overlaying='y', side='right', range=[0, 110]), legend=dict(x=0.6, y=1.1, orientation='h'))
    st.plotly_chart(fig_pareto, use_container_width=True)

with col_b2:
    df_crm = df_filtered['Motivo_CRM'].value_counts().reset_index()
    df_crm.columns = ['Motivo CRM', 'Volume']
    fig_donut = px.pie(df_crm, names='Motivo CRM', values='Volume', hole=0.5, title='Distribuição de Motivos CRM')
    st.plotly_chart(fig_donut, use_container_width=True)

# C. Eficiência Logística
st.markdown("---")
st.subheader("🚚 Eficiência Logística & Operacional")
col_c1, col_c2 = st.columns(2)

with col_c1:
    df_tree = df_filtered.copy()
    df_tree['Is_Atraso'] = df_tree['Motivo'].apply(lambda x: 1 if x == 'Atraso' else 0)
    df_tree_grp = df_tree.groupby('Transportadora').agg(Volume=('Chave_Unica', 'count'), Atrasos=('Is_Atraso', 'sum')).reset_index()
    df_tree_grp['Perc_Atraso'] = (df_tree_grp['Atrasos'] / df_tree_grp['Volume']) * 100
    
    fig_tree = px.treemap(df_tree_grp, path=['Transportadora'], values='Volume', color='Perc_Atraso', color_continuous_scale='RdYlGn_r', title='Volume por Transportadora (Cor = % Atraso)')
    st.plotly_chart(fig_tree, use_container_width=True)

with col_c2:
    ordem_dias = ['Segunda-Feira', 'Terça-Feira', 'Quarta-Feira', 'Quinta-Feira', 'Sexta-Feira', 'Sábado', 'Domingo']
    df_heat = df_filtered.groupby(['Dia_Semana', 'Hora_Cheia']).size().reset_index(name='Chamados')
    fig_heat = px.density_heatmap(df_heat, x='Dia_Semana', y='Hora_Cheia', z='Chamados', title='Mapa de Calor de Atendimento', category_orders={"Dia_Semana": ordem_dias}, color_continuous_scale='Viridis')
    st.plotly_chart(fig_heat, use_container_width=True)
