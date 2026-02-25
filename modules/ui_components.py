import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

def load_css():
    with open("modules/styles.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

def render_sidebar_filters(df_raw):
    st.sidebar.header("🔍 Filtros")
    st.sidebar.markdown("---")

    min_date = df_raw['Data'].min().date()
    max_date = max(df_raw['Data'].max().date(), datetime.now().date())
    today = datetime.now().date()

    # Lógica de dia atual
    default_val = [min_date, min_date] if today < min_date else [today, today]

    date_range = st.sidebar.date_input("Período", value=default_val, min_value=min_date, max_value=max_date, format="DD/MM/YYYY")
    
    if len(date_range) == 2:
        start, end = date_range
    elif len(date_range) == 1:
        start, end = date_range[0], date_range[0]
    else:
        start, end = today, today

    # Filtros de Lista
    setores = st.sidebar.multiselect("Setor", options=sorted(df_raw['Setor'].unique())) if 'Setor' in df_raw.columns else []
    colaboradores = st.sidebar.multiselect("Colaborador", options=sorted(df_raw['Colaborador'].unique()))
    portais = st.sidebar.multiselect("Portal", options=sorted(df_raw['Portal'].unique()))
    transportadoras = st.sidebar.multiselect("Transportadora", options=sorted([t for t in df_raw['Transportadora'].unique() if t not in ['-', 'Não Informado']]))

    # Aplica Filtros
    df = df_raw.copy()
    df = df[(df['Data'].dt.date >= start) & (df['Data'].dt.date <= end)]
    if setores: df = df[df['Setor'].isin(setores)]
    if colaboradores: df = df[df['Colaborador'].isin(colaboradores)]
    if portais: df = df[df['Portal'].isin(portais)]
    if transportadoras: df = df[df['Transportadora'].isin(transportadoras)]

    return df, end

def render_kpis(df, df_metas, end_date):
    total_bruto = df.shape[0]
    total_liquido = df['Eh_Novo_Episodio'].sum()
    taxa_duplicidade = ((total_bruto - total_liquido) / total_bruto * 100) if total_bruto > 0 else 0

    k1, k2, k3 = st.columns(3)
    k1.metric("📦 Total Registros (Bruto)", f"{total_bruto}")
    k2.metric("✅ Atendimentos Reais (2h)", f"{total_liquido}")
    k3.metric("⚠️ Taxa de Duplicidade", f"{taxa_duplicidade:.1f}%", delta_color="inverse")

    st.markdown("---")
    return total_liquido

def render_productivity_charts(df):
    # Gráfico 1: Volume
    st.subheader("1. Volume de Atendimento (Bruto vs Líquido)")
    df_vol = df.groupby('Colaborador').agg(
        Bruto=('Data', 'count'),
        Liquido=('Eh_Novo_Episodio', 'sum'),
        Erros_CRM=('Motivo_CRM', lambda x: x.isin(['SEM ABERTURA DE CRM', 'Não Informado']).sum())
    ).reset_index().sort_values('Liquido', ascending=True)
    
    df_melt = df_vol.melt(id_vars=['Colaborador', 'Erros_CRM'], value_vars=['Bruto', 'Liquido'], var_name='Métrica', value_name='Volume')
    max_vol = df_melt['Volume'].max()
    
    fig = px.bar(df_melt, y='Colaborador', x='Volume', color='Métrica', barmode='group', orientation='h',
                 color_discrete_map={'Bruto': '#FFA15A', 'Liquido': '#19D3F3'}, text='Volume',
                 hover_data={'Erros_CRM': True, 'Métrica': True, 'Volume': True, 'Colaborador': False})
    fig.update_traces(textposition='outside')
    fig.update_layout(height=450, margin=dict(r=50), xaxis=dict(range=[0, max_vol * 1.15]), legend=dict(orientation="h", y=-0.15))
    st.plotly_chart(fig, use_container_width=True)

def render_capacity_chart(df):
    st.subheader("2. Projeção de Capacidade (Meta vs Real)")
    
    df_tma = df.groupby('Colaborador')['TMA_Valido'].agg(['mean', 'count']).reset_index()
    df_tma.columns = ['Colaborador', 'TMA_Medio', 'Amostra']
    df_tma = df_tma[df_tma['Amostra'] > 5] 
    
    # Dia Cheio: 07:30 a 17:18 = 9.8h -> 588 min * 0.7 = 411.6
    TEMPO_UTIL = (17.3 - 7.5) * 60 * 0.70
    
    df_tma['Capacidade_Diaria'] = (TEMPO_UTIL / df_tma['TMA_Medio']).fillna(0).astype(int)
    df_tma = df_tma.sort_values('Capacidade_Diaria', ascending=False)
    max_cap = df_tma['Capacidade_Diaria'].max() if not df_tma.empty else 100

    fig = go.Figure()
    fig.add_trace(go.Bar(x=df_tma['Colaborador'], y=df_tma['Capacidade_Diaria'], name='Capacidade Projetada', marker_color='#00CC96', text=df_tma['Capacidade_Diaria'], textposition='outside'))
    fig.add_trace(go.Scatter(x=df_tma['Colaborador'], y=df_tma['TMA_Medio'], mode='lines+markers+text', name='TMA Atual (min)', marker=dict(color='#EF553B'), line=dict(color='#EF553B'), text=df_tma['TMA_Medio'].apply(lambda x: f"{x:.1f}'"), textposition='top center', yaxis='y2'))
    
    fig.update_layout(height=450, yaxis=dict(title='Capacidade', range=[0, max_cap * 1.25]), yaxis2=dict(title='TMA (min)', overlaying='y', side='right', showgrid=False), legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig, use_container_width=True)
