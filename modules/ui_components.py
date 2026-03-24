import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

# CONFIGURAÇÃO DE PRESTÍGIO
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
        
        dr = st.date_input("Filtrar por Período", value=[today, today], min_value=min_date, max_value=max_val)
        
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
    with c2: st.markdown(gauge_card("Setor Pendência", perc_pend, realizado_pend, meta_pend, "⏳"), unsafe_allow_html=True)

def render_ranking_section(df):
    st.markdown("<h3 style='margin-top:40px; font-weight:800; color:#0f172a;'>🏆 Top Performance Recognition</h3>", unsafe_allow_html=True)
    
    df_rank = df[df['Eh_Novo_Episodio'] == 1].groupby('Colaborador').size().reset_index(name='Vol').sort_values('Vol', ascending=False).head(5).reset_index(drop=True)
    
    if df_rank.empty: return
    
    # Render Pódio corrigido (valores dentro da margem)
    p1 = df_rank.iloc[0] if len(df_rank) > 0 else None
    p2 = df_rank.iloc[1] if len(df_rank) > 1 else None
    p3 = df_rank.iloc[2] if len(df_rank) > 2 else None
    
    podium_html = f"""
        <div class="podium-container">
            <!-- 2º Lugar -->
            <div class="podium-place place-2" style="padding-top: 30px;">
                <div class="medal">🥈</div>
                <div class="podium-name" style="width: 100%; padding: 0 5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{p2['Colaborador'] if p2 is not None else '-'}</div>
                <div class="podium-value" style="font-size: 22px;">{int(p2['Vol']) if p2 is not None else 0}</div>
            </div>
            <!-- 1º Lugar -->
            <div class="podium-place place-1" style="padding-top: 30px;">
                <div class="medal">👑</div>
                <div class="podium-name" style="width: 100%; padding: 0 5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{p1['Colaborador'] if p1 is not None else '-'}</div>
                <div class="podium-value" style="font-size: 28px;">{int(p1['Vol']) if p1 is not None else 0}</div>
            </div>
            <!-- 3º Lugar -->
            <div class="podium-place place-3" style="padding-top: 30px;">
                <div class="medal">🥉</div>
                <div class="podium-name" style="width: 100%; padding: 0 5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{p3['Colaborador'] if p3 is not None else '-'}</div>
                <div class="podium-value" style="font-size: 20px;">{int(p3['Vol']) if p3 is not None else 0}</div>
            </div>
        </div>
    """
    st.markdown(podium_html, unsafe_allow_html=True)
    
    # Outros no Top 5
    if len(df_rank) > 3:
        st.markdown("<div style='margin-top:-20px;'></div>", unsafe_allow_html=True)
        for i, row in df_rank.iloc[3:].iterrows():
            st.markdown(f"""
                <div style="background:white; border:1px solid #f1f5f9; border-radius:12px; padding:15px 25px; display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; box-shadow:0 2px 4px rgba(0,0,0,0.02);">
                    <div style="display:flex; align-items:center; gap:15px;">
                        <span style="font-weight:900; color:#cbd5e1; font-size:18px;">#{i+1}</span>
                        <span style="font-weight:700; color:#1e293b;">{row['Colaborador']}</span>
                    </div>
                    <span style="font-weight:800; color:#1e40af; font-size:18px;">{int(row['Vol'])}</span>
                </div>
            """, unsafe_allow_html=True)

def render_main_charts(df):
    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2 = st.columns([2, 1])
    
    with c1:
        st.markdown("<p style='font-size:16px; font-weight:800; color:#0f172a; margin-bottom:15px;'>📊 Eficiência Analítica por Colaborador</p>", unsafe_allow_html=True)
        df_vol = df.groupby('Colaborador').agg(
            Liquido=('Eh_Novo_Episodio', 'sum')
        ).reset_index().sort_values('Liquido', ascending=True)
        
        fig = px.bar(df_vol, y='Colaborador', x='Liquido', 
                     orientation='h', 
                     color_discrete_sequence=[THEME['primary']],
                     text_auto=True) # ADICIONADO QUANTIDADE NA BARRA
        
        fig.update_traces(textposition='outside')
        fig.update_layout(
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=10, r=40, t=10, b=10), height=450,
            showlegend=False, xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='#f1f5f9')
        )
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown("<p style='font-size:16px; font-weight:800; color:#0f172a; margin-bottom:15px;'>⚠️ Risk Analysis</p>", unsafe_allow_html=True)
        df_stats = df.groupby('Colaborador').agg(TMA=('TMA_Valido', 'mean')).reset_index()
        media_tma = df_stats['TMA'].mean()
        alertas = df_stats[df_stats['TMA'] > media_tma * 1.3].head(3)
        
        if alertas.empty:
            st.markdown("""
                <div style="background:#f0fdf4; border:1px solid #dcfce7; border-radius:15px; padding:40px; text-align:center;">
                    <div style="font-size:40px; margin-bottom:10px;">🛡️</div>
                    <div style="font-weight:800; color:#16a34a;">OPERATIONAL STABILITY</div>
                    <div style="font-size:12px; color:#16a34a; font-weight:500;">Todos os analistas operando no SLA.</div>
                </div>
            """, unsafe_allow_html=True)
        else:
            for _, r in alertas.iterrows():
                st.markdown(f"""
                    <div style="background:#fff1f2; border:1px solid #ffe4e6; border-radius:12px; padding:15px; margin-bottom:12px; border-left:5px solid #e11d48;">
                        <div style="font-weight:800; color:#9f1239; font-size:14px;">{r['Colaborador']}</div>
                        <div style="font-size:12px; color:#e11d48; font-weight:500;">TMA Crítico: {r['TMA']:.1f} min</div>
                    </div>
                """, unsafe_allow_html=True)

def render_capacity_analysis(df):
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<div class='kpi-card'>", unsafe_allow_html=True)
    st.markdown("<p style='font-size:16px; font-weight:800; color:#0f172a; margin-bottom:20px;'>⚡ Capacidade Projetada vs TMA Real</p>", unsafe_allow_html=True)
    
    df_tma = df.groupby('Colaborador')['TMA_Valido'].agg(['mean', 'count']).reset_index()
    df_tma = df_tma[df_tma['count'] > 5]
    TEMPO_UTIL = (17.3 - 7.5) * 60 * 0.80
    df_tma['Capacidade'] = (TEMPO_UTIL / df_tma['mean']).fillna(0).astype(int)
    df_tma = df_tma.sort_values('Capacidade', ascending=False)
    
    fig = go.Figure()
    # Adicionando rótulos nas barras
    fig.add_trace(go.Bar(
        x=df_tma['Colaborador'], y=df_tma['Capacidade'], 
        name='Capacidade', marker_color='#dbeafe',
        text=df_tma['Capacidade'], textposition='outside'
    ))
    # Adicionando rótulos na linha
    fig.add_trace(go.Scatter(
        x=df_tma['Colaborador'], y=df_tma['mean'], 
        name='TMA (min)', yaxis='y2', 
        line=dict(color='#ef4444', width=3),
        text=df_tma['mean'].round(1), mode='lines+markers+text', textposition='top center'
    ))
    
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
        height=400, margin=dict(l=10, r=40, t=10, b=10),
        yaxis=dict(title='Capacidade/Dia'), yaxis2=dict(title='TMA (min)', overlaying='y', side='right', showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5)
    )
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)
