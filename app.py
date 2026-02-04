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
st.set_page_config(page_title="Dashboard Operacional", page_icon="🚛", layout="wide")

# ==============================================================================
# 2. DEFINIÇÃO DE METAS (VALORES FORNECIDOS)
# ==============================================================================
# Conversão de MM:SS para minutos decimais
TMA_ALVO_SAC = 5 + (9/60)        # 5.15 min
TMA_ALVO_PENDENCIA = 5 + (53/60)  # 5.88 min
TMA_PADRAO = (TMA_ALVO_SAC + TMA_ALVO_PENDENCIA) / 2

# Cálculo de Tempo Útil: (11 horas * 60 min) * 0.70 (30% ociosidade)
TEMPO_UTIL_DIA = (11 * 60) * 0.70  # 462 minutos

# ==============================================================================
# 3. ETL & PROCESSAMENTO
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

    # Limpeza de strings
    cols_texto = ['Colaborador', 'Setor', 'Portal', 'Transportadora', 'Motivo', 'Motivo_CRM', 'Numero_Pedido', 'Nota_Fiscal']
    for col in cols_texto:
        if col in df.columns:
            df[col] = df[col].fillna("Não Informado").astype(str).str.strip()

    # Horários
    if 'Hora' in df.columns:
        df['Hora_Str'] = df['Hora'].astype(str)
    else:
        df['Hora_Str'] = df['Data'].dt.strftime('%H:%M:%S')

    df['Data_Completa'] = df['Data'] + pd.to_timedelta(df['Hora_Str'])
    
    # Lógica de Reincidência (2 horas)
    df = df.sort_values(by=['Numero_Pedido', 'Nota_Fiscal', 'Data_Completa'])
    df['ID_Ref'] = np.where(df['Numero_Pedido'] != "Não Informado", df['Numero_Pedido'], df['Nota_Fiscal'])
    df['Eh_Novo_Episodio'] = np.where(df.groupby('ID_Ref')['Data_Completa'].diff() > pd.Timedelta(hours=2), 1, 0)
    df.loc[df.groupby('ID_Ref').head(1).index, 'Eh_Novo_Episodio'] = 1

    # Cálculo TMA Real (Performance atual)
    df = df.sort_values(by=['Colaborador', 'Data_Completa'])
    df['TMA_Valido'] = df.groupby('Colaborador')['Data_Completa'].diff().shift(-1).dt.total_seconds() / 60
    df['TMA_Valido'] = np.where((df['TMA_Valido'] > 0.5) & (df['TMA_Valido'] <= 40), df['TMA_Valido'], np.nan)

    return df

df_raw = load_data()

# ==============================================================================
# 4. FILTROS LATERAIS (SEM CONTROLES DE META)
# ==============================================================================
st.sidebar.title("Dashboard Operacional")
if st.sidebar.button("🔄 Atualizar Dados"):
    st.cache_data.clear()
    st.rerun()

min_date, max_date = df_raw['Data'].min().date(), df_raw['Data'].max().date()
date_range = st.sidebar.date_input("Período", value=[min_date, max_date])

# Aplicação de filtros
df_filtered = df_raw.copy()
if len(date_range) == 2:
    df_filtered = df_filtered[(df_filtered['Data'].dt.date >= date_range[0]) & (df_filtered['Data'].dt.date <= date_range[1])]

colaboradores = st.sidebar.multiselect("Colaborador", options=sorted(df_filtered['Colaborador'].unique()))
if colaboradores: df_filtered = df_filtered[df_filtered['Colaborador'].isin(colaboradores)]

setores = st.sidebar.multiselect("Setor", options=sorted(df_filtered['Setor'].unique()))
if setores: df_filtered = df_filtered[df_filtered['Setor'].isin(setores)]

# ==============================================================================
# 5. LÓGICA DE METAS POR SETOR
# ==============================================================================
def get_meta_individual(setor):
    s = str(setor).upper()
    if 'SAC' in s: return int(TEMPO_UTIL_DIA / TMA_ALVO_SAC)
    if 'PEND' in s or 'ATRASO' in s: return int(TEMPO_UTIL_DIA / TMA_ALVO_PENDENCIA)
    return int(TEMPO_UTIL_DIA / TMA_PADRAO)

# Mapeia metas para cada colaborador ativo no filtro
df_colabs_ativos = df_filtered.groupby(['Colaborador', 'Setor']).size().reset_index()
df_colabs_ativos['Meta_Individual'] = df_colabs_ativos['Setor'].apply(get_meta_individual)

meta_total_dia = df_colabs_ativos['Meta_Individual'].sum()
total_liquido = df_filtered['Eh_Novo_Episodio'].sum()

# Cálculo de Dias Úteis no Filtro
dias_diff = (df_filtered['Data'].max() - df_filtered['Data'].min()).days + 1
real_medio_dia = total_liquido / dias_diff if dias_diff > 0 else 0

# ==============================================================================
# 6. VISUALIZAÇÃO
# ==============================================================================
st.markdown(f"## 📊 Visão Geral Operacional")

# KPIs
k1, k2, k3 = st.columns(3)
k1.metric("✅ Atendimentos Reais", f"{total_liquido}")
k2.metric("🎯 Meta Diária do Time (Fixa)", f"{meta_total_dia}")

pacing = (real_medio_dia / meta_total_dia) * 100 if meta_total_dia > 0 else 0
k3.metric("📈 Atingimento da Meta", f"{pacing:.1f}%", 
          delta="Dentro do esperado" if pacing >= 90 else "Abaixo da meta",
          delta_color="normal" if pacing >= 90 else "inverse")

tab1, tab2 = st.tabs(["🚀 Performance", "🔎 Detalhes por Colaborador"])

with tab1:
    # Gráfico de Capacidade vs TMA Real
    df_perf = df_filtered.groupby(['Colaborador', 'Setor'])['TMA_Valido'].mean().reset_index()
    df_perf['Meta_Fixa'] = df_perf['Setor'].apply(get_meta_individual)
    
    fig = go.Figure()
    # Barra da Meta (Fixa baseada no setor)
    fig.add_trace(go.Bar(
        x=df_perf['Colaborador'], y=df_perf['Meta_Fixa'],
        name="Meta (Base Setor)", marker_color='#00CC96', text=df_perf['Meta_Fixa'], textposition='outside'
    ))
    # Linha do TMA Real (Velocidade deles)
    fig.add_trace(go.Scatter(
        x=df_perf['Colaborador'], y=df_perf['TMA_Valido'],
        name="TMA Real (min)", yaxis='y2', marker_color='#EF553B', mode='lines+markers'
    ))

    fig.update_layout(
        title="Capacidade Requerida vs Velocidade Real",
        yaxis=dict(title="Meta de Atendimentos (Qtd)"),
        yaxis2=dict(title="TMA Real (Minutos)", overlaying='y', side='right', range=[0, 15]),
        legend=dict(orientation="h", y=-0.2)
    )
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.write("### Tabela de Referência de Metas")
    st.dataframe(df_colabs_ativos[['Colaborador', 'Setor', 'Meta_Individual']], use_container_width=True)
    st.caption(f"Configuração: SAC ({TMA_ALVO_SAC:.2f} min) | Pendência ({TMA_ALVO_PENDENCIA:.2f} min) | Ociosidade: 30%")
