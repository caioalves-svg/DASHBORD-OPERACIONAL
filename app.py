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

# --- PARÂMETROS FIXOS (DEFINIDOS POR VOCÊ) ---
TMA_ALVO_SAC = 5 + (9/60)         # 05:09 -> 5.15 min
TMA_ALVO_PEND = 5 + (53/60)       # 05:53 -> 5.88 min
HORA_OPERACIONAL_INICIO = 7       # 07:00
HORA_OPERACIONAL_FIM = 18         # 18:00
# (11 horas * 60 min) * 0.70 (30% ociosidade) = 462 min produtivos/dia
TEMPO_UTIL_DIA = ((HORA_OPERACIONAL_FIM - HORA_OPERACIONAL_INICIO) * 60) * 0.70 

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
    else:
        df['Hora_Str'] = df['Data'].dt.strftime('%H:%M:%S')

    try:
        df['Data_Completa'] = df['Data'] + pd.to_timedelta(df['Hora_Str'])
    except:
        df['Data_Completa'] = df['Data']

    df['Hora_Cheia'] = df['Data_Completa'].dt.hour.astype(str).str.zfill(2) + ":00"
    df['Dia_Semana'] = df['Data'].dt.day_name() # Nome do dia em inglês para ordenação de heatmap posterior se necessário

    # ID Ref
    df['ID_Ref'] = np.where(df['Numero_Pedido'] != "Não Informado", df['Numero_Pedido'], df['Nota_Fiscal'])
    df['ID_Ref'] = df['ID_Ref'].astype(str)
    
    # --- LÓGICA 2 HORAS (REINCIDÊNCIA) ---
    df = df.sort_values(by=['ID_Ref', 'Data_Completa'])
    df['Tempo_Desde_Ultimo_Contato'] = df.groupby('ID_Ref')['Data_Completa'].diff()
    df['Eh_Novo_Episodio'] = np.where((df['Tempo_Desde_Ultimo_Contato'].isnull()) | (df['Tempo_Desde_Ultimo_Contato'] > pd.Timedelta(hours=2)), 1, 0)

    # --- TMA REAL (PERFORMANCE) ---
    df = df.sort_values(by=['Colaborador', 'Data_Completa'])
    df['Tempo_Ate_Proximo'] = df.groupby('Colaborador')['Data_Completa'].shift(-1) - df['Data_Completa']
    df['Minutos_No_Atendimento'] = df['Tempo_Ate_Proximo'].dt.total_seconds() / 60
    df['TMA_Valido'] = np.where((df['Minutos_No_Atendimento'] > 0.5) & (df['Minutos_No_Atendimento'] <= 40), df['Minutos_No_Atendimento'], np.nan)

    return df

# --- REFRESH ---
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
# 3. FILTROS
# ==============================================================================
st.sidebar.header("🔍 Filtros")
min_date, max_date = df_raw['Data'].min().date(), df_raw['Data'].max().date()
date_range = st.sidebar.date_input("Período", value=[min_date, max_date], format="DD/MM/YYYY")

if len(date_range) == 2: s_date, e_date = date_range
elif len(date_range) == 1: s_date = e_date = date_range[0]
else: s_date, e_date = min_date, max_date

num_dias = (e_date - s_date).days + 1
if num_dias < 1: num_dias = 1

df_filtered = df_raw[(df_raw['Data'].dt.date >= s_date) & (df_raw['Data'].dt.date <= e_date)]

if 'Setor' in df_filtered.columns:
    setores = st.sidebar.multiselect("Setor", options=sorted(df_filtered['Setor'].unique()))
    if setores: df_filtered = df_filtered[df_filtered['Setor'].isin(setores)]

colaboradores = st.sidebar.multiselect("Colaborador", options=sorted(df_filtered['Colaborador'].unique()))
if colaboradores: df_filtered = df_filtered[df_filtered['Colaborador'].isin(colaboradores)]

portais = st.sidebar.multiselect("Portal", options=sorted(df_filtered['Portal'].unique()))
if portais: df_filtered = df_filtered[df_filtered['Portal'].isin(portais)]

transportadoras = st.sidebar.multiselect("Transportadora", options=sorted(df_filtered['Transportadora'].unique()))
if transportadoras: df_filtered = df_filtered[df_filtered['Transportadora'].isin(transportadoras)]

# ==============================================================================
# 4. DASHBOARD & KPIS (META FIXA)
# ==============================================================================
st.markdown("## 📊 Visão Geral") 

total_bruto = df_filtered.shape[0]
total_liquido = df_filtered['Eh_Novo_Episodio'].sum()
taxa_duplicidade = ((total_bruto - total_liquido) / total_bruto * 100) if total_bruto > 0 else 0

# --- LÓGICA DE META SETORIAL ---
def calc_meta_setor(setor):
    s = str(setor).upper()
    if 'SAC' in s: return int(TEMPO_UTIL_DIA / TMA_ALVO_SAC)
    if 'PEND' in s or 'ATRASO' in s: return int(TEMPO_UTIL_DIA / TMA_ALVO_PEND)
    return int(TEMPO_UTIL_DIA / ((TMA_ALVO_SAC + TMA_ALVO_PEND)/2))

df_ativos = df_filtered.groupby(['Colaborador', 'Setor']).size().reset_index()
df_ativos['Meta_Individual'] = df_ativos['Setor'].apply(calc_meta_setor)
meta_total_dia = df_ativos['Meta_Individual'].sum()

real_medio_dia = int(total_liquido / num_dias)
percentual_entregue = (real_medio_dia / meta_total_dia * 100) if meta_total_dia > 0 else 0

# PACING (Ritmo 07h-18h)
fuso_br = pytz.timezone('America/Sao_Paulo')
agora = datetime.now(fuso_br)
if e_date < agora.date(): progresso_esp = 100.0
elif s_date > agora.date(): progresso_esp = 0.0
else:
    h = agora.hour + (agora.minute/60)
    progresso_esp = max(0, min(100, ((h - HORA_OPERACIONAL_INICIO) / (HORA_OPERACIONAL_FIM - HORA_OPERACIONAL_INICIO)) * 100))

cor_ritmo = "normal" if percentual_entregue >= progresso_esp else "inverse"

k1, k2, k3, k4 = st.columns(4)
k1.metric("📦 Registros Brutos", f"{total_bruto}")
k2.metric("✅ Atendimentos (2h)", f"{total_liquido}")
k3.metric("⚠️ Duplicidade", f"{taxa_duplicidade:.1f}%", delta_color="inverse")
k4.metric("🎯 Meta Diária (Fixa)", f"{meta_total_dia}", 
          delta=f"{percentual_entregue:.1f}% entregue", delta_color=cor_ritmo,
          help=f"Meta: SAC ({TMA_ALVO_SAC:.2f}m) | Pend ({TMA_ALVO_PEND:.2f}m)\nOciosidade aplicada: 30%")

st.markdown("---")
tab1, tab2, tab3 = st.tabs(["🚀 Produtividade & Capacidade", "🔥 Causa Raiz", "🕵️ Reincidência & Risco"])

# --- ABA 1: PRODUTIVIDADE ---
with tab1:
    st.subheader("1. Volume por Colaborador (Bruto vs Líquido)")
    df_vol = df_filtered.groupby('Colaborador').agg(Bruto=('Data','count'), Liquido=('Eh_Novo_Episodio','sum')).reset_index().sort_values('Liquido')
    fig_vol = px.bar(df_vol.melt(id_vars='Colaborador'), y='Colaborador', x='value', color='variable', barmode='group', orientation='h', text_auto=True)
    st.plotly_chart(fig_vol, use_container_width=True)

    st.markdown("---")
    st.subheader("2. Meta Fixa vs TMA Real")
    df_perf = df_filtered.groupby(['Colaborador','Setor'])['TMA_Valido'].mean().reset_index()
    df_perf['Meta_Fixa'] = df_perf['Setor'].apply(calc_meta_setor)
    
    fig_cap = go.Figure()
    fig_cap.add_trace(go.Bar(x=df_perf['Colaborador'], y=df_perf['Meta_Fixa'], name='Meta (Fixa)', marker_color='#00CC96', text_auto=True))
    fig_cap.add_trace(go.Scatter(x=df_perf['Colaborador'], y=df_perf['TMA_Valido'], name='TMA Real (min)', yaxis='y2', marker_color='#EF553B', mode='lines+markers'))
    fig_cap.update_layout(yaxis=dict(title='Capacidade Meta'), yaxis2=dict(title='TMA (Min)', overlaying='y', side='right', range=[0,15]), legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig_cap, use_container_width=True)

# --- ABA 2: CAUSA RAIZ ---
with tab2:
    def matrix(col_x, col_y, title):
        df_m = df_filtered[(df_filtered[col_x] != 'Não Informado') & (df_filtered[col_y] != 'Não Informado')]
        if not df_m.empty:
            st.plotly_chart(px.imshow(pd.crosstab(df_m[col_y], df_m[col_x]), text_auto=True, color_continuous_scale='Reds', title=title), use_container_width=True)
    matrix('Motivo', 'Portal', 'Matriz: Portal x Motivo')
    matrix('Motivo', 'Transportadora', 'Matriz: Transportadora x Motivo')

# --- ABA 3: REINCIDÊNCIA ---
with tab3:
    st.subheader("🕵️ Análise de Risco de Cancelamento")
    df_reinc = df_filtered.sort_values('Data_Completa').groupby('ID_Ref').agg(
        Vezes=('Eh_Novo_Episodio','sum'),
        Ultimo_Motivo=('Motivo','last'),
        Historico_Completo=('Motivo', lambda x: " ➡️ ".join(x.astype(str))),
        Ultima_Data=('Data_Completa','max')
    ).reset_index()
    
    df_critico = df_reinc[df_reinc['Vezes'] > 1].sort_values('Vezes', ascending=False)
    
    risco_count = df_critico[df_critico['Ultimo_Motivo'].str.contains('Cancelamento', case=False, na=False)].shape[0]
    st.metric("Clientes Reincidentes em Risco Crítico", f"{risco_count}", delta="Atenção Prioritária", delta_color="inverse")

    st.download_button("📥 Baixar Relatório (Excel)", data=df_critico.to_csv(index=False, sep=';').encode('utf-8-sig'), file_name='risco.csv', mime='text/csv')
    st.dataframe(df_critico, use_container_width=True, hide_index=True, column_config={"Historico_Completo": st.column_config.TextColumn("Histórico Cronológico", width="large")})
