import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import pytz

# ==============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(
    page_title="Dashboard Operacional",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Parâmetros Fixos Solicitados
TMA_ALVO_SAC = 5 + (9/60)        # 05:09 (5.15 min)
TMA_ALVO_PEND = 5 + (53/60)      # 05:53 (5.88 min)
TMA_PADRAO = (TMA_ALVO_SAC + TMA_ALVO_PEND) / 2
HORA_INICIO = 7
HORA_FIM = 18
# 11 horas de trabalho * 60 min * 0.7 (30% ociosidade) = 462 minutos produtivos
TEMPO_UTIL_DIA = ((HORA_FIM - HORA_INICIO) * 60) * 0.70 

st.markdown("""
<style>
    .metric-card { background-color: #f0f2f6; border-radius: 10px; padding: 15px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); }
    [data-testid="stMetricValue"] { font-size: 24px; font-weight: bold; }
    .js-plotly-plot .plotly .modebar { orientation: v; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. ETL & CÁLCULOS
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

    cols_texto = ['Colaborador', 'Setor', 'Portal', 'Transportadora', 'Motivo', 'Motivo_CRM', 'Numero_Pedido', 'Nota_Fiscal']
    for col in cols_texto:
        if col in df.columns:
            df[col] = df[col].fillna("Não Informado").astype(str).replace("nan", "Não Informado").str.strip().str.replace(';', ',').str.replace('\n', ' ')

    # Data e Hora
    if 'Hora' in df.columns:
        df['Hora_Str'] = df['Hora'].astype(str)
        df['Hora_Cheia'] = df['Hora_Str'].str.slice(0, 2) + ":00"
    else:
        df['Hora_Cheia'] = df['Data'].dt.hour.astype(str).str.zfill(2) + ":00"
        df['Hora_Str'] = df['Data'].dt.strftime('%H:%M:%S')

    try:
        df['Data_Completa'] = df['Data'] + pd.to_timedelta(df['Hora_Str'])
    except:
        df['Data_Completa'] = df['Data']

    if 'Dia_Semana' in df.columns:
        df['Dia_Semana'] = df['Dia_Semana'].astype(str).str.title().str.strip()

    # Chave Única e ID Ref
    df['ID_Ref'] = np.where(df['Numero_Pedido'] != "Não Informado", df['Numero_Pedido'], df['Nota_Fiscal'])
    df['ID_Ref'] = df['ID_Ref'].astype(str)
    
    df['Data_Str'] = df['Data'].dt.strftime('%Y-%m-%d')
    df['Chave_Unica_Dia'] = df['Data_Str'] + "_" + df['Colaborador'] + "_" + df['ID_Ref']

    # --- LÓGICA 2 HORAS ---
    df = df.sort_values(by=['ID_Ref', 'Data_Completa'])
    df['Tempo_Desde_Ultimo_Contato'] = df.groupby('ID_Ref')['Data_Completa'].diff()
    
    df['Eh_Novo_Episodio'] = np.where(
        (df['Tempo_Desde_Ultimo_Contato'].isnull()) | (df['Tempo_Desde_Ultimo_Contato'] > pd.Timedelta(hours=2)), 
        1, 
        0
    )

    # --- CÁLCULO TMA REAL (DO TIME) ---
    df = df.sort_values(by=['Colaborador', 'Data_Completa'])
    df['Tempo_Ate_Proximo'] = df.groupby('Colaborador')['Data_Completa'].shift(-1) - df['Data_Completa']
    df['Minutos_No_Atendimento'] = df['Tempo_Ate_Proximo'].dt.total_seconds() / 60
    
    df['TMA_Valido'] = np.where(
        (df['Minutos_No_Atendimento'] > 0.5) & (df['Minutos_No_Atendimento'] <= 40),
        df['Minutos_No_Atendimento'],
        np.nan
    )

    return df

# --- BOTÃO DE REFRESH MANUAL ---
st.sidebar.title("Dashboard Operacional")
if st.sidebar.button("🔄 Atualizar Dados Agora"):
    st.cache_data.clear()
    st.rerun()

try:
    df_raw = load_data()
except Exception as e:
    st.error(f"Erro no processamento. Detalhe: {e}")
    st.stop()

# ==============================================================================
# 3. FILTROS & CONFIGURAÇÕES
# ==============================================================================
st.sidebar.header("🔍 Filtros")
st.sidebar.markdown("---")

min_date = df_raw['Data'].min().date()
max_date = df_raw['Data'].max().date()

date_range = st.sidebar.date_input(
    "Período",
    value=[min_date, max_date],
    min_value=min_date,
    max_value=max_date,
    format="DD/MM/YYYY"
)

if len(date_range) == 2:
    start_date, end_date = date_range
elif len(date_range) == 1:
    start_date, end_date = date_range[0], date_range[0]
else:
    start_date, end_date = min_date, max_date

num_dias_selecionados = (end_date - start_date).days + 1
if num_dias_selecionados < 1: num_dias_selecionados = 1

if 'Setor' in df_raw.columns:
    setores = st.sidebar.multiselect("Setor", options=sorted(df_raw['Setor'].unique()))
else: setores = []

colaboradores = st.sidebar.multiselect("Colaborador", options=sorted(df_raw['Colaborador'].unique()))
portais = st.sidebar.multiselect("Portal", options=sorted(df_raw['Portal'].unique()))
transportadoras = st.sidebar.multiselect("Transportadora", options=sorted([t for t in df_raw['Transportadora'].unique() if t not in ['-', 'Não Informado']]))

# Aplica Filtros
df_f = df_raw.copy()
df_f = df_f[(df_f['Data'].dt.date >= start_date) & (df_f['Data'].dt.date <= end_date)]

if setores: df_f = df_f[df_f['Setor'].isin(setores)]
if colaboradores: df_f = df_f[df_f['Colaborador'].isin(colaboradores)]
if portais: df_f = df_f[df_f['Portal'].isin(portais)]
if transportadoras: df_f = df_f[df_f['Transportadora'].isin(transportadoras)]

# ==============================================================================
# 4. LÓGICA DE METAS SEPARADAS (SAC / PENDÊNCIA)
# ==============================================================================
# Identifica colaboradores únicos por setor no filtro atual
colabs_sac = df_f[df_f['Setor'].str.contains('SAC', case=False, na=False)]['Colaborador'].nunique()
colabs_pend = df_f[df_f['Setor'].str.contains('PEND|ATRASO', case=False, na=False)]['Colaborador'].nunique()

# Meta Individual Diária (considerando ociosidade)
meta_ind_sac = int(TEMPO_UTIL_DIA / TMA_ALVO_SAC)
meta_ind_pend = int(TEMPO_UTIL_DIA / TMA_ALVO_PEND)

# Meta Total do Período (Meta Diária * Qtd Colaboradores * Qtd Dias)
meta_total_sac = meta_ind_sac * colabs_sac * num_dias_selecionados
meta_total_pend = meta_ind_pend * colabs_pend * num_dias_selecionados

# Realizado Total do Período
real_sac = df_f[df_f['Setor'].str.contains('SAC', case=False, na=False)]['Eh_Novo_Episodio'].sum()
real_pend = df_f[df_f['Setor'].str.contains('PEND|ATRASO', case=False, na=False)]['Eh_Novo_Episodio'].sum()

# Porcentagem de Atingimento
pct_sac = (real_sac / meta_total_sac * 100) if meta_total_sac > 0 else 0
pct_pend = (real_pend / meta_total_pend * 100) if meta_total_pend > 0 else 0

# ==============================================================================
# 5. DASHBOARD
# ==============================================================================
st.markdown("## 📊 Visão Geral Operacional")

k1, k2, k3, k4 = st.columns(4)

# KPI 1 e 2: Volumes Gerais
k1.metric("📦 Registros Brutos", f"{df_f.shape[0]}")
k2.metric("✅ Atendimentos (2h)", f"{df_f['Eh_Novo_Episodio'].sum()}")

# KPI 3: Meta SAC
k3.metric(
    "🎯 Meta SAC", 
    f"{real_sac} / {meta_total_sac}", 
    delta=f"{pct_sac:.1f}% realizado",
    delta_color="normal" if pct_sac >= 90 else "inverse"
)

# KPI 4: Meta Pendência
k4.metric(
    "🎯 Meta Pendência", 
    f"{real_pend} / {meta_total_pend}", 
    delta=f"{pct_pend:.1f}% realizado",
    delta_color="normal" if pct_pend >= 90 else "inverse"
)

st.markdown("---")

tab1, tab2, tab3 = st.tabs(["🚀 Produtividade & Capacidade", "🔥 Causa Raiz", "🕵️ Reincidência & Risco"])

# --- ABA 1: PRODUTIVIDADE ---
with tab1:
    st.subheader("1. Volume por Colaborador")
    df_vol = df_f.groupby('Colaborador').agg(Bruto=('Data','count'), Liquido=('Eh_Novo_Episodio','sum')).reset_index().sort_values('Liquido', ascending=True)
    fig_vol = px.bar(df_vol.melt(id_vars='Colaborador'), y='Colaborador', x='value', color='variable', 
                     barmode='group', orientation='h', color_discrete_map={'Bruto':'#FFA15A','Liquido':'#19D3F3'}, text_auto=True)
    st.plotly_chart(fig_vol, use_container_width=True)

    st.markdown("---")
    st.subheader("2. Projeção de Capacidade (Baseado no TMA Real)")
    
    # MANTIDO: Lógica original de projeção enviada no seu código
    df_perf = df_f.groupby(['Colaborador','Setor'])['TMA_Valido'].mean().reset_index()
    
    # Helper para aplicar a meta individual no gráfico de barras conforme o setor
    def get_meta_grafico(setor):
        if 'SAC' in str(setor).upper(): return meta_ind_sac
        return meta_ind_pend

    df_perf['Meta_Fixa'] = df_perf['Setor'].apply(get_meta_grafico)
    
    fig_cap = go.Figure()
    fig_cap.add_trace(go.Bar(x=df_perf['Colaborador'], y=df_perf['Meta_Fixa'], name="Capacidade Meta (Fixa)", marker_color='#00CC96', text_auto=True))
    fig_cap.add_trace(go.Scatter(x=df_perf['Colaborador'], y=df_perf['TMA_Valido'], name="TMA Real (min)", yaxis='y2', marker_color='#EF553B', mode='lines+markers'))
    
    fig_cap.update_layout(
        yaxis=dict(title="Capacidade Diária (Atendimentos)"), 
        yaxis2=dict(title="TMA (Minutos)", overlaying='y', side='right', range=[0,15]), 
        legend=dict(orientation="h", y=-0.2)
    )
    st.plotly_chart(fig_cap, use_container_width=True)

# --- ABA 2: CAUSA RAIZ ---
with tab2:
    def plot_matrix(x, y, title):
        df_m = df_f[(df_f[x] != 'Não Informado') & (df_f[y] != 'Não Informado')]
        if not df_m.empty:
            st.plotly_chart(px.imshow(pd.crosstab(df_m[y], df_m[x]), text_auto=True, color_continuous_scale='Reds', title=title), use_container_width=True)

    plot_matrix('Motivo', 'Portal', 'Matriz: Portal x Motivo')
    plot_matrix('Motivo', 'Transportadora', 'Matriz: Transportadora x Motivo')

# --- ABA 3: REINCIDÊNCIA ---
with tab3:
    st.subheader("🕵️ Risco de Cancelamento")
    df_reinc = df_f.sort_values('Data_Completa').groupby('ID_Ref').agg(
        Vezes=('Eh_Novo_Episodio','sum'),
        Ultimo_Motivo=('Motivo','last'),
        Historico=('Motivo', lambda x: " ➡️ ".join(x.astype(str))),
        Ultima_Data=('Data_Completa','max')
    ).reset_index()
    
    df_critico = df_reinc[df_reinc['Vezes'] > 1].sort_values('Vezes', ascending=False)
    
    risco_count = df_critico[df_critico['Ultimo_Motivo'].str.contains('Cancelamento', case=False, na=False)].shape[0]
    st.metric("Clientes Reincidentes Pedindo Cancelamento", f"{risco_count}", delta_color="inverse")

    csv = df_critico.to_csv(index=False, sep=';').encode('utf-8-sig')
    st.download_button("📥 Baixar Relatório (Excel)", data=csv, file_name='risco_cancelamento.csv', mime='text/csv')
    
    st.dataframe(df_critico, use_container_width=True, hide_index=True,
                 column_config={"Historico": st.column_config.TextColumn("Linha do Tempo (Evolução)", width="large")})
