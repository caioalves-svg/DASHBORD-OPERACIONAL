import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import timedelta
from streamlit_gsheets import GSheetsConnection

# ==============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(
    page_title="Dashboard Operacional",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS Aprimorado
st.markdown("""
<style>
    .metric-card { background-color: #f0f2f6; border-radius: 10px; padding: 15px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); }
    [data-testid="stMetricValue"] { font-size: 24px; font-weight: bold; }
    .js-plotly-plot .plotly .modebar { orientation: v; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. CONEXÃO E ETL (COM LÓGICA DE REINCIDÊNCIA AVANÇADA)
# ==============================================================================
@st.cache_data(ttl=600)
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df = conn.read(worksheet="Página1")
    except:
        df = conn.read()

    # --- TRATAMENTO BÁSICO ---
    df['Data'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['Data'])

    # Padronização de Textos
    cols_texto = ['Colaborador', 'Setor', 'Portal', 'Transportadora', 'Motivo', 'Motivo_CRM', 'Numero_Pedido', 'Nota_Fiscal']
    for col in cols_texto:
        if col in df.columns:
            df[col] = df[col].fillna("Não Informado").astype(str).replace("nan", "Não Informado").str.strip()

    # Dia da Semana e Hora Cheia
    if 'Dia_Semana' in df.columns:
        df['Dia_Semana'] = df['Dia_Semana'].astype(str).str.title().str.strip()
    
    if 'Hora' in df.columns:
        # Garante string HH:MM:SS
        df['Hora_Str'] = df['Hora'].astype(str)
        df['Hora_Cheia'] = df['Hora_Str'].str.slice(0, 2) + ":00"
    else:
        df['Hora_Cheia'] = df['Data'].dt.hour.astype(str).str.zfill(2) + ":00"
        df['Hora_Str'] = df['Data'].dt.strftime('%H:%M:%S')

    # --- LÓGICA DE CHAVE ÚNICA ---
    df['ID_Ref'] = np.where(df['Numero_Pedido'] != "Não Informado", df['Numero_Pedido'], df['Nota_Fiscal'])
    df['Data_Str'] = df['Data'].dt.strftime('%Y-%m-%d')
    df['Chave_Unica'] = df['Data_Str'] + "_" + df['Colaborador'] + "_" + df['ID_Ref']

    # --- LÓGICA DE REINCIDÊNCIA (O PULO DO GATO AVANÇADO) ---
    # 1. Cria Data Completa (Data + Hora) para cálculo preciso
    # Tenta converter Hora_Str para timedelta, se falhar assume 00:00
    try:
        df['Data_Completa'] = df['Data'] + pd.to_timedelta(df['Hora_Str'])
    except:
        df['Data_Completa'] = df['Data']

    # 2. Ordena por Pedido e Tempo
    df = df.sort_values(by=['ID_Ref', 'Data_Completa'])

    # 3. Calcula a diferença de tempo entre contatos DO MESMO PEDIDO
    df['Tempo_Desde_Ultimo'] = df.groupby('ID_Ref')['Data_Completa'].diff()

    # 4. Define se é um "Novo Episódio" (Se for o primeiro contato OU se passou mais de 24h do anterior)
    # pd.Timedelta(hours=24) define a janela de agrupamento
    df['Eh_Novo_Episodio'] = np.where(
        (df['Tempo_Desde_Ultimo'].isnull()) | (df['Tempo_Desde_Ultimo'] > pd.Timedelta(hours=24)), 
        1, 
        0
    )

    return df

try:
    df_raw = load_data()
except Exception as e:
    st.error(f"Erro no processamento. Verifique se a coluna Hora existe e está correta. Detalhe: {e}")
    st.stop()

# ==============================================================================
# 3. FILTROS GLOBAIS
# ==============================================================================
st.sidebar.header("🔍 Filtros")
st.sidebar.markdown("---")

min_date = df_raw['Data'].min().date()
max_date = df_raw['Data'].max().date()

start_date, end_date = st.sidebar.date_input("Período", [min_date, max_date], min_value=min_date, max_value=max_date, format="DD/MM/YYYY")

# Filtros Condicionais
if 'Setor' in df_raw.columns:
    setores = st.sidebar.multiselect("Setor", options=sorted(df_raw['Setor'].unique()))
else:
    setores = []

colaboradores = st.sidebar.multiselect("Colaborador", options=sorted(df_raw['Colaborador'].unique()))
portais = st.sidebar.multiselect("Portal", options=sorted(df_raw['Portal'].unique()))
lista_transp = sorted([t for t in df_raw['Transportadora'].unique() if t not in ['-', 'Não Informado']])
transportadoras = st.sidebar.multiselect("Transportadora", options=lista_transp)

# Aplica Filtros
df_filtered = df_raw.copy()
df_filtered = df_filtered[(df_filtered['Data'].dt.date >= start_date) & (df_filtered['Data'].dt.date <= end_date)]

if setores and 'Setor' in df_filtered.columns: df_filtered = df_filtered[df_filtered['Setor'].isin(setores)]
if colaboradores: df_filtered = df_filtered[df_filtered['Colaborador'].isin(colaboradores)]
if portais: df_filtered = df_filtered[df_filtered['Portal'].isin(portais)]
if transportadoras: df_filtered = df_filtered[df_filtered['Transportadora'].isin(transportadoras)]

# ==============================================================================
# 4. DASHBOARD
# ==============================================================================
st.title("DASHBOARD OPERACIONAL")

# KPIs Principais (Fixos no topo)
total_bruto = df_filtered.shape[0]
total_liquido = df_filtered['Chave_Unica'].nunique()
taxa_duplicidade = ((total_bruto - total_liquido) / total_bruto * 100) if total_bruto > 0 else 0
crm_ok = df_filtered[~df_filtered['Motivo_CRM'].isin(['SEM ABERTURA DE CRM', 'Não Informado'])].shape[0]
aderencia_crm = (crm_ok / total_bruto * 100) if total_bruto > 0 else 0

k1, k2, k3, k4 = st.columns(4)
k1.metric("📦 Total Registros", f"{total_bruto}")
k2.metric("✅ Atendimentos Reais", f"{total_liquido}")
k3.metric("⚠️ Taxa Retrabalho", f"{taxa_duplicidade:.1f}%", delta_color="inverse")
k4.metric("🛡️ Aderência CRM", f"{aderencia_crm:.1f}%")

st.markdown("---")

# ABAS PARA ORGANIZAÇÃO
tab1, tab2, tab3 = st.tabs(["📊 Visão Geral", "🔥 Causa Raiz", "🕵️ Deep Dive (Reincidência)"])

# --- ABA 1: VISÃO GERAL (Produtividade e Operacional) ---
with tab1:
    st.subheader("1. Produtividade da Equipe")
    df_prod = df_filtered.groupby('Colaborador').agg(
        Bruto=('Chave_Unica', 'count'),
        Liquido=('Chave_Unica', 'nunique')
    ).reset_index().sort_values('Liquido', ascending=True)
    
    df_melt = df_prod.melt(id_vars='Colaborador', value_vars=['Bruto', 'Liquido'], var_name='Métrica', value_name='Volume')
    fig_prod = px.bar(df_melt, y='Colaborador', x='Volume', color='Métrica', barmode='group', orientation='h',
                      color_discrete_map={'Bruto': '#FFA15A', 'Liquido': '#19D3F3'}, text='Volume')
    fig_prod.update_traces(textposition='outside')
    fig_prod.update_layout(height=500, margin=dict(r=50))
    st.plotly_chart(fig_prod, use_container_width=True)

    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("2. Horários de Pico")
        dias_ordem = ['Segunda-Feira', 'Terça-Feira', 'Quarta-Feira', 'Quinta-Feira', 'Sexta-Feira', 'Sábado', 'Domingo']
        df_heat = df_filtered.groupby(['Dia_Semana', 'Hora_Cheia']).size().reset_index(name='Chamados')
        fig_heat = px.density_heatmap(df_heat, x='Dia_Semana', y='Hora_Cheia', z='Chamados',
                                      category_orders={"Dia_Semana": dias_ordem}, color_continuous_scale='Viridis', text_auto=True)
        st.plotly_chart(fig_heat, use_container_width=True)
    
    with col2:
        st.subheader("3. Volume por Transportadora")
        df_transp = df_filtered[~df_filtered['Transportadora'].isin(['-', 'Não Informado'])]
        df_tree = df_transp['Transportadora'].value_counts().reset_index()
        df_tree.columns = ['Transportadora', 'Volume']
        df_tree = df_tree.sort_values('Volume', ascending=True)
        fig_bar_trans = px.bar(df_tree, y='Transportadora', x='Volume', orientation='h', text='Volume', 
                               color='Volume', color_continuous_scale='Blues')
        fig_bar_trans.update_traces(textposition='outside')
        fig_bar_trans.update_layout(coloraxis_showscale=False)
        st.plotly_chart(fig_bar_trans, use_container_width=True)

# --- ABA 2: CAUSA RAIZ ---
with tab2:
    st.subheader("1. Pareto de Motivos (80/20)")
    df_pareto = df_filtered['Motivo'].value_counts().reset_index()
    df_pareto.columns = ['Motivo', 'Qtd']
    df_pareto = df_pareto[df_pareto['Motivo'] != 'Não Informado']
    df_pareto['Acumulado'] = df_pareto['Qtd'].cumsum()
    df_pareto['Perc'] = (df_pareto['Acumulado'] / df_pareto['Qtd'].sum()) * 100

    fig_pareto = go.Figure()
    fig_pareto.add_trace(go.Bar(x=df_pareto['Motivo'], y=df_pareto['Qtd'], name='Volume', marker_color='#636EFA', text=df_pareto['Qtd'], textposition='auto'))
    fig_pareto.add_trace(go.Scatter(x=df_pareto['Motivo'], y=df_pareto['Perc'], name='% Acumulado', yaxis='y2', mode='lines+markers+text', 
                                    line=dict(color='red', width=3), text=df_pareto['Perc'].apply(lambda x: f'{x:.0f}%'), textposition='top center'))
    fig_pareto.update_layout(height=500, yaxis=dict(title='Volume'), yaxis2=dict(title='% Acumulado', overlaying='y', side='right', range=[0, 115], showgrid=False),
                             legend=dict(orientation='h', y=1.1, x=0.5, xanchor='center'))
    st.plotly_chart(fig_pareto, use_container_width=True)
    
    st.markdown("---")
    
    st.subheader("2. Matriz de Risco (Portal vs Motivo)")
    st.info("💡 Insight: Quanto mais escura a cor, maior a concentração daquele problema naquele Portal.")
    
    # Heatmap cruzado
    df_matrix = df_filtered[df_filtered['Motivo'] != 'Não Informado']
    df_matrix = df_matrix[df_matrix['Portal'] != 'Não Informado']
    
    # Cria crosstab
    matrix_data = pd.crosstab(df_matrix['Portal'], df_matrix['Motivo'])
    
    fig_matrix = px.imshow(
        matrix_data, 
        text_auto=True, 
        aspect="auto", 
        color_continuous_scale='Reds',
        labels=dict(x="Motivo", y="Portal", color="Volume")
    )
    fig_matrix.update_layout(height=500)
    st.plotly_chart(fig_matrix, use_container_width=True)

# --- ABA 3: DEEP DIVE (REINCIDÊNCIA) ---
with tab3:
    st.subheader("🕵️ Análise de Reincidência (O 'Freguês')")
    st.markdown("""
    **Lógica:** Consideramos um novo episódio apenas se o contato ocorrer **24 horas após** o contato anterior.
    Registros muito próximos (ex: 10:00 e 10:05) são agrupados como uma única tratativa.
    """)
    
    # Agrupa por Pedido para calcular métricas de reincidência
    df_reincidencia = df_filtered.groupby('ID_Ref').agg(
        Episodios_Reais=('Eh_Novo_Episodio', 'sum'), # Conta quantas vezes quebrou a janela de 24h
        Total_Contatos=('Data', 'count'),            # Contatos brutos
        Primeiro_Contato=('Data_Completa', 'min'),
        Ultimo_Contato=('Data_Completa', 'max'),
        Motivos_Distintos=('Motivo', lambda x: list(set(x)))
    ).reset_index()

    # Filtra apenas quem tem ID válido
    df_reincidencia = df_reincidencia[df_reincidencia['ID_Ref'] != 'Não Informado']
    
    # Calcula duração do "pesadelo" (dias entre primeiro e ultimo contato)
    df_reincidencia['Dias_Em_Aberto'] = (df_reincidencia['Ultimo_Contato'] - df_reincidencia['Primeiro_Contato']).dt.days
    
    # Filtro: Apenas reincidentes (Episodios > 1)
    df_criticos = df_reincidencia[df_reincidencia['Episodios_Reais'] > 1].copy()
    
    col_d1, col_d2 = st.columns([3, 1])
    
    with col_d1:
        st.markdown("#### Dispersão: Tempo de Resolução vs. Quantidade de Episódios")
        if not df_criticos.empty:
            fig_scatter = px.scatter(
                df_criticos,
                x='Dias_Em_Aberto',
                y='Episodios_Reais',
                hover_data=['ID_Ref', 'Motivos_Distintos'],
                size='Total_Contatos', # Tamanho da bolha = volume bruto
                color='Episodios_Reais',
                title="Pedidos Críticos (Reincidentes)",
                labels={'Dias_Em_Aberto': 'Dias desde o 1º contato', 'Episodios_Reais': 'Qtd de Atendimentos (Janela 24h)'}
            )
            fig_scatter.update_layout(height=500)
            st.plotly_chart(fig_scatter, use_container_width=True)
        else:
            st.success("Parabéns! Nenhum pedido com reincidência crítica (>1 episódio com intervalo de 24h) encontrado no período.")

    with col_d2:
        st.markdown("#### Top 5 'Fregueses'")
        if not df_criticos.empty:
            top_5 = df_criticos.sort_values('Episodios_Reais', ascending=False).head(5)
            for index, row in top_5.iterrows():
                st.error(f"**Pedido: {row['ID_Ref']}**")
                st.write(f"⚠️ {row['Episodios_Reais']} Episódios Reais")
                st.write(f"📅 {row['Dias_Em_Aberto']} Dias em aberto")
                st.write(f"📝 Motivos: {row['Motivos_Distintos']}")
                st.markdown("---")
