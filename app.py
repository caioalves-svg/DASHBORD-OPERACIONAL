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

# CSS Ajustado: Remove margens excessivas e estiliza KPIs
st.markdown("""
<style>
    .metric-card { background-color: #f0f2f6; border-radius: 10px; padding: 15px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); }
    [data-testid="stMetricValue"] { font-size: 24px; font-weight: bold; }
    /* Ajuste para gráficos não cortarem textos */
    .js-plotly-plot .plotly .modebar { orientation: v; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. CONEXÃO E ETL
# ==============================================================================
@st.cache_data(ttl=600)
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    try:
        df = conn.read(worksheet="Página1")
    except:
        df = conn.read()

    # --- TRATAMENTO ---
    df['Data'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['Data'])

    # Textos
    cols_texto = ['Colaborador', 'Portal', 'Transportadora', 'Motivo', 'Motivo_CRM', 'Numero_Pedido', 'Nota_Fiscal']
    for col in cols_texto:
        if col in df.columns:
            df[col] = df[col].fillna("Não Informado").astype(str).replace("nan", "Não Informado").str.strip()

    # Dia da Semana
    if 'Dia_Semana' in df.columns:
        df['Dia_Semana'] = df['Dia_Semana'].astype(str).str.title().str.strip()
    
    # Hora Cheia
    if 'Hora' in df.columns:
        df['Hora_Cheia'] = df['Hora'].astype(str).str.slice(0, 2) + ":00"
    else:
        df['Hora_Cheia'] = df['Data'].dt.hour.astype(str).str.zfill(2) + ":00"

    # Chave Única
    df['ID_Ref'] = np.where(
        df['Numero_Pedido'] != "Não Informado", 
        df['Numero_Pedido'], 
        df['Nota_Fiscal']
    )
    df['Data_Str'] = df['Data'].dt.strftime('%Y-%m-%d')
    df['Chave_Unica'] = df['Data_Str'] + "_" + df['Colaborador'] + "_" + df['ID_Ref']
    
    return df

try:
    df_raw = load_data()
except Exception as e:
    st.error(f"Erro na conexão. Verifique o secrets.toml. Detalhe: {e}")
    st.stop()

# ==============================================================================
# 3. FILTROS
# ==============================================================================
st.sidebar.header("🔍 Filtros Globais")
st.sidebar.markdown("---")

min_date = df_raw['Data'].min().date()
max_date = df_raw['Data'].max().date()
start_date, end_date = st.sidebar.date_input("Período", [min_date, max_date], min_value=min_date, max_value=max_date)

colaboradores = st.sidebar.multiselect("Colaborador", options=sorted(df_raw['Colaborador'].unique()))
portais = st.sidebar.multiselect("Portal", options=sorted(df_raw['Portal'].unique()))
# Filtra Transportadoras (sem o traço para o filtro visual ficar bonito, mas dados crus mantêm)
lista_transp = sorted([t for t in df_raw['Transportadora'].unique() if t != '-'])
transportadoras = st.sidebar.multiselect("Transportadora", options=lista_transp)

# Aplica Filtros
df_filtered = df_raw.copy()
df_filtered = df_filtered[(df_filtered['Data'].dt.date >= start_date) & (df_filtered['Data'].dt.date <= end_date)]

if colaboradores:
    df_filtered = df_filtered[df_filtered['Colaborador'].isin(colaboradores)]
if portais:
    df_filtered = df_filtered[df_filtered['Portal'].isin(portais)]
if transportadoras:
    df_filtered = df_filtered[df_filtered['Transportadora'].isin(transportadoras)]

# ==============================================================================
# 4. KPIs
# ==============================================================================
st.title("📊 Dashboard de Performance Logística")
st.markdown("---")

total_bruto = df_filtered.shape[0]
total_liquido = df_filtered['Chave_Unica'].nunique()
taxa_duplicidade = ((total_bruto - total_liquido) / total_bruto * 100) if total_bruto > 0 else 0
crm_ok = df_filtered[~df_filtered['Motivo_CRM'].isin(['SEM ABERTURA DE CRM', 'Não Informado'])].shape[0]
aderencia_crm = (crm_ok / total_bruto * 100) if total_bruto > 0 else 0

k1, k2, k3, k4 = st.columns(4)
k1.metric("📦 Total Registros (Bruto)", f"{total_bruto}")
k2.metric("✅ Atendimentos Reais (Líquido)", f"{total_liquido}")
k3.metric("⚠️ Taxa de Retrabalho", f"{taxa_duplicidade:.1f}%", delta_color="inverse")
k4.metric("🛡️ Aderência ao CRM", f"{aderencia_crm:.1f}%")

st.markdown("---")

# ==============================================================================
# 5. VISUALIZAÇÕES
# ==============================================================================

# --- A. PRODUTIVIDADE ---
col_a1, col_a2 = st.columns([2, 1])

with col_a1:
    st.subheader("Produtividade da Equipe")
    df_prod = df_filtered.groupby('Colaborador').agg(
        Bruto=('Chave_Unica', 'count'),
        Liquido=('Chave_Unica', 'nunique')
    ).reset_index().sort_values('Liquido', ascending=True)
    
    df_melt = df_prod.melt(id_vars='Colaborador', value_vars=['Bruto', 'Liquido'], var_name='Métrica', value_name='Volume')
    
    fig_prod = px.bar(
        df_melt, y='Colaborador', x='Volume', color='Métrica', barmode='group', orientation='h',
        color_discrete_map={'Bruto': '#FFA15A', 'Liquido': '#19D3F3'},
        text='Volume' # Exibe o número
    )
    # FORÇA O TEXTO A FICAR VISÍVEL
    fig_prod.update_traces(textposition='outside', textfont_size=12)
    fig_prod.update_layout(height=400, margin=dict(r=20))
    st.plotly_chart(fig_prod, use_container_width=True)

with col_a2:
    st.subheader("Ranking de Retrabalho")
    df_prod['Tx_Erro'] = ((df_prod['Bruto'] - df_prod['Liquido']) / df_prod['Bruto'] * 100).fillna(0)
    df_prod = df_prod.sort_values('Tx_Erro', ascending=True) # Ordenado para o gráfico
    
    fig_rank = px.bar(
        df_prod, x='Tx_Erro', y='Colaborador', orientation='h',
        text=df_prod['Tx_Erro'].apply(lambda x: f'{x:.1f}%'),
        color='Tx_Erro', color_continuous_scale='Reds'
    )
    fig_rank.update_traces(textposition='outside')
    fig_rank.update_layout(height=400, xaxis_title="% Duplicidade", coloraxis_showscale=False, margin=dict(r=20))
    st.plotly_chart(fig_rank, use_container_width=True)

# --- B. PARETO REFINADO ---
st.markdown("---")
col_b1, col_b2 = st.columns(2)

with col_b1:
    st.subheader("Pareto de Motivos (80/20)")
    df_pareto = df_filtered['Motivo'].value_counts().reset_index()
    df_pareto.columns = ['Motivo', 'Qtd']
    
    # Filtra motivos vazios ou irrelevantes se necessário
    df_pareto = df_pareto[df_pareto['Motivo'] != 'Não Informado']
    
    df_pareto['Acumulado'] = df_pareto['Qtd'].cumsum()
    df_pareto['Perc'] = (df_pareto['Acumulado'] / df_pareto['Qtd'].sum()) * 100
    
    fig_pareto = go.Figure()
    
    # Barras
    fig_pareto.add_trace(go.Bar(
        x=df_pareto['Motivo'], 
        y=df_pareto['Qtd'], 
        name='Volume', 
        marker_color='#636EFA',
        text=df_pareto['Qtd'], # Texto na barra
        textposition='auto'
    ))
    
    # Linha
    fig_pareto.add_trace(go.Scatter(
        x=df_pareto['Motivo'], 
        y=df_pareto['Perc'], 
        name='% Acumulado', 
        yaxis='y2', 
        mode='lines+markers+text', # Adiciona texto na linha
        line=dict(color='red', width=3),
        text=df_pareto['Perc'].apply(lambda x: f'{x:.0f}%'), # Texto formatado
        textposition='top center'
    ))
    
    fig_pareto.update_layout(
        height=450,
        xaxis=dict(title='Motivo'),
        yaxis=dict(title='Volume de Ocorrências'),
        yaxis2=dict(title='Porcentagem Acumulada', overlaying='y', side='right', range=[0, 110], showgrid=False),
        showlegend=True,
        legend=dict(x=0.5, y=1.1, orientation='h', xanchor='center')
    )
    st.plotly_chart(fig_pareto, use_container_width=True)

with col_b2:
    st.subheader("Motivos CRM (Erros de Processo)")
    df_crm_clean = df_filtered[~df_filtered['Motivo_CRM'].isin(['SEM ABERTURA DE CRM', 'Não Informado'])]
    
    if not df_crm_clean.empty:
        # Gráfico de Rosca com rótulos
        fig_donut = px.pie(
            df_crm_clean, 
            names='Motivo_CRM', 
            hole=0.5, 
            color_discrete_sequence=px.colors.sequential.RdBu
        )
        fig_donut.update_traces(textposition='inside', textinfo='percent+label')
        fig_donut.update_layout(height=450, showlegend=False) # Tira legenda pra limpar, pois já tem label
        st.plotly_chart(fig_donut, use_container_width=True)
    else:
        st.info("Nenhum erro de CRM registrado no período selecionado.")

# --- C. OPERACIONAL ---
st.markdown("---")
col_c1, col_c2 = st.columns(2)

with col_c1:
    st.subheader("Mapa de Calor (Horário de Pico)")
    dias_ordem = ['Segunda-Feira', 'Terça-Feira', 'Quarta-Feira', 'Quinta-Feira', 'Sexta-Feira', 'Sábado', 'Domingo']
    df_heat = df_filtered.groupby(['Dia_Semana', 'Hora_Cheia']).size().reset_index(name='Chamados')
    
    fig_heat = px.density_heatmap(
        df_heat, x='Dia_Semana', y='Hora_Cheia', z='Chamados',
        category_orders={"Dia_Semana": dias_ordem}, 
        color_continuous_scale='Viridis',
        text_auto=True # Mostra número no quadrado
    )
    fig_heat.update_layout(height=400)
    st.plotly_chart(fig_heat, use_container_width=True)

with col_c2:
    st.subheader("Top Transportadoras (Exclui não informados)")
    
    # Filtra tirando o "-" e "Não Informado"
    df_transp = df_filtered[~df_filtered['Transportadora'].isin(['-', 'Não Informado'])]
    
    df_tree = df_transp['Transportadora'].value_counts().reset_index()
    df_tree.columns = ['Transportadora', 'Volume']
    df_tree = df_tree.sort_values('Volume', ascending=True) # Ordem para barra horizontal
    
    # Gráfico de Barras Horizontais (Substitui Treemap)
    fig_bar_trans = px.bar(
        df_tree, 
        y='Transportadora', 
        x='Volume', 
        orientation='h',
        text='Volume',
        title='Volume por Transportadora',
        color='Volume',
        color_continuous_scale='Blues'
    )
    fig_bar_trans.update_traces(textposition='outside')
    fig_bar_trans.update_layout(height=400, xaxis_title="Volume", coloraxis_showscale=False)
    
    if not df_tree.empty:
        st.plotly_chart(fig_bar_trans, use_container_width=True)
    else:
        st.warning("Nenhuma transportadora informada nos registros filtrados.")
