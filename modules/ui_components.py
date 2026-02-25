import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

# CORES GLOBAIS DO DASHBOARD
COLOR_PALETTE = {
    'primary': '#4F46E5', # Indigo
    'secondary': '#10B981', # Emerald
    'accent': '#F59E0B', # Amber
    'danger': '#EF4444', # Red
    'neutral': '#6B7280', # Gray
    'charts': ['#4F46E5', '#10B981', '#3B82F6', '#F59E0B', '#EF4444', '#8B5CF6']
}

def load_css():
    with open("modules/styles.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# --- COMPONENTE DE CARD PERSONALIZADO (HTML) ---
def kpi_card(title, value, delta=None, delta_color="neutral", icon="📊"):
    """
    Renderiza um card HTML estilizado.
    delta_color: 'normal' (verde), 'inverse' (vermelho), 'neutral' (cinza)
    """
    
    # Lógica de cor do delta
    css_class = "delta-neu"
    if delta_color == "normal": css_class = "delta-pos"
    elif delta_color == "inverse": css_class = "delta-neg"
    
    delta_html = f"<div class='kpi-delta {css_class}'>{delta}</div>" if delta else ""
    
    html = f"""
    <div class="kpi-card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div class="kpi-title">{title}</div>
            <div style="font-size:1.2rem; opacity:0.5;">{icon}</div>
        </div>
        <div class="kpi-value">{value}</div>
        {delta_html}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

# --- FUNÇÕES DE RENDERIZAÇÃO ---

def render_sidebar_filters(df_raw):
    st.sidebar.markdown("### 🎛️ Filtros Operacionais")
    
    min_date = df_raw['Data'].min().date()
    max_date = max(df_raw['Data'].max().date(), datetime.now().date())
    today = datetime.now().date()

    # Lógica de dia atual
    default_val = [min_date, min_date] if today < min_date else [today, today]

    date_range = st.sidebar.date_input("Período de Análise", value=default_val, min_value=min_date, max_value=max_date, format="DD/MM/YYYY")
    
    if len(date_range) == 2:
        start, end = date_range
    elif len(date_range) == 1:
        start, end = date_range[0], date_range[0]
    else:
        start, end = today, today

    st.sidebar.markdown("---")
    
    # Filtros com chaves únicas para evitar conflito
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

    # Layout de Cards HTML
    c1, c2, c3 = st.columns(3)
    with c1: kpi_card("Total Registros", f"{total_bruto}", icon="📦")
    with c2: kpi_card("Atendimentos Reais (2h)", f"{total_liquido}", icon="✅")
    with c3: kpi_card("Taxa de Duplicidade", f"{taxa_duplicidade:.1f}%", delta="Alvo: < 15%", delta_color="inverse", icon="⚠️")

    st.markdown("---")
    return total_liquido

def render_productivity_charts(df):
    st.subheader("1. Volume de Atendimento")
    st.caption("Comparativo entre Total de Registros (Bruto) e Atendimentos Reais (Líquido)")
    
    df_vol = df.groupby('Colaborador').agg(
        Bruto=('Data', 'count'),
        Liquido=('Eh_Novo_Episodio', 'sum'),
        Erros_CRM=('Motivo_CRM', lambda x: x.isin(['SEM ABERTURA DE CRM', 'Não Informado']).sum())
    ).reset_index().sort_values('Liquido', ascending=True)
    
    df_melt = df_vol.melt(id_vars=['Colaborador', 'Erros_CRM'], value_vars=['Bruto', 'Liquido'], var_name='Métrica', value_name='Volume')
    max_vol = df_melt['Volume'].max()
    
    fig = px.bar(df_melt, y='Colaborador', x='Volume', color='Métrica', barmode='group', orientation='h',
                 color_discrete_map={'Bruto': '#FCD34D', 'Liquido': COLOR_PALETTE['primary']}, # Amarelo suave e Indigo
                 text='Volume',
                 hover_data={'Erros_CRM': True, 'Métrica': True, 'Volume': True, 'Colaborador': False})
    
    # Estilização Clean do Plotly
    fig.update_traces(textposition='outside', marker_line_width=0, opacity=0.9)
    fig.update_layout(
        height=450, 
        margin=dict(r=50, l=0, t=0, b=0), 
        xaxis=dict(range=[0, max_vol * 1.15], showgrid=False),
        yaxis=dict(showgrid=False),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        legend=dict(orientation="h", y=-0.15, title=None)
    )
    st.plotly_chart(fig, use_container_width=True)

def render_capacity_chart(df, df_metas, perc_sac, realized_sac, meta_sac, cor_sac, perc_pend, realized_pend, meta_pend, cor_pend):
    
    # Cards de Meta Estilizados
    mc1, mc2 = st.columns(2)
    with mc1: 
        # Traduz 'normal'/'inverse' para cores do kpi_card
        d_color = "normal" if cor_sac == "normal" else "inverse"
        kpi_card("Meta SAC (Projeção)", f"{perc_sac:.1f}%", delta=f"{realized_sac}/{meta_sac} Realizados", delta_color=d_color, icon="🎧")
    with mc2:
        d_color = "normal" if cor_pend == "normal" else "inverse"
        kpi_card("Meta Pendência (Projeção)", f"{perc_pend:.1f}%", delta=f"{realized_pend}/{meta_pend} Realizados", delta_color=d_color, icon="⏳")

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("2. Projeção Individual (Meta vs Real)")
    
    df_tma = df.groupby('Colaborador')['TMA_Valido'].agg(['mean', 'count']).reset_index()
    df_tma.columns = ['Colaborador', 'TMA_Medio', 'Amostra']
    df_tma = df_tma[df_tma['Amostra'] > 5] 
    
    # 07:30 a 17:18 = 9.8h -> 588 min * 0.7 = 411.6
    TEMPO_UTIL = (17.3 - 7.5) * 60 * 0.70
    
    df_tma['Capacidade_Diaria'] = (TEMPO_UTIL / df_tma['TMA_Medio']).fillna(0).astype(int)
    df_tma = df_tma.sort_values('Capacidade_Diaria', ascending=False)
    max_cap = df_tma['Capacidade_Diaria'].max() if not df_tma.empty else 100

    fig = go.Figure()
    # Barra suave
    fig.add_trace(go.Bar(
        x=df_tma['Colaborador'], 
        y=df_tma['Capacidade_Diaria'], 
        name='Capacidade Projetada', 
        marker_color='#10B981', # Emerald Green
        text=df_tma['Capacidade_Diaria'], 
        textposition='outside',
        marker_cornerradius=5 # Bordas arredondadas na barra (Novo no Plotly)
    ))
    
    # Linha elegante
    fig.add_trace(go.Scatter(
        x=df_tma['Colaborador'], 
        y=df_tma['TMA_Medio'], 
        mode='lines+markers+text', 
        name='TMA Atual (min)', 
        marker=dict(color='#EF4444', size=10, line=dict(width=2, color='white')), # Bolinha vermelha com borda branca
        line=dict(color='#EF4444', width=3, shape='spline'), # Linha curva (spline) fica mais bonito
        text=df_tma['TMA_Medio'].apply(lambda x: f"{x:.1f}'"), 
        textposition='top center', 
        yaxis='y2'
    ))
    
    fig.update_layout(
        height=450,
        yaxis=dict(title='Capacidade', range=[0, max_cap * 1.3], showgrid=True, gridcolor='#F3F4F6'),
        yaxis2=dict(title='TMA (min)', overlaying='y', side='right', showgrid=False),
        xaxis=dict(showgrid=False),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        legend=dict(orientation="h", y=-0.2),
        margin=dict(t=40)
    )
    st.plotly_chart(fig, use_container_width=True)

def render_heatmap(df):
    st.subheader("3. Mapa de Calor (Pressão Operacional)")
    dias_uteis = ['Segunda-Feira', 'Terça-Feira', 'Quarta-Feira', 'Quinta-Feira', 'Sexta-Feira']
    df_heat = df[df['Dia_Semana'].isin(dias_uteis)]
    
    if not df_heat.empty:
        df_grp = df_heat.groupby(['Dia_Semana', 'Hora_Cheia']).size().reset_index(name='Chamados')
        fig_heat = px.density_heatmap(
            df_grp, x='Dia_Semana', y='Hora_Cheia', z='Chamados', 
            category_orders={"Dia_Semana": dias_uteis}, 
            color_continuous_scale='ygmnbu', # Gradiente profissional (Yellow Green Blue)
            text_auto=True
        )
        fig_heat.update_layout(
            height=400,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=0, r=0, b=0, t=0)
        )
        st.plotly_chart(fig_heat, use_container_width=True)

def render_reincidencia_charts(df_criticos):
    c1, c2 = st.columns([2,1])
    with c1:
        st.markdown("**Top Motivos de Retorno**")
        all_motivos = df_criticos.explode('Motivos_Unicos')
        if not all_motivos.empty:
            counts = all_motivos['Motivos_Unicos'].value_counts().reset_index()
            counts.columns = ['Motivo', 'Volume']
            counts['Porcentagem'] = (counts['Volume'] / counts['Volume'].sum() * 100).map('{:,.1f}%'.format)
            
            fig = px.bar(
                counts.head(8).sort_values('Volume', ascending=True),
                x='Volume', y='Motivo', orientation='h', text='Porcentagem', 
                color='Volume', color_continuous_scale='Blues'
            )
            fig.update_traces(textposition='outside', marker_cornerradius=3)
            fig.update_layout(
                height=350, 
                coloraxis_showscale=False, 
                yaxis_title=None,
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showgrid=True, gridcolor='#F3F4F6')
            )
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.info("💡 **Dica:** Use a tabela abaixo para ver o histórico cronológico de cada pedido crítico.")
