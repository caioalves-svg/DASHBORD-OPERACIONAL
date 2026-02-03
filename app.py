import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from streamlit_gsheets import GSheetsConnection

# ==============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(
    page_title="Dashboard de Eficiência Logística",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS para estilizar os cartões de KPI
st.markdown("""
<style>
    .metric-card { background-color: #f0f2f6; border-radius: 10px; padding: 15px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); }
    [data-testid="stMetricValue"] { font-size: 24px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. CONEXÃO E TRATAMENTO DE DADOS (ETL)
# ==============================================================================
@st.cache_data(ttl=600) # Cache de 10 min para otimizar performance
def load_data():
    # Conecta usando as credenciais do secrets.toml
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Tenta ler a aba "Página1". Se falhar, lê a primeira aba disponível.
    try:
        df = conn.read(worksheet="Página1")
    except:
        df = conn.read()

    # --- LIMPEZA E PADRONIZAÇÃO ---
    
    # 1. Conversão de Data (Assume formato dia/mês/ano)
    df['Data'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['Data']) # Remove linhas vazias

    # 2. Padronizar texto
    cols_texto = ['Colaborador', 'Portal', 'Transportadora', 'Motivo', 'Motivo_CRM', 'Numero_Pedido', 'Nota_Fiscal']
    for col in cols_texto:
        if col in df.columns:
            df[col] = df[col].fillna("Não Informado").astype(str).replace("nan", "Não Informado")

    # 3. Padronizar Dia da Semana
    if 'Dia_Semana' in df.columns:
        df['Dia_Semana'] = df['Dia_Semana'].astype(str).str.title().str.strip()
    
    # 4. Criar Hora Cheia (HH:00)
    # Tenta usar coluna 'Hora' existente, senão extrai da 'Data'
    if 'Hora' in df.columns:
        df['Hora_Cheia'] = df['Hora'].astype(str).str.slice(0, 2) + ":00"
    else:
        df['Hora_Cheia'] = df['Data'].dt.hour.astype(str).str.zfill(2) + ":00"

    # 5. Lógica de Unicidade ("O Pulo do Gato")
    # Define ID de referência: Se não tem Pedido, usa a Nota Fiscal
    df['ID_Ref'] = np.where(
        df['Numero_Pedido'] != "Não Informado", 
        df['Numero_Pedido'], 
        df['Nota_Fiscal']
    )
    
    # Cria a Chave Única para remover duplicidade de atendimento
    df['Data_Str'] = df['Data'].dt.strftime('%Y-%m-%d')
    df['Chave_Unica'] = df['Data_Str'] + "_" + df['Colaborador'] + "_" + df['ID_Ref']
    
    return df

# Executa o carregamento
try:
    df_raw = load_data()
except Exception as e:
    st.error(f"Erro ao carregar dados. Verifique se o secrets.toml está na pasta .streamlit. Erro: {e}")
    st.stop()

# ==============================================================================
# 3. FILTROS LATERAIS
# ==============================================================================
st.sidebar.header("🔍 Filtros Globais")
st.sidebar.markdown("---")

# Filtro de Data
min_date = df_raw['Data'].min().date()
max_date = df_raw['Data'].max().date()
start_date, end_date = st.sidebar.date_input("Período", [min_date, max_date], min_value=min_date, max_value=max_date)

# Filtros de Seleção
colaboradores = st.sidebar.multiselect("Colaborador", options=sorted(df_raw['Colaborador'].unique()))
portais = st.sidebar.multiselect("Portal", options=sorted(df_raw['Portal'].unique()))
transportadoras = st.sidebar.multiselect("Transportadora", options=sorted(df_raw['Transportadora'].unique()))

# Aplicação dos Filtros
df_filtered = df_raw.copy()
df_filtered = df_filtered[(df_filtered['Data'].dt.date >= start_date) & (df_filtered['Data'].dt.date <= end_date)]

if colaboradores:
    df_filtered = df_filtered[df_filtered['Colaborador'].isin(colaboradores)]
if portais:
    df_filtered = df_filtered[df_filtered['Portal'].isin(portais)]
if transportadoras:
    df_filtered = df_filtered[df_filtered['Transportadora'].isin(transportadoras)]

# ==============================================================================
# 4. KPIs (INDICADORES)
# ==============================================================================
st.title("📊 Dashboard de Performance Logística")
st.markdown("---")

# Cálculos KPI
total_bruto = df_filtered.shape[0]
total_liquido = df_filtered['Chave_Unica'].nunique()
taxa_duplicidade = ((total_bruto - total_liquido) / total_bruto * 100) if total_bruto > 0 else 0
crm_ok = df_filtered[~df_filtered['Motivo_CRM'].isin(['SEM ABERTURA DE CRM', 'Não Informado'])].shape[0]
aderencia_crm = (crm_ok / total_bruto * 100) if total_bruto > 0 else 0

# Exibição KPI
k1, k2, k3, k4 = st.columns(4)
k1.metric("📦 Total Registros (Bruto)", f"{total_bruto}")
k2.metric("✅ Atendimentos Reais (Líquido)", f"{total_liquido}")
k3.metric("⚠️ Taxa de Retrabalho", f"{taxa_duplicidade:.1f}%", delta_color="inverse")
k4.metric("🛡️ Aderência ao CRM", f"{aderencia_crm:.1f}%")

st.markdown("---")

# ==============================================================================
# 5. VISUALIZAÇÕES
# ==============================================================================

# --- LINHA A: Produtividade ---
col_a1, col_a2 = st.columns([2, 1])

with col_a1:
    st.subheader("Produtividade da Equipe")
    df_prod = df_filtered.groupby('Colaborador').agg(
        Bruto=('Chave_Unica', 'count'),
        Liquido=('Chave_Unica', 'nunique')
    ).reset_index().sort_values('Liquido', ascending=True)
    
    df_melt = df_prod.melt(id_vars='Colaborador', value_vars=['Bruto', 'Liquido'], var_name='Métrica', value_name='Volume')
    
    fig_prod = px.bar(df_melt, y='Colaborador', x='Volume', color='Métrica', barmode='group', orientation='h',
                      color_discrete_map={'Bruto': '#FFA15A', 'Liquido': '#19D3F3'}, text_auto=True)
    fig_prod.update_layout(height=400, legend_title_text='')
    st.plotly_chart(fig_prod, use_container_width=True)

with col_a2:
    st.subheader("Ranking de Retrabalho")
    df_prod['Tx_Erro'] = ((df_prod['Bruto'] - df_prod['Liquido']) / df_prod['Bruto'] * 100).fillna(0)
    df_prod = df_prod.sort_values('Tx_Erro', ascending=False)
    
    fig_rank = px.bar(df_prod, x='Tx_Erro', y='Colaborador', orientation='h',
                      text=df_prod['Tx_Erro'].apply(lambda x: f'{x:.1f}%'),
                      color='Tx_Erro', color_continuous_scale='Reds')
    fig_rank.update_layout(height=400, xaxis_title="% Duplicidade", coloraxis_showscale=False)
    st.plotly_chart(fig_rank, use_container_width=True)

# --- LINHA B: Motivos e Causa Raiz ---
st.markdown("---")
col_b1, col_b2 = st.columns(2)

with col_b1:
    st.subheader("Pareto de Motivos (80/20)")
    df_pareto = df_filtered['Motivo'].value_counts().reset_index()
    df_pareto.columns = ['Motivo', 'Qtd']
    df_pareto['Acumulado'] = df_pareto['Qtd'].cumsum()
    df_pareto['Perc'] = (df_pareto['Acumulado'] / df_pareto['Qtd'].sum()) * 100
    
    fig_pareto = go.Figure()
    fig_pareto.add_trace(go.Bar(x=df_pareto['Motivo'], y=df_pareto['Qtd'], name='Qtd', marker_color='#636EFA'))
    fig_pareto.add_trace(go.Scatter(x=df_pareto['Motivo'], y=df_pareto['Perc'], name='% Acumulado', yaxis='y2', mode='lines+markers', line=dict(color='red', width=2)))
    fig_pareto.update_layout(height=400, yaxis2=dict(overlaying='y', side='right', range=[0, 110], showgrid=False), showlegend=False)
    st.plotly_chart(fig_pareto, use_container_width=True)

with col_b2:
    st.subheader("Motivos CRM (Erros Reais)")
    df_crm_clean = df_filtered[~df_filtered['Motivo_CRM'].isin(['SEM ABERTURA DE CRM', 'Não Informado'])]
    
    if not df_crm_clean.empty:
        fig_donut = px.pie(df_crm_clean, names='Motivo_CRM', hole=0.5, color_discrete_sequence=px.colors.sequential.RdBu)
        fig_donut.update_layout(height=400)
        st.plotly_chart(fig_donut, use_container_width=True)
    else:
        st.info("Nenhum erro de CRM registrado no período selecionado.")

# --- LINHA C: Operacional ---
st.markdown("---")
col_c1, col_c2 = st.columns(2)

with col_c1:
    st.subheader("Mapa de Calor (Horário de Pico)")
    dias_ordem = ['Segunda-Feira', 'Terça-Feira', 'Quarta-Feira', 'Quinta-Feira', 'Sexta-Feira', 'Sábado', 'Domingo']
    df_heat = df_filtered.groupby(['Dia_Semana', 'Hora_Cheia']).size().reset_index(name='Chamados')
    
    fig_heat = px.density_heatmap(df_heat, x='Dia_Semana', y='Hora_Cheia', z='Chamados',
                                  category_orders={"Dia_Semana": dias_ordem}, color_continuous_scale='Viridis')
    fig_heat.update_layout(height=400)
    st.plotly_chart(fig_heat, use_container_width=True)

with col_c2:
    st.subheader("Volume por Transportadora")
    df_tree = df_filtered.groupby('Transportadora').size().reset_index(name='Volume')
    fig_tree = px.treemap(df_tree, path=['Transportadora'], values='Volume', color='Volume', color_continuous_scale='Blues')
    fig_tree.update_layout(height=400)
    st.plotly_chart(fig_tree, use_container_width=True)
