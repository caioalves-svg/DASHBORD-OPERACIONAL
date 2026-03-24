import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

# TEMA GLOBAL DARK PREMIUM
THEME = {
    'primary': '#6366f1',    # Indigo Neon
    'secondary': '#10b981',  # Emerald
    'warning': '#f59e0b',    # Amber
    'danger': '#ef4444',     # Rose
    'grid': '#334155',       # Slate 700
    'text': '#f8fafc'        # Slate 50
}

# Configuração Padrão dos Gráficos
PLOT_CONFIG = dict(
    plot_bgcolor='rgba(0,0,0,0)',
    paper_bgcolor='rgba(0,0,0,0)',
    font=dict(color=THEME['text'], family="Inter, sans-serif"),
    xaxis=dict(showgrid=False, color='#94a3b8'),
    yaxis=dict(showgrid=True, gridcolor=THEME['grid'], color='#94a3b8')
)

CHART_TITLE_STYLE = "font-size:20px; font-weight:700; color:#f8fafc; font-family:Inter,sans-serif; margin-bottom:15px; letter-spacing:-0.5px;"

def load_css():
    try:
        with open("modules/styles.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except: pass

def render_header():
    st.markdown(f"""
        <div class="custom-header">
            <div style="font-size: 3rem; margin-bottom: 15px;">🚀</div>
            <div class="header-title">OPERATIONAL COMMAND CENTER</div>
            <div style="font-size: 14px; font-weight: 500; color: rgba(255,255,255,0.8); text-transform: uppercase; letter-spacing: 2px;">
                Monitoramento de Performance em Tempo Real
            </div>
        </div>
    """, unsafe_allow_html=True)

def render_sidebar_filters(df_raw):
    st.sidebar.markdown("<h2 style='color:white; font-size:24px; font-weight:800; margin-bottom:20px;'>Dashboard Control</h2>", unsafe_allow_html=True)
    
    # Estilo custom para a barra lateral
    st.sidebar.markdown("---")
    
    min_date = df_raw['Data'].min().date()
    try: max_val = df_raw['Data'].max().date()
    except: max_val = datetime.now().date()
    max_date = max(max_val, datetime.now().date())
    today = datetime.now().date()
    
    default_val = [today, today] if today >= min_date else [min_date, min_date]
    date_range = st.sidebar.date_input("📅 Período de Análise", value=default_val, min_value=min_date, max_value=max_date, format="DD/MM/YYYY")
    
    if isinstance(date_range, (list, tuple)):
        start, end = (date_range[0], date_range[0]) if len(date_range) == 1 else date_range
    else:
        start, end = date_range, date_range

    setores = st.sidebar.multiselect("🏢 Selecionar Setor", options=sorted(df_raw['Setor'].unique()))
    colaboradores = st.sidebar.multiselect("👥 Selecionar Colaboradores", options=sorted(df_raw['Colaborador'].unique()))
    
    df = df_raw.copy()
    df = df[(df['Data'].dt.date >= start) & (df['Data'].dt.date <= end)]
    if setores: df = df[df['Setor'].isin(setores)]
    if colaboradores: df = df[df['Colaborador'].isin(colaboradores)]
    
    st.sidebar.markdown("<br><br>", unsafe_allow_html=True)
    st.sidebar.info("⚙️ Versão 4.0 - Premium Design")
    
    return df, end

def render_gauges(perc_sac, perc_pend, realizado_sac=0, meta_sac=0, realizado_pend=0, meta_pend=0):
    def meta_card(titulo, icone, perc, realizado, meta, cor_base):
        atingiu = perc >= 100
        perc_bar = min(perc, 100)
        falta = max(0, int(meta) - int(realizado))

        # Design Premium Glass
        cor_neon = "#10b981" if atingiu else "#f59e0b"
        status_txt = "META BATIDA!" if atingiu else f"PENDENTE: {falta} atend."
        
        return (
            f'<div class="glass-card" style="margin-bottom:20px; border-left: 6px solid {cor_neon} !important;">'
            f'<div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:15px;">'
            f'  <div style="display:flex; align-items:center; gap:12px;">'
            f'    <div style="background:{cor_neon}22; padding:10px; border-radius:12px; font-size:24px;">{icone}</div>'
            f'    <div>'
            f'      <div style="font-size:14px; font-weight:500; color:#94a3b8; text-transform:uppercase; letter-spacing:1px;">{titulo}</div>'
            f'      <div style="font-size:20px; font-weight:800; color:white;">{int(realizado)} <span style="font-size:14px; font-weight:400; color:#64748b;">/ {int(meta)}</span></div>'
            f'    </div>'
            f'  </div>'
            f'  <div style="text-align:right;">'
            f'    <div style="font-size:32px; font-weight:900; color:{cor_neon}; line-height:1;">{perc:.1f}%</div>'
            f'    <div style="font-size:10px; font-weight:700; color:{cor_neon}; margin-top:4px;">{status_txt}</div>'
            f'  </div>'
            f'</div>'
            f'<div style="background:rgba(255,255,255,0.05); border-radius:999px; height:8px; overflow:hidden; margin-top:10px;">'
            f'  <div style="width:{perc_bar}%; height:100%; background:linear-gradient(90deg, {cor_neon}, #6366f1); box-shadow: 0 0 15px {cor_neon}66;"></div>'
            f'</div>'
            f'</div>'
        )

    st.markdown("<h3 style='margin-bottom:20px; font-weight:800; color:white; letter-spacing:-1px;'>🎯 PERFORMANCE DE METAS</h3>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(meta_card("Setor SAC", "📞", perc_sac, realizado_sac, meta_sac, cor_base="#6366f1"), unsafe_allow_html=True)
    with col2:
        st.markdown(meta_card("Setor Pendência", "⏳", perc_pend, realizado_pend, meta_pend, cor_base="#f59e0b"), unsafe_allow_html=True)

def render_main_bar_chart(df):
    if df.empty: return st.info("Sem dados para exibir.")
    
    df_vol = df.groupby('Colaborador').agg(
        Bruto=('Data', 'count'), 
        Liquido=('Eh_Novo_Episodio', 'sum')
    ).reset_index().sort_values('Liquido', ascending=True)
    
    df_melt = df_vol.melt(id_vars='Colaborador', var_name='Tipo', value_name='Volume')
    
    fig = px.bar(df_melt, y='Colaborador', x='Volume', color='Tipo', 
                 orientation='h', barmode='group',
                 color_discrete_map={'Bruto': 'rgba(99, 102, 241, 0.2)', 'Liquido': '#6366f1'},
                 text='Volume')
    
    fig.update_traces(textposition='outside', marker_cornerradius=8)
    fig.update_layout(
        **PLOT_CONFIG,
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1, title=None),
        margin=dict(l=10, r=40, t=20, b=10)
    )
    st.markdown(f"<div class='glass-card'><p style='{CHART_TITLE_STYLE}'>📊 Eficiência por Colaborador</p>", unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

def render_capacity_scatter(df):
    if df.empty: return
    df_tma = df.groupby('Colaborador')['TMA_Valido'].agg(['mean', 'count']).reset_index()
    df_tma.columns = ['Colaborador', 'mean', 'Amostra']
    df_tma = df_tma[df_tma['Amostra'] > 5]
    
    # Cálculo de capacidade usando os novos parâmetros (80% produtividade)
    TEMPO_UTIL = (17.3 - 7.5) * 60 * 0.80
    df_tma['Capacidade'] = (TEMPO_UTIL / df_tma['mean']).fillna(0).astype(int)
    df_tma = df_tma.sort_values('Capacidade', ascending=False)
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_tma['Colaborador'], y=df_tma['Capacidade'], name='Capacidade Projetada',
        marker=dict(color='rgba(16, 185, 129, 0.1)', line=dict(color=THEME['secondary'], width=2)),
        text=df_tma['Capacidade'], textposition='outside'
    ))
    fig.add_trace(go.Scatter(
        x=df_tma['Colaborador'], y=df_tma['mean'], mode='markers+lines+text',
        name='TMA Atual (Min)', yaxis='y2',
        text=df_tma['mean'].round(1),
        textposition='top center',
        line=dict(color=THEME['danger'], width=4, dash='dot'),
        marker=dict(size=12, color='white', line=dict(width=3, color=THEME['danger']))
    ))
    
    fig.update_layout(
        **PLOT_CONFIG,
        height=450,
        yaxis=dict(title='Volume de Entrega', showgrid=True, gridcolor=THEME['grid']),
        yaxis2=dict(title='TMA (minutos)', overlaying='y', side='right', showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.1, xanchor="center", x=0.5),
        margin=dict(l=10, r=10, t=60, b=10)
    )
    st.markdown(f"<div class='glass-card'><p style='{CHART_TITLE_STYLE}'>⚡ Potencial de Entrega vs TMA</p>", unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

def render_evolution_chart(df):
    if df.empty: return
    df_line = df.groupby('Hora_Cheia').size().reset_index(name='Volume').sort_values('Hora_Cheia')
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_line['Hora_Cheia'], y=df_line['Volume'],
        mode='lines+markers',
        line=dict(color=THEME['primary'], width=5, shape='spline'),
        fill='tozeroy',
        fillcolor='rgba(99, 102, 241, 0.15)',
        marker=dict(size=10, color='white', line=dict(width=3, color=THEME['primary']))
    ))
    fig.update_layout(
        **PLOT_CONFIG,
        height=350,
        margin=dict(l=10, r=10, t=30, b=10)
    )
    st.markdown(f"<div class='glass-card'><p style='{CHART_TITLE_STYLE}'>📈 Fluxo Operacional (Horário)</p>", unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

def render_heatmap_clean(df):
    dias_ordem = ['Segunda-Feira', 'Terça-Feira', 'Quarta-Feira', 'Quinta-Feira', 'Sexta-Feira']
    df_heat = df[df['Dia_Semana'].isin(dias_ordem)]
    if df_heat.empty: return
    
    df_grp = df_heat.groupby(['Dia_Semana', 'Hora_Cheia']).size().reset_index(name='Volume')
    
    fig = px.density_heatmap(df_grp, x='Dia_Semana', y='Hora_Cheia', z='Volume',
                              color_continuous_scale=['#0f172a', '#6366f1', '#a855f7', '#f472b6'],
                              category_orders={"Dia_Semana": dias_ordem})
    
    fig.update_layout(
        **PLOT_CONFIG,
        height=350,
        coloraxis_colorbar=dict(thickness=15, len=0.8),
        margin=dict(l=10, r=10, t=30, b=10)
    )
    st.markdown(f"<div class='glass-card'><p style='{CHART_TITLE_STYLE}'>🔥 Mapa de Calor da Operação</p>", unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

def render_ranking_alertas(df):
    if df.empty: return
    st.markdown("<br>", unsafe_allow_html=True)
    
    col_rank, col_alert = st.columns([1, 1])

    with col_rank:
        st.markdown(f"<p style='{CHART_TITLE_STYLE}'>🏆 TOP PERFORMERS</p>", unsafe_allow_html=True)
        
        df_rank = (
            df[df['Eh_Novo_Episodio'] == 1]
            .groupby('Colaborador')
            .agg(Atendimentos=('Eh_Novo_Episodio', 'sum'))
            .reset_index()
            .sort_values('Atendimentos', ascending=False)
            .head(5)
        )

        for i, row in df_rank.reset_index(drop=True).iterrows():
            medal = "👑" if i == 0 else "⭐"
            st.markdown(
                f'<div class="glass-card" style="padding:15px !important; margin-bottom:12px; border-left:4px solid #f59e0b !important;">'
                f'<div style="display:flex; align-items:center; justify-content:space-between;">'
                f'  <div style="display:flex; align-items:center; gap:12px;">'
                f'    <div style="font-size:20px;">{medal}</div>'
                f'    <div style="font-weight:700; color:white; font-size:15px;">{row["Colaborador"]}</div>'
                f'  </div>'
                f'  <div style="font-size:20px; font-weight:900; color:#f59e0b;">{int(row["Atendimentos"])}</div>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True
            )

    with col_alert:
        st.markdown(f"<p style='{CHART_TITLE_STYLE}'>🚨 CRITICAL INSIGHTS</p>", unsafe_allow_html=True)
        
        # Lógica de Alertas Premium
        df_stats = df.groupby('Colaborador').agg(
            Volume=('Eh_Novo_Episodio', 'sum'),
            TMA=('TMA_Valido', 'mean')
        ).reset_index()
        
        media_tma = df_stats['TMA'].mean()
        alertas = df_stats[df_stats['TMA'] > media_tma * 1.3].head(3)

        if alertas.empty:
            st.markdown(
                f'<div class="glass-card" style="border-left:4px solid #10b981 !important; text-align:center; padding:30px !important;">'
                f'<div style="font-size:40px; margin-bottom:10px;">🛡️</div>'
                f'<div style="font-weight:700; color:#10b981;">OPERATIONAL STABILITY</div>'
                f'<div style="font-size:12px; color:#94a3b8;">Nenhuma anomalia detectada</div>'
                f'</div>',
                unsafe_allow_html=True
            )
        else:
            for _, r in alertas.iterrows():
                st.markdown(
                    f'<div class="glass-card" style="padding:15px !important; margin-bottom:12px; border-left:4px solid #ef4444 !important;">'
                    f'<div style="font-size:11px; font-weight:700; color:#ef4444; text-transform:uppercase;">Alerta de Gargalo</div>'
                    f'<div style="font-weight:700; color:white; margin:4px 0;">{r["Colaborador"]}</div>'
                    f'<div style="font-size:12px; color:#94a3b8;">TMA {r["TMA"]:.1f} min — {((r["TMA"]/media_tma-1)*100):.0f}% acima da média</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
