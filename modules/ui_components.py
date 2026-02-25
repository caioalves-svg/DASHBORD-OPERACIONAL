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

CHART_TITLE_STYLE = "font-size:18px; font-weight:600; color:#1f2937; font-family:Inter,sans-serif; margin-bottom:-10px; padding-left:5px;"

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

def render_gauges(perc_sac, perc_pend, realizado_sac=0, meta_sac=0, realizado_pend=0, meta_pend=0):
    def meta_card(titulo, icone, perc, realizado, meta, cor_base):
        atingiu = perc >= 100
        perc_bar = min(perc, 100)
        falta = max(0, int(meta) - int(realizado))

        # Cor muda tudo: verde se bateu, vermelho se não bateu
        cor      = "#10b981" if atingiu else "#ef4444"
        cor_bg   = "#f0fdf4" if atingiu else "#fee2e2"
        status_txt  = "Meta atingida!" if atingiu else f"Faltam <b>{falta}</b> atendimentos"
        status_icon = "🏆" if atingiu else "⚠️"

        return (
            f'<div style="background:white;border-radius:16px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,0.08);border-top:4px solid {cor};margin-bottom:12px;">'
            f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;">'
            f'<div style="display:flex;align-items:center;gap:8px;">'
            f'<span style="font-size:20px;">{icone}</span>'
            f'<span style="font-size:15px;font-weight:700;color:#1f2937;">{titulo}</span>'
            f'</div>'
            f'<span style="font-size:26px;font-weight:800;color:{cor};">{perc:.1f}%</span>'
            f'</div>'
            f'<div style="background:#f3f4f6;border-radius:999px;height:10px;margin-bottom:10px;overflow:hidden;">'
            f'<div style="width:{perc_bar}%;height:100%;border-radius:999px;background:{cor};"></div>'
            f'</div>'
            f'<div style="display:flex;justify-content:space-between;font-size:12px;color:#6b7280;margin-bottom:12px;">'
            f'<span>0</span>'
            f'<span style="font-weight:600;color:#374151;">Feito: <b style="color:{cor};">{int(realizado)}</b> / {int(meta)}</span>'
            f'<span>Meta</span>'
            f'</div>'
            f'<div style="background:{cor_bg};border-radius:8px;padding:8px 12px;font-size:13px;color:{cor};text-align:center;">'
            f'{status_icon} {status_txt}'
            f'</div>'
            f'</div>'
        )

    st.markdown("<h4 style='margin-bottom:12px; color:#1f2937;'>🎯 Metas</h4>", unsafe_allow_html=True)
    st.markdown(meta_card("SAC", "📞", perc_sac, realizado_sac, meta_sac, cor_base="#6366f1"), unsafe_allow_html=True)
    st.markdown(meta_card("Pendência", "⏳", perc_pend, realizado_pend, meta_pend, cor_base="#f59e0b"), unsafe_allow_html=True)

def render_main_bar_chart(df):
    if df.empty: return st.info("Sem dados.")
    df_vol = df.groupby('Colaborador').agg(Bruto=('Data', 'count'), Liquido=('Eh_Novo_Episodio', 'sum')).reset_index().sort_values('Liquido', ascending=True)
    df_melt = df_vol.melt(id_vars='Colaborador', var_name='Tipo', value_name='Volume')
    
    fig = px.bar(df_melt, y='Colaborador', x='Volume', color='Tipo', orientation='h', barmode='group',
                 color_discrete_map={'Bruto': '#e0e7ff', 'Liquido': THEME['primary']}, text='Volume')
    
    fig.update_traces(textposition='outside', marker_cornerradius=4)
    fig.update_layout(
        height=450,
        xaxis=dict(showgrid=False), 
        yaxis=dict(title=None),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=None),
        plot_bgcolor='rgba(0,0,0,0)', 
        paper_bgcolor='rgba(0,0,0,0)', 
        margin=dict(l=10, r=10, t=40, b=10)
    )
    st.markdown(f"<p style='{CHART_TITLE_STYLE}'>📊 Performance Individual</p>", unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True)

def render_capacity_scatter(df):
    if df.empty: return
    df_tma = df.groupby('Colaborador')['TMA_Valido'].agg(['mean', 'count']).reset_index()
    df_tma.columns = ['Colaborador', 'mean', 'Amostra']
    df_tma = df_tma[df_tma['Amostra'] > 5]
    TEMPO_UTIL = (17.3 - 7.5) * 60 * 0.70
    df_tma['Capacidade'] = (TEMPO_UTIL / df_tma['mean']).fillna(0).astype(int)
    df_tma = df_tma.sort_values('Capacidade', ascending=False)
    df_tma['TMA_Label'] = df_tma['mean'].round(1).astype(str)
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_tma['Colaborador'], y=df_tma['Capacidade'], name='Capacidade',
        marker_color='#d1fae5', marker_line_color=THEME['secondary'], marker_line_width=1,
        text=df_tma['Capacidade'], textposition='outside'
    ))
    fig.add_trace(go.Scatter(
        x=df_tma['Colaborador'], y=df_tma['mean'], mode='markers+lines+text',
        name='TMA Real', yaxis='y2',
        text=df_tma['TMA_Label'],
        textposition='top center',
        textfont=dict(size=11, color='#ef4444'),
        line=dict(color='#ef4444', width=3),
        marker=dict(size=8, color='white', line=dict(width=2, color='#ef4444'))
    ))
    
    fig.update_layout(
        height=400,
        yaxis=dict(title='Atendimentos', showgrid=True, gridcolor=THEME['grid']),
        yaxis2=dict(title='TMA (min)', overlaying='y', side='right', showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5, title=None),
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=10, r=10, t=50, b=10)
    )
    st.markdown(f"<p style='{CHART_TITLE_STYLE}'>⚡ Capacidade vs Realizado (TMA)</p>", unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True)

def render_evolution_chart(df):
    if df.empty: return
    df_line = df.groupby('Hora_Cheia').size().reset_index(name='Volume').sort_values('Hora_Cheia')
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_line['Hora_Cheia'], y=df_line['Volume'],
        mode='lines+markers+text',
        text=df_line['Volume'],
        textposition='top center',
        textfont=dict(size=11, color=THEME['primary']),
        line=dict(color=THEME['primary'], width=3, shape='spline'),
        fill='tozeroy',
        fillcolor='rgba(99, 102, 241, 0.1)',
        marker=dict(size=6, color=THEME['primary'])
    ))
    fig.update_layout(
        height=320,
        xaxis=dict(showgrid=False, title=None),
        yaxis=dict(showgrid=True, gridcolor=THEME['grid'], title=None),
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=10, r=10, t=20, b=10)
    )
    st.markdown(f"<p style='{CHART_TITLE_STYLE}'>📈 Fluxo Horário</p>", unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True)

def render_heatmap_clean(df):
    dias = ['Segunda-Feira', 'Terça-Feira', 'Quarta-Feira', 'Quinta-Feira', 'Sexta-Feira']
    df_heat = df[df['Dia_Semana'].isin(dias)]
    if df_heat.empty: return
    df_grp = df_heat.groupby(['Dia_Semana', 'Hora_Cheia']).size().reset_index(name='Chamados')
    fig = px.density_heatmap(df_grp, x='Dia_Semana', y='Hora_Cheia', z='Chamados',
                              color_continuous_scale='Purples', text_auto=True)
    fig.update_layout(
        height=320,
        coloraxis_showscale=True,
        coloraxis_colorbar=dict(
            title="Chamados",
            thickness=12,
            len=0.8,
            tickfont=dict(size=10)
        ),
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=10, r=60, t=20, b=10)
    )
    st.markdown(f"<p style='{CHART_TITLE_STYLE}'>🔥 Mapa de Calor Semanal</p>", unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True)
