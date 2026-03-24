import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime

# CONFIGURACAO DE PRESTIGIO
THEME = {
    'primary': '#1e40af',    # Blue Sapphire
    'secondary': '#059669',  # Emerald
    'warning': '#d97706',    # Amber
    'danger': '#dc2626',     # Crimson
    'white': '#ffffff',
    'slate': '#64748b'
}

def load_css():
    try:
        with open("modules/styles.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except: pass

def render_header():
    st.markdown(f"""
        <div style="display:flex; align-items:center; justify-content:space-between; padding: 20px 0; margin-bottom: 20px;">
            <div>
                <h1 style="margin:0; font-size:34px; font-weight:800; color:#0f172a; letter-spacing:-1.5px;">Dashboard Operacional</h1>
                <p style="margin:0; font-size:14px; color:#64748b; font-weight:500;">Intelligence & Global Performance Analysis • {datetime.now().strftime('%d/%m/%Y')}</p>
            </div>
            <div style="background:#eff6ff; border:1px solid #dbeafe; padding:10px 20px; border-radius:14px;">
                <span style="color:#1e40af; font-weight:800; font-size:12px; letter-spacing:1px; text-transform:uppercase;">Status: Operational ⚡</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

def render_kpi_cards(total_bruto, total_liquido, taxa_duplicidade, media_meta):
    c1, c2, c3, c4 = st.columns(4)
    
    dup_color = THEME['secondary'] if taxa_duplicidade < 15 else THEME['danger']
    meta_color = THEME['secondary'] if media_meta >= 100 else (THEME['warning'] if media_meta >= 80 else THEME['danger'])
    
    def card(label, value, sub, color, icon):
        return f"""
            <div class="kpi-card" style="border-top: 5px solid {color};">
                <div style="font-size: 24px; margin-bottom: 10px;">{icon}</div>
                <div style="font-size: 13px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px;">{label}</div>
                <div style="font-size: 34px; font-weight: 900; color: #0f172a; margin: 5px 0;">{value}</div>
                <div style="font-size: 12px; color: #94a3b8; font-weight: 500;">{sub}</div>
            </div>
        """
    
    c1.markdown(card("Volume Bruto", f"{total_bruto:,}", "Registros totais", THEME['primary'], "📊"), unsafe_allow_html=True)
    c2.markdown(card("Atendimentos", f"{int(total_liquido):,}", "Casos únicos resolvidos", THEME['secondary'], "✅"), unsafe_allow_html=True)
    c3.markdown(card("Duplicidade", f"{taxa_duplicidade:.1f}%", "Alvo: < 15%", dup_color, "🔁"), unsafe_allow_html=True)
    c4.markdown(card("Meta Global", f"{media_meta:.1f}%", "Aproveitamento geral", meta_color, "🎯"), unsafe_allow_html=True)

def render_sidebar_filters(df_raw):
    with st.sidebar:
        st.markdown("<h2 style='font-size:22px; font-weight:800; color:#0f172a;'>Control Center</h2>", unsafe_allow_html=True)
        st.markdown("---")
        
        min_date = df_raw['Data'].min().date()
        max_val = df_raw['Data'].max().date()
        today = datetime.now().date()
        
        dr = st.date_input("Filtrar por Periodo", value=[today, today], min_value=min_date, max_value=max_val)
        
        if isinstance(dr, (list, tuple)) and len(dr) == 2: start, end = dr
        else: start = end = (dr[0] if isinstance(dr, (list, tuple)) else dr)
        
        setores = st.multiselect("Setores", options=sorted(df_raw['Setor'].unique()))
        analistas = st.multiselect("Analistas", options=sorted(df_raw['Colaborador'].unique()))
        
        df = df_raw.copy()
        df = df[(df['Data'].dt.date >= start) & (df['Data'].dt.date <= end)]
        if setores: df = df[df['Setor'].isin(setores)]
        if analistas: df = df[df['Colaborador'].isin(analistas)]
        
        return df, end

def render_gauges(perc_sac, perc_pend, realizado_sac=0, meta_sac=0, realizado_pend=0, meta_pend=0):
    def gauge_card(title, perc, done, target, icon):
        color = THEME['secondary'] if perc >= 100 else (THEME['warning'] if perc >= 80 else THEME['danger'])
        return f"""
            <div class="kpi-card" style="border-right: 6px solid {color}; padding: 30px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <div style="font-size:12px; font-weight:800; color:#64748b; text-transform:uppercase;">{icon} {title}</div>
                        <div style="font-size:32px; font-weight:900; color:#0f172a; margin-top:5px;">{perc:.1f}%</div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-size:12px; font-weight:600; color:#94a3b8;">{int(done)} / {int(target)}</div>
                        <div style="background:{color}22; color:{color}; font-size:10px; font-weight:800; padding:2px 8px; border-radius:5px; margin-top:5px;">METRIC STATUS</div>
                    </div>
                </div>
                <div style="background:#f1f5f9; height:8px; border-radius:10px; margin-top:15px; overflow:hidden;">
                    <div style="width:{min(perc, 100)}%; height:100%; background:{color};"></div>
                </div>
            </div>
        """
    
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1: st.markdown(gauge_card("Setor SAC", perc_sac, realizado_sac, meta_sac, "📞"), unsafe_allow_html=True)
    with c2: st.markdown(gauge_card("Setor Pendencia", perc_pend, realizado_pend, meta_pend, "⏳"), unsafe_allow_html=True)

def render_ranking_section(df):
    st.markdown("<h3 style='margin-top:40px; font-weight:800; color:#0f172a;'>🏆 Top Performance Recognition</h3>", unsafe_allow_html=True)
    
    df_rank = df[df['Eh_Novo_Episodio'] == 1].groupby('Colaborador').size().reset_index(name='Total').sort_values('Total', ascending=False).head(5).reset_index(drop=True)
    
    if df_rank.empty: return
    
    p1 = df_rank.iloc[0] if len(df_rank) > 0 else None
    p2 = df_rank.iloc[1] if len(df_rank) > 1 else None
    p3 = df_rank.iloc[2] if len(df_rank) > 2 else None
    
    def podium_item(p, place_cls, medal, font_size):
        if p is None: return ""
        return f'<div class="podium-place {place_cls}"><div class="medal">{medal}</div><div class="podium-name">{p["Colaborador"]}</div><div class="podium-value" style="font-size:{font_size}px; max-width:90%; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; box-sizing:border-box;">{int(p["Total"])}</div></div>'

    podium_html = f'<div class="podium-container">{podium_item(p2, "place-2", "🥈", 22)}{podium_item(p1, "place-1", "👑", 28)}{podium_item(p3, "place-3", "🥉", 20)}</div>'
    st.markdown(podium_html, unsafe_allow_html=True)
    
    if len(df_rank) > 3:
        st.markdown("<div style='margin-top:-10px;'></div>", unsafe_allow_html=True)
        for i, row in df_rank.iloc[3:].iterrows():
            st.markdown(f"""
                <div style="background:white; border:1px solid #f1f5f9; border-radius:12px; padding:15px 25px; display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; box-shadow:0 2px 4px rgba(0,0,0,0.02);">
                    <div style="display:flex; align-items:center; gap:15px;">
                        <span style="font-weight:900; color:#cbd5e1; font-size:18px;">#{i+1}</span>
                        <span style="font-weight:700; color:#1e293b;">{row['Colaborador']}</span>
                    </div>
                    <span style="font-weight:800; color:#1e40af; font-size:18px;">{int(row['Total'])}</span>
                </div>
            """, unsafe_allow_html=True)

def render_main_charts(df):
    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2 = st.columns([2, 1])
    
    with c1:
        st.markdown("<p style='font-size:16px; font-weight:800; color:#0f172a; margin-bottom:15px;'>📊 Eficiência Analítica (Média Diária)</p>", unsafe_allow_html=True)
        n_dias = max(df['Data'].nunique(), 1)
        df_vol = df.groupby('Colaborador').agg(Liquido=('Eh_Novo_Episodio', 'sum')).reset_index()
        df_vol['Media_Dia'] = (df_vol['Liquido'] / n_dias).round(1)
        df_vol = df_vol.sort_values('Media_Dia', ascending=True)
        
        fig = px.bar(df_vol, y='Colaborador', x='Media_Dia', orientation='h', color_discrete_sequence=[THEME['primary']], text_auto=True)
        fig.update_traces(textposition='outside')
        fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', margin=dict(l=10, r=40, t=10, b=10), height=450, showlegend=False, xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='#f1f5f9'))
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown("<p style='font-size:16px; font-weight:800; color:#0f172a; margin-bottom:15px;'>⚠️ Risk Analysis (SLA)</p>", unsafe_allow_html=True)
        df_stats = df.groupby('Colaborador').agg(TMA=('TMA_Valido', 'mean'), Volume=('Eh_Novo_Episodio', 'sum')).reset_index()
        media_tma_equipe = df_stats['TMA'].mean()
        
        # Logica Auditada de Alerta: Quem tem volume alto (> media + 20%) tem o limite de TMA flexibilizado para +50% da media.
        # Caso contrario, o limite padrao e +30% da media.
        media_vol = df_stats['Volume'].mean()
        df_stats['Limite_TMA'] = np.where(df_stats['Volume'] > media_vol * 1.2, media_tma_equipe * 1.5, media_tma_equipe * 1.3)
        alertas = df_stats[df_stats['TMA'] > df_stats['Limite_TMA']].head(3)
        
        if alertas.empty:
            st.markdown('<div style="background:#f0fdf4; border:1px solid #dcfce7; border-radius:15px; padding:40px; text-align:center;"><div style="font-size:40px; margin-bottom:10px;">🛡️</div><div style="font-weight:800; color:#16a34a;">OPERATIONAL STABILITY</div><div style="font-size:12px; color:#16a34a; font-weight:500;">Metricas dentro do esperado.</div></div>', unsafe_allow_html=True)
        else:
            for _, r in alertas.iterrows():
                st.markdown(f'<div style="background:#fff1f2; border:1px solid #ffe4e6; border-radius:12px; padding:15px; margin-bottom:12px; border-left:5px solid #e11d48;"><div style="font-weight:800; color:#9f1239; font-size:14px;">{r["Colaborador"]}</div><div style="font-size:12px; color:#e11d48; font-weight:500;">TMA Critico: {r["TMA"]:.1f} min</div></div>', unsafe_allow_html=True)

def render_capacity_analysis(df):
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<div class='kpi-card'><p style='font-size:16px; font-weight:800; color:#0f172a; margin-bottom:20px;'>⚡ Capacidade Projetada vs TMA Real</p>", unsafe_allow_html=True)
    df_tma = df.groupby('Colaborador')['TMA_Valido'].agg(['mean', 'count']).reset_index()
    df_tma = df_tma[df_tma['count'] > 5]
    
    # 25% Ociosidade (75% produtivo)
    TEMPO_UTIL = (17.3 - 7.5) * 60 * 0.75 
    df_tma['Capacidade'] = (TEMPO_UTIL / df_tma['mean']).fillna(0).astype(int)
    df_tma = df_tma.sort_values('Capacidade', ascending=False)
    
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df_tma['Colaborador'], y=df_tma['Capacidade'], marker_color='#dbeafe', text=df_tma['Capacidade'], textposition='outside'))
    fig.add_trace(go.Scatter(x=df_tma['Colaborador'], y=df_tma['mean'], yaxis='y2', line=dict(color='#ef4444', width=3), text=df_tma['mean'].round(1), mode='lines+markers+text', textposition='top center'))
    fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=400, margin=dict(l=10, r=40, t=10, b=10), yaxis=dict(title='Capacidade/Dia'), yaxis2=dict(title='TMA (min)', overlaying='y', side='right', showgrid=False), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

def render_heatmap(df):
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<div class='kpi-card'><p style='font-size:16px; font-weight:800; color:#0f172a; margin-bottom:20px;'>🔥 Mapa de Calor: Produtividade por Hora</p>", unsafe_allow_html=True)
    
    df_heat = df.copy()
    
    if not df_heat.empty:
        # Agrupa por Hora e Dia da Semana
        df_grp = df_heat.groupby(['Dia_Semana', 'Hora_Cheia']).size().reset_index(name='Atendimentos')
        
        # Ordem dos dias sem caracteres especiais para evitar problemas de encoding
        ordem_dias = ['Segunda-Feira', 'Terça-Feira', 'Quarta-Feira', 'Quinta-Feira', 'Sexta-Feira', 'Sábado', 'Domingo']
        
        fig_heat = px.density_heatmap(
            df_grp, 
            x='Dia_Semana', 
            y='Hora_Cheia', 
            z='Atendimentos',
            category_orders={"Dia_Semana": ordem_dias},
            color_continuous_scale='Blues',
            text_auto=True
        )
        
        fig_heat.update_layout(
            height=450,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=10, r=10, b=10, t=10),
            xaxis_title="Dia da Semana",
            yaxis_title="Hora do Dia"
        )
        st.plotly_chart(fig_heat, use_container_width=True)
    else:
        st.warning("Sem dados suficientes para gerar o mapa de calor.")
    st.markdown("</div>", unsafe_allow_html=True)
