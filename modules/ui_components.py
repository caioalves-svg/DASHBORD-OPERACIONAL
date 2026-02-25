import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

# TEMA GLOBAL
THEME = {
    'primary': '#6366f1',    # Roxo
    'secondary': '#10b981',  # Verde
    'grid': '#e5e7eb',
    'text': '#1f2937'
}

TITLE_FONT = dict(size=18, color=THEME['text'], family="Inter, sans-serif")

def load_css():
    try:
        with open("modules/styles.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except: pass

def render_header():
    st.markdown(f"""
        <div class="custom-header">
            <div class="header-title">Monitoramento Operacional</div>
            <div style="font-size: 2rem;">🚛</div>
        </div>
    """, unsafe_allow_html=True)

def render_sidebar_filters(df_raw):
    st.sidebar.markdown("### 🎛️ Filtros")
    min_date = df_raw['Data'].min().date()
    try: max_val = df_raw['Data'].max().date()
    except: max_val = datetime.now().date()
    max_date = max(max_val, datetime.now().date())
    today = datetime.now().date()
    
    default_val = [today, today] if today >= min_date else [min_date, min_date]
    date_range = st.sidebar.date_input("Período", value=default_val, min_value=min_date, max_value=max_date, format="DD/MM/YYYY")
    
    if isinstance(date_range, (list, tuple)):
        start, end = (date_range[0], date_range[0]) if len(date_range) == 1 else date_range
    else:
        start, end = date_range, date_range

    setores = st.sidebar.multiselect("Setor", options=sorted(df_raw['Setor'].unique()))
    colaboradores = st.sidebar.multiselect("Colaborador", options=sorted(df_raw['Colaborador'].unique()))
    
    df = df_raw.copy()
    df = df[(df['Data'].dt.date >= start) & (df['Data'].dt.date <= end)]
    if setores: df = df[df['Setor'].isin(setores)]
    if colaboradores: df = df[df['Colaborador'].isin(colaboradores)]
    return df, end

def render_gauges(perc_sac, perc_pend):
    def create_gauge(value, title, color):
        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = min(value, 100),
            title = {'text': title, 'font': {'size': 15, 'color': '#6b7280'}},
            number = {'suffix': "%", 'font': {'size': 24, 'color': '#1f2937'}},
            gauge = {
                'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "rgba(0,0,0,0)"},
                'bar': {'color': color},
                'bgcolor': "rgba(0,0,0,0)",
                'borderwidth': 0,
                'steps': [{'range': [0, 100], 'color': "#f3f4f6"}]
            }
        ))
        fig.update_layout(height=180, margin=dict(l=30, r=30, t=50, b=10), paper_bgcolor='rgba(0,0,0,0)')
        return fig

    st.markdown("<h4 style='margin-bottom:-20px; color:#1f2937;'>🎯 Metas</h4>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(create_gauge(perc_sac, "SAC", THEME['secondary'] if perc_sac >= 100 else THEME['primary']), use_container_width=True)
    with c2:
        st.plotly_chart(create_gauge(perc_pend, "Pendência", THEME['secondary'] if perc_pend >= 100 else "#f59e0b"), use_container_width=True)

def render_main_bar_chart(df):
    if df.empty: return st.info("Sem dados.")
    df_vol = df.groupby('Colaborador').agg(Bruto=('Data', 'count'), Liquido=('Eh_Novo_Episodio', 'sum')).reset_index().sort_values('Liquido', ascending=True)
    df_melt = df_vol.melt(id_vars='Colaborador', var_name='Tipo', value_name='Volume')
    
    fig = px.bar(df_melt, y='Colaborador', x='Volume', color='Tipo', orientation='h', barmode='group',
                 color_discrete_map={'Bruto': '#e0e7ff', 'Liquido': THEME['primary']}, text='Volume')
    
    fig.update_traces(textposition='outside', marker_cornerradius=4)
    fig.update_layout(
        title=dict(text="📊 Performance Individual", font=TITLE_FONT, x=0.01, y=0.97),  # y ajustado
        height=450,
        xaxis=dict(showgrid=False), 
        yaxis=dict(title=None),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=None),
        plot_bgcolor='rgba(0,0,0,0)', 
        paper_bgcolor='rgba(0,0,0,0)', 
        margin=dict(l=10, r=10, t=110, b=10)  # t aumentado de 90 → 110
    )
    st.plotly_chart(fig, use_container_width=True)

def render_capacity_scatter(df):
    if df.empty: return
    df_tma = df.groupby('Colaborador')['TMA_Valido'].agg(['mean', 'count']).reset_index()
    df_tma.columns = ['Colaborador', 'mean', 'Amostra']
    df_tma = df_tma[df_tma['Amostra'] > 5]
    TEMPO_UTIL = (17.3 - 7.5) * 60 * 0.70
    df_tma['Capacidade'] = (TEMPO_UTIL / df_tma['mean']).fillna(0).astype(int)
    df_tma = df_tma.sort_values('Capacidade', ascending=False)
    
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df_tma['Colaborador'], y=df_tma['Capacidade'], name='Capacidade', marker_color='#d1fae5', marker_line_color=THEME['secondary'], marker_line_width=1, text=df_tma['Capacidade'], textposition='outside'))
    fig.add_trace(go.Scatter(x=df_tma['Colaborador'], y=df_tma['mean'], mode='markers+lines', name='TMA Real', yaxis='y2', line=dict(color='#ef4444', width=3), marker=dict(size=8, color='white', line=dict(width=2, color='#ef4444'))))
    
    fig.update_layout(
        title=dict(text="⚡ Capacidade vs Realizado (TMA)", font=TITLE_FONT, x=0.01, y=0.97),
        height=400,
        yaxis=dict(title='Atendimentos', showgrid=True, gridcolor=THEME['grid']),
        yaxis2=dict(title='TMA (min)', overlaying='y', side='right', showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5, title=None),
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=10, r=10, t=120, b=10)
    )
    st.plotly_chart(fig, use_container_width=True)

def render_evolution_chart(df):
    if df.empty: return
    df_line = df.groupby('Hora_Cheia').size().reset_index(name='Volume').sort_values('Hora_Cheia')
    fig = px.area(df_line, x='Hora_Cheia', y='Volume', markers=True)
    fig.update_traces(line=dict(color=THEME['primary'], shape='spline'), fillcolor='rgba(99, 102, 241, 0.1)')
    fig.update_layout(
        title=dict(text="📈 Fluxo Horário", font=TITLE_FONT, x=0.01, y=0.97),
        height=320,
        xaxis=dict(showgrid=False, title=None),
        yaxis=dict(showgrid=True, gridcolor=THEME['grid'], title=None),
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=10, r=10, t=90, b=10)
    )
    st.plotly_chart(fig, use_container_width=True)

def render_heatmap_clean(df):
    dias = ['Segunda-Feira', 'Terça-Feira', 'Quarta-Feira', 'Quinta-Feira', 'Sexta-Feira']
    df_heat = df[df['Dia_Semana'].isin(dias)]
    if df_heat.empty: return
    df_grp = df_heat.groupby(['Dia_Semana', 'Hora_Cheia']).size().reset_index(name='Chamados')
    fig = px.density_heatmap(df_grp, x='Dia_Semana', y='Hora_Cheia', z='Chamados', color_continuous_scale='Purples', text_auto=True)
    fig.update_layout(
        title=dict(text="🔥 Mapa de Calor Semanal", font=TITLE_FONT, x=0.01, y=0.97),
        height=320, coloraxis_showscale=False,
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=10, r=10, t=90, b=10)
    )
    st.plotly_chart(fig, use_container_width=True)
