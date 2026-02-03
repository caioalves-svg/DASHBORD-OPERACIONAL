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

# CSS para deixar os cards de KPI bonitos
st.markdown("""
<style>
    .metric-card { background-color: #f0f2f6; border-radius: 10px; padding: 15px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); }
    [data-testid="stMetricValue"] { font-size: 24px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. CARREGAMENTO E LIMPEZA DE DADOS (ETL)
# ==============================================================================
@st.cache_data(ttl=600) # Cache de 10 min para não ficar lento
def load_data():
    # Conexão com o Google Sheets
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Lê a planilha. O parâmetro usecols garante que só pegamos o que importa
    # Se der erro de "Worksheet not found", verifique se a aba chama "Página1" mesmo
    try:
        df = conn.read(worksheet="Página1")
    except:
        # Tenta ler a primeira aba se o nome for diferente
        df = conn.read()

    # --- LIMPEZA E TRATAMENTO ---
    
    # 1. Converter Data (tratando dia/mês brasileiro)
    df['Data'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['Data']) # Remove linhas vazias/lixo

    # 2. Padronizar Dia da Semana (Garantindo que fique bonito: "Terça-Feira")
    if 'Dia_Semana' in df.columns:
        df['Dia_Semana'] = df['Dia_Semana'].astype(str).str.title().str.strip()
    
    # 3. Criar Hora Cheia (Pegando da coluna 'Hora' que você já tem: "07:18:37" -> "07:00")
    # Garante que é string, pega os 2 primeiros digitos e adiciona :00
    df['Hora_Cheia'] = df['Hora'].astype(str).str.slice(0, 2) + ":00"

    # 4. Tratamento de Nulos (Texto)
    cols_texto = ['Colaborador', 'Portal', 'Transportadora', 'Motivo', 'Motivo_CRM', 'Numero_Pedido', 'Nota_Fiscal']
    for col in cols_texto:
        if col in df.columns:
            df[col] = df[col].fillna("Não Informado").astype(str).replace("nan", "Não Informado")

    # 5. Lógica de Unicidade (O "Pulo do Gato" para duplicidade)
    # Cria um ID de referência: Se tiver Pedido usa ele, se não, usa a Nota Fiscal
    df['ID_Ref'] = np.where(
        df['Numero_Pedido'] != "Não Informado", 
        df['Numero_Pedido'], 
        df['Nota_Fiscal']
    )
    
    # Chave Única = Data + Colaborador + ID_Ref
    # Isso impede que 5 tratativas do mesmo pedido no mesmo dia contem como 5 atendimentos
    df['Data_Str'] = df['Data'].dt.strftime('%Y-%m-%d')
    df['Chave_Unica'] = df['Data_Str'] + "_" + df['Colaborador'] + "_" + df['ID_Ref']
    
    return df

# Carrega os dados
try:
    df_raw = load_data()
except Exception as e:
    st.error(f"Erro ao carregar dados. Verifique o arquivo secrets.toml. Detalhe: {e}")
    st.stop()

# ==============================================================================
# 3. FILTROS LATERAIS (SIDEBAR)
# ==============================================================================
st.sidebar.header("🔍 Filtros")
st.sidebar.markdown("---")

# Filtro de Data
min_date = df_raw['Data'].min().date()
max_date = df_raw['Data'].max().date()
start_date, end_date = st.sidebar.date_input("Período", [min_date, max_date], min_value=min_date, max_value=max_date)

# Filtros de Seleção Múltipla
colaboradores = st.sidebar.multiselect("Colaborador", options=sorted(df_raw['Colaborador'].unique()))
portais = st.sidebar.multiselect("Portal", options=sorted(df_raw['Portal'].unique()))
transportadoras = st.sidebar.multiselect("Transportadora", options=sorted(df_raw['Transportadora'].unique()))

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
# 4. KPIs (INDICADORES)
# ==============================================================================
st.title("📊 Dashboard Operacional Logística")
st.markdown("---")

# Cálculos
total_bruto = df_filtered.shape[0] # Contagem de linhas total
total_liquido = df_filtered['Chave_Unica'].nunique() # Contagem de atendimentos únicos

# Taxa de Duplicidade (Gordura no processo)
taxa_duplicidade = ((total_bruto - total_liquido) / total_bruto * 100) if total_bruto > 0 else 0

# Aderência ao CRM (Tudo que NÃO é "SEM ABERTURA DE CRM" nem "Não Informado")
crm_registrados = df_filtered[~df_filtered['Motivo_CRM'].isin(['SEM ABERTURA DE CRM', 'Não Informado'])].shape[0]
aderencia_crm = (crm_registrados / total_bruto * 100) if total_bruto > 0 else 0

# Exibição
c1, c2, c3, c4 = st.columns(4)
c1.metric("📦 Total Registros", f"{total_bruto}", help="Total de linhas na planilha")
c2.metric("✅ Atendimentos Reais", f"{total_liquido}", help="Pedidos únicos atendidos por colaborador/dia")
c3.metric("⚠️ Taxa de Retrabalho", f"{taxa_duplicidade:.1f}%", delta_color="inverse", help="% de registros duplicados para o mesmo caso")
c4.metric("🛡️ Aderência CRM", f"{aderencia_crm:.1f}%", help="% de casos com Motivo CRM preenchido")

st.markdown("---")

# ==============================================================================
# 5. GRÁFICOS (VISUALIZAÇÃO)
# ==============================================================================

# --- LINHA 1: Produtividade e Ranking ---
col_L1_1, col_L1_2 = st.columns([2, 1])

with col_L1_1:
    st.subheader("Produtividade: Bruto vs Líquido")
    # Agrupa por colaborador
    df_prod = df_filtered.groupby('Colaborador').agg(
        Bruto=('Chave_Unica', 'count'),
        Liquido=('Chave_Unica', 'nunique')
    ).reset_index().sort_values('Liquido', ascending=True) # Ordena pelo real
    
    # Melt para formato do Plotly
    df_melt = df_prod.melt(id_vars='Colaborador', value_vars=['Bruto', 'Liquido'], var_name='Métrica', value_name='Volume')
    
    fig_prod = px.bar(
        df_melt, y='Colaborador', x='Volume', color='Métrica', barmode='group', orientation='h',
        color_discrete_map={'Bruto': '#ff9f3b', 'Liquido': '#0068c9'}, text_auto=True
    )
    fig_prod.update_layout(height=400, margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig_prod, use_container_width=True)

with col_L1_2:
    st.subheader("Ranking Retrabalho")
    # Calcula % de duplicidade por pessoa
    df_prod['Tx_Retrabalho'] = ((df_prod['Bruto'] - df_prod['Liquido']) / df_prod['Bruto'] * 100).fillna(0)
    df_prod = df_prod.sort_values('Tx_Retrabalho', ascending=False)
    
    fig_rank = px.bar(
        df_prod, x='Tx_Retrabalho', y='Colaborador', orientation='h',
        text=df_prod['Tx_Retrabalho'].apply(lambda x: f'{x:.1f}%'),
        color='Tx_Retrabalho', color_continuous_scale='Reds'
    )
    fig_rank.update_layout(height=400, xaxis_title="% Retrabalho", coloraxis_showscale=False)
    st.plotly_chart(fig_rank, use_container_width=True)

st.markdown("---")

# --- LINHA 2: Pareto e Motivos ---
col_L2_1, col_L2_2 = st.columns(2)

with col_L2_1:
    st.subheader("Pareto de Motivos (80/20)")
    # Prepara dados Pareto
    df_pareto = df_filtered['Motivo'].value_counts().reset_index()
    df_pareto.columns = ['Motivo', 'Qtd']
    df_pareto['Acumulado'] = df_pareto['Qtd'].cumsum()
    df_pareto['Perc_Acumulado'] = (df_pareto['Acumulado'] / df_pareto['Qtd'].sum()) * 100
    
    # Gráfico combinado
    fig_pareto = go.Figure()
    fig_pareto.add_trace(go.Bar(x=df_pareto['Motivo'], y=df_pareto['Qtd'], name='Qtd', marker_color='#0068c9'))
    fig_pareto.add_trace(go.Scatter(x=df_pareto['Motivo'], y=df_pareto['Perc_Acumulado'], name='% Acumulado', yaxis='y2', mode='lines+markers', line=dict(color='red', width=2)))
    
    fig_pareto.update_layout(
        height=400,
        yaxis=dict(title='Volume'),
        yaxis2=dict(title='%', overlaying='y', side='right', range=[0, 110]),
        showlegend=False
    )
    st.plotly_chart(fig_pareto, use_container_width=True)

with col_L2_2:
    st.subheader("Distribuição Motivos CRM")
    # Filtra os motivos que importam (tira os "SEM ABERTURA") para ver o erro real
    df_crm_real = df_filtered[~df_filtered['Motivo_CRM'].isin(['SEM ABERTURA DE CRM', 'Não Informado'])]
    
    if not df_crm_real.empty:
        fig_donut = px.pie(df_crm_real, names='Motivo_CRM', hole=0.5)
        fig_donut.update_layout(height=400)
        st.plotly_chart(fig_donut, use_container_width=True)
    else:
        st.warning("Sem dados de CRM registrados no período selecionado.")

# --- LINHA 3: Operacional (Heatmap e Treemap) ---
col_L3_1, col_L3_2 = st.columns(2)

with col_L3_1:
    st.subheader("Mapa de Calor: Pico de Atendimento")
    # Ordenação dos dias
    dias_ordem = ['Segunda-Feira', 'Terça-Feira', 'Quarta-Feira', 'Quinta-Feira', 'Sexta-Feira', 'Sábado', 'Domingo']
    
    # Agrupa dia e hora
    df_heat = df_filtered.groupby(['Dia_Semana', 'Hora_Cheia']).size().reset_index(name='Chamados')
    
    fig_heat = px.density_heatmap(
        df_heat, x='Dia_Semana', y='Hora_Cheia', z='Chamados',
        category_orders={"Dia_Semana": dias_ordem},
        color_continuous_scale='Viridis'
    )
    fig_heat.update_layout(height=400)
    st.plotly_chart(fig_heat, use_container_width=True)

with col_L3_2:
    st.subheader("Volume por Transportadora")
    # Treemap
    df_tree = df_filtered.groupby('Transportadora').size().reset_index(name='Volume')
    fig_tree = px.treemap(df_tree, path=['Transportadora'], values='Volume', color='Volume', color_continuous_scale='Blues')
    fig_tree.update_layout(height=400)
    st.plotly_chart(fig_tree, use_container_width=True)
