import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

# TEMA AUDITADO: CLEAR PROFESSIONAL
THEME = {
    'primary': '#2563eb',    # Azul Profissional
    'secondary': '#10b981',  # Verde Sucesso
    'warning': '#f59e0b',    # Laranja Alerta
    'danger': '#ef4444',     # Vermelho Erro
    'grid': '#f1f5f9',       # Cinza muito claro
    'text': '#1e293b',       # Cinza Escuro (Slate 800)
    'text_muted': '#64748b'  # Cinza Médio (Slate 500)
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
        font=dict(color=THEME['text'], family="Inter, sans-serif"),
        height=height,
        xaxis=dict(showgrid=False, linecolor=THEME['grid']),
        yaxis=dict(showgrid=True, gridcolor=THEME['grid'], linecolor=THEME['grid']),
        margin=dict(l=10, r=10, t=40, b=10)
    )

CHART_TITLE_STYLE = "font-size:18px; font-weight:700; color:#1e293b; font-family:Inter,sans-serif; margin-bottom:12px; border-left: 4px solid #2563eb; padding-left: 10px;"

def render_header():
    st.markdown(f"""
        <div class="custom-header">
            <div class="header-title">📋 Monitoramento Operacional</div>
            <div style="font-size: 13px; color: #64748b; font-weight: 500; margin-top: 5px;">
                Gestão de Metas e Performance Auditada • {datetime.now().strftime('%d/%m/%Y')}
            </div>
        </div>
    """, unsafe_allow_html=True)

def render_sidebar_filters(df_raw):
    st.sidebar.markdown("<h2 style='color:#1e293b; font-size:20px; font-weight:800;'>Filtros Globais</h2>", unsafe_allow_html=True)
    st.sidebar.markdown("---")
    
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
    
    st.sidebar.markdown("<br><br>", unsafe_allow_html=True)
    st.sidebar.caption("v5.2 - Error Fixed")
    
    return df, end

def render_gauges(perc_sac, perc_pend, realizado_sac=0, meta_sac=0, realizado_pend=0, meta_pend=0):
    def meta_card(titulo, icone, perc, realizado, meta):
        atingiu = perc >= 100
        cor = THEME['secondary'] if atingiu else THEME['warning']
        status = "META ALCANÇADA" if atingiu else "PENDENTE"
        
        return (
            f'<div class="professional-card" style="border-top: 4px solid {cor} !important;">'
            f'<div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:10px;">'
            f'  <div style="font-size:14px; font-weight:700; color:#64748b; text-transform:uppercase;">{icone} {titulo}</div>'
            f'  <div style="font-size:24px; font-weight:800; color:{cor};">{perc:.1f}%</div>'
            f'</div>'
            f'<div style="display:flex; align-items:center; justify-content:space-between;">'
            f'  <div style="font-size:18px; font-weight:700; color:#1e293b;">{int(realizado)} <span style="font-size:13px; font-weight:400; color:#94a3b8;">de {int(meta)}</span></div>'
            f'  <div style="font-size:11px; font-weight:700; color:{cor}; background:{cor}11; padding:2px 8px; border-radius:4px;">{status}</div>'
            f'</div>'
            f'<div style="background:#f1f5f9; border-radius:4px; height:6px; margin-top:12px; overflow:hidden;">'
            f'  <div style="width:{min(perc, 100)}%; height:100%; background:{cor};"></div>'
            f'</div>'
            f'</div>'
        )

    st.markdown("<h4 style='margin-bottom:15px; font-weight:700; color:#1e293b;'>🎯 Acompanhamento de Metas</h4>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(meta_card("SAC", "📞", perc_sac, realizado_sac, meta_sac), unsafe_allow_html=True)
    with col2:
        st.markdown(meta_card("Pendência", "⏳", perc_pend, realizado_pend, meta_pend), unsafe_allow_html=True)

def render_main_bar_chart(df):
    if df.empty: return
    df_vol = df.groupby('Colaborador').agg(
        Bruto=('Data', 'count'), 
        Liquido=('Eh_Novo_Episodio', 'sum')
    ).reset_index().sort_values('Liquido', ascending=True)
    
    fig = px.bar(df_vol, y='Colaborador', x=['Liquido', 'Bruto'], 
                 orientation='h', barmode='group',
                 color_discrete_sequence=[THEME['primary'], '#e2e8f0'],
                 text_auto='.0s')
    
    apply_chart_layout(fig, height=500)
    fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=None))
    
    st.markdown(f"<div class='professional-card'><p style='{CHART_TITLE_STYLE}'>Volume por Colaborador (Líquido x Bruto)</p>", unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True)
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
        marker=dict(color='#eff6ff', line=dict(color=THEME['primary'], width=1))
    ))
    fig.add_trace(go.Scatter(
        x=df_tma['Colaborador'], y=df_tma['mean'], name='TMA Atual (min)',
        yaxis='y2', line=dict(color=THEME['danger'], width=3),
        marker=dict(size=8, color=THEME['danger'])
    ))
    
    apply_chart_layout(fig, height=450)
    fig.update_layout(
        yaxis2=dict(title='TMA (min)', overlaying='y', side='right', showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.1, xanchor="center", x=0.5)
    )
    
    st.markdown(f"<div class='professional-card'><p style='{CHART_TITLE_STYLE}'>Capacidade de Atendimento x TMA</p>", unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

def render_evolution_chart(df):
    if df.empty: return
    df_line = df.groupby('Hora_Cheia').size().reset_index(name='Volume').sort_values('Hora_Cheia')
    fig = px.line(df_line, x='Hora_Cheia', y='Volume', markers=True, 
                  color_discrete_sequence=[THEME['primary']])
    fig.update_traces(line_width=3, fill='tozeroy')
    apply_chart_layout(fig, height=350)
    st.markdown(f"<div class='professional-card'><p style='{CHART_TITLE_STYLE}'>Fluxo Operacional por Hora</p>", unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

def render_heatmap_clean(df):
    dias_ordem = ['Segunda-Feira', 'Terça-Feira', 'Quarta-Feira', 'Quinta-Feira', 'Sexta-Feira']
    df_grp = df[df['Dia_Semana'].isin(dias_ordem)].groupby(['Dia_Semana', 'Hora_Cheia']).size().reset_index(name='Volume')
    if df_grp.empty: return
    fig = px.density_heatmap(df_grp, x='Dia_Semana', y='Hora_Cheia', z='Volume',
                              color_continuous_scale='Blues', category_orders={"Dia_Semana": dias_ordem})
    apply_chart_layout(fig, height=350)
    st.markdown(f"<div class='professional-card'><p style='{CHART_TITLE_STYLE}'>Concentração de Chamados (Heatmap)</p>", unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

def render_ranking_alertas(df):
    if df.empty: return
    col_rank, col_alert = st.columns(2)
    
    with col_rank:
        st.markdown(f"<p style='{CHART_TITLE_STYLE}'>🏆 Melhores Desempenhos</p>", unsafe_allow_html=True)
        df_rank = df[df['Eh_Novo_Episodio'] == 1].groupby('Colaborador').size().reset_index(name='Vol').sort_values('Vol', ascending=False).head(5)
        for _, row in df_rank.iterrows():
            st.markdown(
                f'<div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:8px; padding:10px 15px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">'
                f'  <span style="font-weight:700; color:#1e293b;">{row["Colaborador"]}</span>'
                f'  <span style="font-weight:800; color:#2563eb; font-size:18px;">{int(row["Vol"])}</span>'
                f'</div>',
                unsafe_allow_html=True
            )

    with col_alert:
        st.markdown(f"<p style='{CHART_TITLE_STYLE}'>🚨 Alertas de Performance</p>", unsafe_allow_html=True)
        df_stats = df.groupby('Colaborador').agg(TMA=('TMA_Valido', 'mean')).reset_index()
        media_tma = df_stats['TMA'].mean()
        alertas = df_stats[df_stats['TMA'] > media_tma * 1.3].head(3)
        
        if alertas.empty:
            st.markdown('<div class="professional-card" style="text-align:center; color:#10b981;">✅ Sem alertas no momento.</div>', unsafe_allow_html=True)
        else:
            for _, r in alertas.iterrows():
                st.markdown(
                    f'<div style="background:#fef2f2; border:1px solid #fee2e2; border-radius:8px; padding:10px 15px; margin-bottom:8px;">'
                    f'  <div style="font-weight:700; color:#ef4444;">{r["Colaborador"]}</div>'
                    f'  <div style="font-size:12px; color:#b91c1c;">TMA {r["TMA"]:.1f} min (acima da média)</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
