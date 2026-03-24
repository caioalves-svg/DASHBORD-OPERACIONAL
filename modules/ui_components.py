import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

# TEMA EXECUTIVO: SAPPHIRE & SLATE
THEME = {
    'primary': '#1e40af',    # Azul Safira (Elegância Corporativa)
    'secondary': '#059669',  # Verde Esmeralda (Sucesso)
    'warning': '#d97706',    # Âmbar (Atenção)
    'danger': '#dc2626',     # Vermelho (Crítico)
    'bg': '#f8fafc',
    'text': '#0f172a',       # Slate 900
    'text_muted': '#64748b'  # Slate 500
}

def load_css():
    try:
        with open("modules/styles.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except: pass

def apply_chart_layout(fig, height=400):
    fig.update_layout(
        plot_bgcolor='rgba(255,255,255,0)',
        paper_bgcolor='rgba(255,255,255,0)',
        font=dict(color=THEME['text'], family="Plus Jakarta Sans, sans-serif"),
        height=height,
        xaxis=dict(showgrid=False, linecolor='#e2e8f0', tickfont=dict(size=11, color=THEME['text_muted'])),
        yaxis=dict(showgrid=True, gridcolor='#f1f5f9', linecolor='#e2e8f0', tickfont=dict(size=11, color=THEME['text_muted'])),
        margin=dict(l=10, r=10, t=20, b=10),
        legend=dict(font=dict(size=11), orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

def render_header():
    st.markdown(f"""
        <div class="exec-header">
            <div>
                <div style="font-size: 28px; font-weight: 800; color: #0f172a; letter-spacing: -1px;">
                    Operational Performance Intelligence
                </div>
                <div style="font-size: 14px; font-weight: 500; color: #64748b; margin-top: 4px;">
                    Monitoramento Estratégico em Tempo Real • {datetime.now().strftime('%d de %B de %Y')}
                </div>
            </div>
            <div style="text-align: right;">
                <div style="background: #eff6ff; padding: 8px 16px; border-radius: 99px; border: 1px solid #dbeafe; font-size: 12px; font-weight: 700; color: #1e40af;">
                    SYSTEMS STATUS: OPTIMIZED ⚡
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

def render_sidebar_filters(df_raw):
    st.sidebar.markdown("<div style='padding: 20px 0;'><span style='font-size: 18px; font-weight: 800; color: #0f172a;'>CONTROLES</span></div>", unsafe_allow_html=True)
    
    min_date = df_raw['Data'].min().date()
    max_val = df_raw['Data'].max().date()
    today = datetime.now().date()
    
    date_range = st.sidebar.date_input("Filtrar Período", value=[today, today], min_value=min_date, max_value=max_val)
    
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        start, end = date_range
    else:
        start = end = (date_range[0] if isinstance(date_range, (list, tuple)) else date_range)

    setores = st.sidebar.multiselect("Setores", options=sorted(df_raw['Setor'].unique()))
    colaboradores = st.sidebar.multiselect("Colaboradores", options=sorted(df_raw['Colaborador'].unique()))
    
    df = df_raw.copy()
    df = df[(df['Data'].dt.date >= start) & (df['Data'].dt.date <= end)]
    if setores: df = df[df['Setor'].isin(setores)]
    if colaboradores: df = df[df['Colaborador'].isin(colaboradores)]
    
    return df, end

def render_gauges(perc_sac, perc_pend, realizado_sac=0, meta_sac=0, realizado_pend=0, meta_pend=0):
    def meta_widget(titulo, perc, realizado, meta):
        cor = THEME['secondary'] if perc >= 100 else (THEME['warning'] if perc >= 80 else THEME['danger'])
        
        return (
            f'<div class="exec-card" style="padding: 20px !important;">'
            f'  <div style="display:flex; align-items:flex-end; justify-content:space-between; margin-bottom:12px;">'
            f'    <div style="font-size:12px; font-weight:700; color:#64748b; text-transform:uppercase;">{titulo}</div>'
            f'    <div style="font-size:24px; font-weight:800; color:{cor};">{perc:.1f}%</div>'
            f'  </div>'
            f'  <div style="background:#f1f5f9; height:8px; border-radius:99px; overflow:hidden; margin-bottom:12px;">'
            f'    <div style="width:{min(perc, 100)}%; height:100%; background:{cor}; border-radius:99px;"></div>'
            f'  </div>'
            f'  <div style="display:flex; justify-content:space-between;">'
            f'    <span style="font-size:12px; color:#94a3b8;">Feito: <b>{int(realizado)}</b></span>'
            f'    <span style="font-size:12px; color:#94a3b8;">Meta: <b>{int(meta)}</b></span>'
            f'  </div>'
            f'</div>'
        )

    st.markdown("<div style='font-size:16px; font-weight:800; color:#0f172a; margin-bottom:16px; margin-top:32px;'>📈 DESEMPENHO CORPORATIVO</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1: st.markdown(meta_widget("Central SAC", perc_sac, realizado_sac, meta_sac), unsafe_allow_html=True)
    with c2: st.markdown(meta_widget("Setor Pendência", perc_pend, realizado_pend, meta_pend), unsafe_allow_html=True)

def render_main_bar_chart(df):
    if df.empty: return
    df_vol = df.groupby('Colaborador').agg(
        Bruto=('Data', 'count'), 
        Liquido=('Eh_Novo_Episodio', 'sum')
    ).reset_index().sort_values('Liquido', ascending=True)
    
    fig = px.bar(df_vol, y='Colaborador', x=['Liquido', 'Bruto'], 
                 orientation='h', barmode='group',
                 color_discrete_sequence=[THEME['primary'], '#f1f5f9'],
                 labels={'value': 'Quantidade', 'variable': 'Tipo'})
    
    apply_chart_layout(fig, height=500)
    fig.update_traces(marker_cornerradius=6)
    
    st.markdown("<div class='exec-card'><div style='font-size:15px; font-weight:700; color:#0f172a; margin-bottom:20px;'>VOLUME OPERACIONAL POR ANALISTA</div>", unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    st.markdown("</div>", unsafe_allow_html=True)

def render_capacity_scatter(df):
    if df.empty: return
    df_tma = df.groupby('Colaborador')['TMA_Valido'].agg(['mean', 'count']).reset_index()
    df_tma.columns = ['Colaborador', 'mean', 'Amostra']
    df_tma = df_tma[df_tma['Amostra'] > 5]
    
    TEMPO_UTIL = (17.3 - 7.5) * 60 * 0.80
    df_tma['Capacidade'] = (TEMPO_UTIL / df_tma['mean']).fillna(0).astype(int)
    df_tma = df_tma.sort_values('Capacidade', ascending=False)
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_tma['Colaborador'], y=df_tma['Capacidade'], name='Capacidade Projetada',
        marker=dict(color='#dbeafe', line=dict(color=THEME['primary'], width=1))
    ))
    fig.add_trace(go.Scatter(
        x=df_tma['Colaborador'], y=df_tma['mean'], name='TMA Médio (min)',
        yaxis='y2', line=dict(color=THEME['danger'], width=4, shape='spline'),
        marker=dict(size=10, color='white', line=dict(width=3, color=THEME['danger']))
    ))
    
    apply_chart_layout(fig, height=450)
    fig.update_layout(
        yaxis2=dict(title='Tempo (min)', overlaying='y', side='right', showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.1, xanchor="center", x=0.5)
    )
    
    st.markdown("<div class='exec-card'><div style='font-size:15px; font-weight:700; color:#0f172a; margin-bottom:20px;'>MATRIZ DE CAPACIDADE VS EFICIÊNCIA</div>", unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    st.markdown("</div>", unsafe_allow_html=True)

def render_evolution_chart(df):
    if df.empty: return
    df_line = df.groupby('Hora_Cheia').size().reset_index(name='Volume')
    fig = px.area(df_line, x='Hora_Cheia', y='Volume', markers=True, 
                  color_discrete_sequence=[THEME['primary']])
    
    apply_chart_layout(fig, height=350)
    fig.update_traces(line_width=4, fillcolor='rgba(30, 64, 175, 0.05)')
    
    st.markdown("<div class='exec-card'><div style='font-size:15px; font-weight:700; color:#0f172a; margin-bottom:20px;'>VOLUMETRIA HORÁRIA (FLOW)</div>", unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    st.markdown("</div>", unsafe_allow_html=True)

def render_heatmap_clean(df):
    dias = ['Segunda-Feira', 'Terça-Feira', 'Quarta-Feira', 'Quinta-Feira', 'Sexta-Feira']
    df_grp = df[df['Dia_Semana'].isin(dias)].groupby(['Dia_Semana', 'Hora_Cheia']).size().reset_index(name='Volume')
    if df_grp.empty: return
    
    fig = px.density_heatmap(df_grp, x='Dia_Semana', y='Hora_Cheia', z='Volume',
                              color_continuous_scale=['#f8fafc', '#dbeafe', '#3b82f6', '#1e40af'],
                              category_orders={"Dia_Semana": dias})
    
    apply_chart_layout(fig, height=350)
    fig.update_layout(coloraxis_showscale=False)
    
    st.markdown("<div class='exec-card'><div style='font-size:15px; font-weight:700; color:#0f172a; margin-bottom:20px;'>PONTOS DE CONGESTIONAMENTO OPERACIONAL</div>", unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    st.markdown("</div>", unsafe_allow_html=True)

def render_ranking_alertas(df):
    if df.empty: return
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown("<div style='font-size:15px; font-weight:700; color:#0f172a; margin-bottom:16px;'>🏆 TOP PERFORMANCE RECOGNITION</div>", unsafe_allow_html=True)
        df_rank = df[df['Eh_Novo_Episodio'] == 1].groupby('Colaborador').size().reset_index(name='Vol').sort_values('Vol', ascending=False).head(5)
        for i, row in df_rank.reset_index(drop=True).iterrows():
            st.markdown(
                f'<div style="background:#ffffff; border:1px solid #f1f5f9; border-radius:12px; padding:12px 20px; margin-bottom:10px; display:flex; justify-content:space-between; align-items:center; box-shadow: 0 1px 2px rgba(0,0,0,0.03);">'
                f'  <div style="display:flex; align-items:center; gap:12px;">'
                f'    <div style="background:#eff6ff; color:#1e40af; font-weight:800; border-radius:8px; width:28px; height:28px; display:flex; align-items:center; justify-content:center; font-size:12px;">{i+1}</div>'
                f'    <span style="font-weight:600; color:#1e293b; font-size:14px;">{row["Colaborador"]}</span>'
                f'  </div>'
                f'  <span style="font-weight:800; color:#0f172a; font-size:16px;">{int(row["Vol"])}</span>'
                f'</div>',
                unsafe_allow_html=True
            )

    with c2:
        st.markdown("<div style='font-size:15px; font-weight:700; color:#0f172a; margin-bottom:16px;'>⚠️ RISK MANAGEMENT & ALERTS</div>", unsafe_allow_html=True)
        df_stats = df.groupby('Colaborador').agg(TMA=('TMA_Valido', 'mean')).reset_index()
        media_tma = df_stats['TMA'].mean()
        alertas = df_stats[df_stats['TMA'] > media_tma * 1.3].head(3)
        
        if alertas.empty:
            st.markdown('<div class="exec-card" style="text-align:center; padding: 40px !important;"><span style="color:#059669; font-weight:700;">✅ TODAS AS MÉTRICAS DENTRO DO SLA</span></div>', unsafe_allow_html=True)
        else:
            for _, r in alertas.iterrows():
                st.markdown(
                    f'<div style="background:#fff1f2; border:1px solid #ffe4e6; border-radius:12px; padding:12px 20px; margin-bottom:10px; border-left: 5px solid #e11d48;">'
                    f'  <div style="font-weight:700; color:#9f1239; font-size:14px;">{r["Colaborador"]}</div>'
                    f'  <div style="font-size:12px; color:#e11d48; font-weight:500;">Alerta de Baixa Eficiência: TMA {r["TMA"]:.1f} min</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
