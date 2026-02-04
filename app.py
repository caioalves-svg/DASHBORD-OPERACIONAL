import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection
import pytz

# ==============================================================================
# 1. CONFIGURAÇÕES E METAS FIXAS
# ==============================================================================
st.set_page_config(page_title="Dashboard Operacional", page_icon="🚛", layout="wide")

# Parâmetros solicitados
TMA_SAC = 5 + (9/60)        # 05:09 em minutos decimais
TMA_PEND = 5 + (53/60)      # 05:53 em minutos decimais
TMA_PADRAO = (TMA_SAC + TMA_PEND) / 2
HORA_INICIO = 7
HORA_FIM = 18
TEMPO_UTIL_DIA = ((HORA_FIM - HORA_INICIO) * 60) * 0.70 # 462 min (30% ociosidade)

st.markdown("""
<style>
    .metric-card { background-color: #f0f2f6; border-radius: 10px; padding: 15px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); }
    [data-testid="stMetricValue"] { font-size: 24px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. ETL (INTELIGÊNCIA DE DADOS)
# ==============================================================================
@st.cache_data(ttl=600)
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df = conn.read(worksheet="Página1")
    except:
        df = conn.read()

    df['Data'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['Data'])

    cols_texto = ['Colaborador', 'Setor', 'Portal', 'Transportadora', 'Motivo', 'Motivo_CRM', 'Numero_Pedido', 'Nota_Fiscal']
    for col in cols_texto:
        if col in df.columns:
            df[col] = df[col].fillna("Não Informado").astype(str).str.strip().str.replace(';', ',').str.replace('\n', ' ')

    if 'Hora' in df.columns:
        df['Hora_Str'] = df['Hora'].astype(str)
        df['Hora_Cheia'] = df['Hora_Str'].str.slice(0, 2) + ":00"
    else:
        df['Hora_Cheia'] = df['Data'].dt.hour.astype(str).str.zfill(2) + ":00"
        df['Hora_Str'] = df['Data'].dt.strftime('%H:%M:%S')

    df['Data_Completa'] = df['Data'] + pd.to_timedelta(df['Hora_Str'])
    df['Dia_Semana'] = df['Data'].dt.day_name() # Ajuste simples para dia

    # Chave Única e ID Ref
    df['ID_Ref'] = np.where(df['Numero_Pedido'] != "Não Informado", df['Numero_Pedido'], df['Nota_Fiscal'])
    df['ID_Ref'] = df['ID_Ref'].astype(str)
    
    # LÓGICA REINCIDÊNCIA 2 HORAS
    df = df.sort_values(by=['ID_Ref', 'Data_Completa'])
    df['Eh_Novo_Episodio'] = np.where(df.groupby('ID_Ref')['Data_Completa'].diff() > pd.Timedelta(hours=2), 1, 0)
    df.loc[df.groupby('ID_Ref').head(1).index, 'Eh_Novo_Episodio'] = 1

    # CÁLCULO TMA REAL (PROJEÇÃO)
    df = df.sort_values(by=['Colaborador', 'Data_Completa'])
    df['TMA_Valido'] = df.groupby('Colaborador')['Data_Completa'].diff().shift(-1).dt.total_seconds() / 60
    df['TMA_Valido'] = np.where((df['TMA_Valido'] > 0.5) & (df['TMA_Valido'] <= 40), df['TMA_Valido'], np.nan)

    return df

df_raw = load_data()

# ==============================================================================
# 3. FILTROS
# ==============================================================================
st.sidebar.title("🚛 Dashboard Pro")
if st.sidebar.button("🔄 Atualizar Dados"):
    st.cache_data.clear()
    st.rerun()

min_date, max_date = df_raw['Data'].min().date(), df_raw['Data'].max().date()
date_range = st.sidebar.date_input("Período", [min_date, max_date])

# Tratamento data única ou range
if len(date_range) == 2: s_date, e_date = date_range
else: s_date = e_date = date_range[0]

num_dias = (e_date - s_date).days + 1

df_f = df_raw[(df_raw['Data'].dt.date >= s_date) & (df_raw['Data'].dt.date <= e_date)]

# Filtros dinâmicos
def multiselect_filter(label, col):
    vals = sorted(df_f[col].unique())
    sel = st.sidebar.multiselect(label, vals)
    return df_f[df_f[col].isin(sel)] if sel else df_f

df_f = multiselect_filter("Setor", "Setor")
df_f = multiselect_filter("Colaborador", "Colaborador")
df_f = multiselect_filter("Portal", "Portal")
df_f = multiselect_filter("Transportadora", "Transportadora")

# ==============================================================================
# 4. CÁLCULOS DE CAPACIDADE (METAS FIXAS)
# ==============================================================================
def get_meta_indiv(setor):
    s = str(setor).upper()
    if 'SAC' in s: return int(TEMPO_UTIL_DIA / TMA_SAC)
    if 'PEND' in s or 'ATRASO' in s: return int(TEMPO_UTIL_DIA / TMA_PEND)
    return int(TEMPO_UTIL_DIA / TMA_PADRAO)

df_ativos = df_f.groupby(['Colaborador', 'Setor']).size().reset_index()
df_ativos['Meta_Fixa'] = df_ativos['Setor'].apply(get_meta_indiv)

meta_total_time = df_ativos['Meta_Fixa'].sum()
total_bruto = df_f.shape[0]
total_liquido = df_f['Eh_Novo_Episodio'].sum()
real_medio_dia = total_liquido / num_dias if num_dias > 0 else 0

# PACING (07h - 18h)
fuso = pytz.timezone('America/Sao_Paulo')
agora = datetime.now(fuso)
if e_date < agora.date(): progresso = 100.0
elif s_date > agora.date(): progresso = 0.0
else:
    h = agora.hour + (agora.minute/60)
    progresso = max(0, min(100, ((h - HORA_INICIO) / (HORA_FIM - HORA_INICIO)) * 100))

atingimento = (real_medio_dia / meta_total_time * 100) if meta_total_time > 0 else 0
cor_ritmo = "normal" if atingimento >= progresso else "inverse"

# ==============================================================================
# 5. LAYOUT E DASHBOARD
# ==============================================================================
st.markdown("## 📊 Visão Geral Operacional")

c1, c2, c3, c4 = st.columns(4)
c1.metric("📦 Registros Brutos", f"{total_bruto}")
c2.metric("✅ Atendimentos (2h)", f"{total_liquido}")
c3.metric("⚠️ Duplicidade", f"{((total_bruto-total_liquido)/total_bruto*100):.1f}%" if total_bruto>0 else "0%")
c4.metric("🎯 Meta Diária (Fixa)", f"{meta_total_time}", 
          delta=f"{atingimento:.1f}% entregue", delta_color=cor_ritmo)

tab1, tab2, tab3 = st.tabs(["🚀 Produtividade", "🔥 Causa Raiz", "🕵️ Reincidência & Risco"])

# --- ABA 1: PRODUTIVIDADE ---
with tab1:
    st.subheader("Volume por Colaborador")
    df_vol = df_f.groupby('Colaborador').agg(Bruto=('Data','count'), Liquido=('Eh_Novo_Episodio','sum')).reset_index()
    fig_vol = px.bar(df_vol.melt(id_vars='Colaborador'), y='Colaborador', x='value', color='variable', 
                     barmode='group', orientation='h', color_discrete_map={'Bruto':'#FFA15A','Liquido':'#19D3F3'}, text_auto=True)
    st.plotly_chart(fig_vol, use_container_width=True)

    st.markdown("---")
    st.subheader("Meta Fixa vs TMA Real")
    df_perf = df_f.groupby(['Colaborador','Setor'])['TMA_Valido'].mean().reset_index()
    df_perf['Meta_Fixa'] = df_perf['Setor'].apply(get_meta_indiv)
    
    fig_cap = go.Figure()
    fig_cap.add_trace(go.Bar(x=df_perf['Colaborador'], y=df_perf['Meta_Fixa'], name="Meta (Fixa)", marker_color='#00CC96'))
    fig_cap.add_trace(go.Scatter(x=df_perf['Colaborador'], y=df_perf['TMA
