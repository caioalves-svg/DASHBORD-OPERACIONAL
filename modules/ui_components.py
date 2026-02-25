import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

# CONFIGURAÇÃO DE CORES
THEME = {
    'primary': '#6366f1',
    'bg_chart': 'rgba(0,0,0,0)',
    'grid': '#f3f4f6'
}

def load_css():
    try:
        with open("modules/styles.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning("CSS não encontrado.")

def render_header():
    st.markdown("""
        <div class="custom-header">
            <div>
                <div class="header-title">Monitoramento Operacional</div>
                <div class="header-subtitle">Performance em Tempo Real • Logística & SAC</div>
            </div>
            <div style="font-size: 2rem;">🚛</div>
        </div>
    """, unsafe_allow_html=True)

def kpi_card_new(title, value, delta=None, delta_type="neutral", icon="📊"):
    delta_html = f"<div class='metric-delta delta-{delta_type}'>{delta}</div>" if delta else ""
    html = f"""
    <div class="metric-container">
        <div style="display:flex; justify-content:space-between;">
            <div class="metric-label">{title}</div>
            <div style="opacity:0.6;">{icon}</div>
        </div>
        <div class="metric-value">{value}</div>
        {delta_html}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def render_sidebar_filters(df_raw):
    st.sidebar.markdown("### 🎛️ Controles")
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

    st.sidebar.markdown("---")
    setores = st.sidebar.multiselect("Setor", options=sorted(df_raw['Setor'].unique())) if 'Setor' in df_raw.columns else []
    colaboradores = st.sidebar.multiselect("Colaborador", options=sorted(df_raw['Colaborador'].unique()))
    
    df = df_raw.copy()
    df = df[(df['Data'].dt.date >= start) & (df['Data'].dt.date <= end)]
    if setores: df = df[df['Setor'].isin(setores)]
    if colaboradores: df = df[df['Colaborador'].isin(colaboradores)]
    return df, end

# --- GRÁFICOS (SEM CONTAINER HTML MANUAL) ---

def render_gauges(perc_sac, perc_pend):
    def create_gauge(value, title, color):
        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = min(value, 100),
            title = {'text': title, 'font': {'size': 14, 'color': '#6b7280'}},
            number = {'suffix': "%", 'font': {'size': 26, 'color': '#1f2937'}},
            gauge = {'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "white"},
                     'bar': {'color': color},
                     'bgcolor': "white",
                     'borderwidth': 0, # Remove borda interna
                     'steps': [{'range': [0, 100], 'color': "#f3f4f6"}]}
        ))
        fig.update_layout(height=160, margin=dict(l=20, r=20, t=30, b=10), paper_bgcolor='rgba(0,0,0,0)')
        return fig

    c1, c2 = st.columns(2)
    with c1:
        color = "#10b981" if perc_sac >= 100 else "#6366f1"
        st.plotly_chart(create_gauge(perc_sac, "Meta SAC", color), use_container_width=True)
    with c2:
        color = "#10b981" if perc_pend >= 100 else "#f59e0b"
        st.plotly_chart(create_gauge(perc_pend, "Meta Pendência", color), use_container_width=True)

def render_main_bar_chart(df):
    if df.empty: return
    df_vol = df.groupby('Colaborador').agg(Bruto=('Data', 'count'), Liquido=('Eh_Novo_Episodio', 'sum')).reset_index().sort_values('Liquido', ascending=True)
    df_melt = df_vol.melt(id_vars='Colaborador', var_name='Tipo', value_name='Volume')
    
    fig = px.bar(df_melt, y='Colaborador', x='Volume', color='Tipo', orientation='h', barmode='group',
                 color_discrete_map={'Bruto': '#e0e7ff', 'Liquido': '#6366f1'}, text='Volume')
    fig.update_traces(textposition='outside', marker_cornerradius=4)
    fig.update_layout(height=400, xaxis=dict(showgrid=False), yaxis=dict(title=None), legend=dict(orientation="h", y=1.1, title=None),
                      plot_bgcolor=THEME['bg_chart'], paper_bgcolor=THEME['bg_chart'], margin=dict(l=0, r=0, t=0, b=0))
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
    fig.add_trace(go.Bar(x=df_tma['Colaborador'], y=df_tma['Capacidade'], name='Capacidade', marker_color='#d1fae5', text=df_tma['Capacidade'], textposition='outside'))
    fig.add_trace(go.Scatter(x=df_tma['Colaborador'], y=df_tma['mean'], mode='markers+lines', name='TMA Real', yaxis='y2', line=dict(color='#ef4444', width=3), marker=dict(size=8, color='white', line=dict(width=2, color='#ef4444'))))
    
    fig.update_layout(height=350, yaxis=dict(title='Qtd', showgrid=True, gridcolor=THEME['grid']), yaxis2=dict(title='TMA (min)', overlaying='y', side='right', showgrid=False), xaxis=dict(showgrid=False),
                      plot_bgcolor=THEME['bg_chart'], paper_bgcolor=THEME['bg_chart'], legend=dict(orientation="h", y=1.1), margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig, use_container_width=True)

def render_evolution_chart(df):
    if df.empty: return
    st.markdown("##### 📈 Fluxo Horário")
    df_line = df.groupby('Hora_Cheia').size().reset_index(name='Volume').sort_values('Hora_Cheia')
    fig = px.area(df_line, x='Hora_Cheia', y='Volume', markers=True)
    fig.update_traces(line=dict(color='#8b5cf6', shape='spline'), fillcolor='rgba(139, 92, 246, 0.1)')
    fig.update_layout(height=250, xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor=THEME['grid']), plot_bgcolor=THEME['bg_chart'], paper_bgcolor=THEME['bg_chart'], margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)

def render_heatmap_clean(df):
    st.markdown("##### 🔥 Mapa de Calor")
    dias = ['Segunda-Feira', 'Terça-Feira', 'Quarta-Feira', 'Quinta-Feira', 'Sexta-Feira']
    df_heat = df[df['Dia_Semana'].isin(dias)]
    if df_heat.empty: return
    
    df_grp = df_heat.groupby(['Dia_Semana', 'Hora_Cheia']).size().reset_index(name='Chamados')
    fig = px.density_heatmap(df_grp, x='Dia_Semana', y='Hora_Cheia', z='Chamados', color_continuous_scale='Blues', text_auto=True)
    fig.update_layout(height=300, coloraxis_showscale=False, xaxis=dict(title=None), yaxis=dict(title=None), margin=dict(l=0, r=0, t=0, b=0), plot_bgcolor=THEME['bg_chart'], paper_bgcolor=THEME['bg_chart'])
    st.plotly_chart(fig, use_container_width=True)

def plot_matrix(df_input, col_x, col_y, title):
    # Lógica simplificada para Aba 2
    df_clean = df_input[(df_input[col_x] != 'Não Informado') & (df_input[col_y] != 'Não Informado')]
    if df_clean.empty: return
    matrix = pd.crosstab(df_clean[col_y], df_clean[col_x])
    matrix = matrix.loc[(matrix!=0).any(axis=1), (matrix!=0).any(axis=0)]
    matrix['Total_Row'] = matrix.sum(axis=1)
    matrix = matrix.sort_values('Total_Row', ascending=False).drop(columns='Total_Row')
    matrix = matrix[matrix.sum().sort_values(ascending=False).index]
    fig = px.imshow(matrix, text_auto=True, aspect="auto", color_continuous_scale='Reds', title=title)
    st.plotly_chart(fig, use_container_width=True)

def render_reincidencia_charts(df_criticos):
    # Lógica simplificada para Aba 3
    c1, c2 = st.columns([2,1])
    with c1:
        all_motivos = df_criticos.explode('Motivos_Unicos')
        if not all_motivos.empty:
            counts = all_motivos['Motivos_Unicos'].value_counts().reset_index()
            counts.columns = ['Motivo', 'Volume']
            fig = px.bar(counts.head(8).sort_values('Volume', ascending=True), x='Volume', y='Motivo', orientation='h', color='Volume')
            st.plotly_chart(fig, use_container_width=True)
