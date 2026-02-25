import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

THEME = {
    'primary': '#6366f1',
    'secondary': '#10b981',
    'warning': '#f59e0b',
    'danger': '#ef4444',
    'grid': '#e5e7eb',
    'text': '#1f2937',
    'soft': '#f3f4f6',
}

CHART_TITLE_STYLE = "font-size:18px; font-weight:600; color:#1f2937; font-family:Inter,sans-serif; margin-bottom:-10px; padding-left:5px;"

def render_pedidos_portal(df):
    st.markdown("<br>", unsafe_allow_html=True)

    # --- Validações de colunas necessárias ---
    required = ['Portal', 'Motivo', 'Numero_Pedido', 'Eh_Novo_Episodio']
    missing = [c for c in required if c not in df.columns]
    if missing:
        st.error(f"Colunas ausentes no DataFrame: {missing}")
        return

    df = df.copy()

    # ── KPIs ─────────────────────────────────────────────────────────────────
    total_pedidos     = df['Numero_Pedido'].nunique()
    total_atendimentos = df['Eh_Novo_Episodio'].sum()
    portais_ativos    = df['Portal'].nunique()

    reincidentes = (
        df[df['Eh_Novo_Episodio'] == 1]
        .groupby('Numero_Pedido')
        .size()
        .reset_index(name='count')
    )
    pedidos_reincidentes = reincidentes[reincidentes['count'] > 1].shape[0]
    taxa_reincidencia = (pedidos_reincidentes / total_pedidos * 100) if total_pedidos > 0 else 0

    k1, k2, k3, k4 = st.columns(4)
    kpi_style = """
        background: white;
        border-radius: 12px;
        padding: 18px 20px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.07);
        border-left: 4px solid {color};
    """
    def kpi_card(col, title, value, subtitle, color):
        col.markdown(f"""
            <div style="{kpi_style.format(color=color)}">
                <p style="margin:0; font-size:12px; color:#6b7280; font-weight:500; text-transform:uppercase; letter-spacing:.05em;">{title}</p>
                <p style="margin:4px 0 2px; font-size:28px; font-weight:700; color:{color};">{value}</p>
                <p style="margin:0; font-size:12px; color:#9ca3af;">{subtitle}</p>
            </div>
        """, unsafe_allow_html=True)

    kpi_card(k1, "Pedidos Únicos",      f"{total_pedidos:,}",         "no período filtrado",         THEME['primary'])
    kpi_card(k2, "Atendimentos Reais",  f"{int(total_atendimentos):,}","episódios novos",             THEME['secondary'])
    kpi_card(k3, "Portais Ativos",      f"{portais_ativos}",          "canais de entrada",           THEME['warning'])
    kpi_card(k4, "Taxa Reincidência",   f"{taxa_reincidencia:.1f}%",  f"{pedidos_reincidentes} pedidos c/ retorno", THEME['danger'])

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Linha 1: Volume por Portal + Motivos por Portal ───────────────────────
    col1, col2 = st.columns([1, 2])

    with col1:
        df_portal = (
            df[df['Eh_Novo_Episodio'] == 1]
            .groupby('Portal')
            .size()
            .reset_index(name='Volume')
            .sort_values('Volume', ascending=True)
        )
        fig_portal = go.Figure(go.Bar(
            x=df_portal['Volume'],
            y=df_portal['Portal'],
            orientation='h',
            marker=dict(
                color=df_portal['Volume'],
                colorscale=[[0, '#e0e7ff'], [1, THEME['primary']]],
                showscale=False,
                cornerradius=6
            ),
            text=df_portal['Volume'],
            textposition='outside',
            textfont=dict(size=12, color=THEME['text'])
        ))
        fig_portal.update_layout(
            height=320,
            xaxis=dict(showgrid=False, showticklabels=False),
            yaxis=dict(title=None),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=10, r=40, t=20, b=10)
        )
        st.markdown(f"<p style='{CHART_TITLE_STYLE}'>🖥️ Volume por Portal</p>", unsafe_allow_html=True)
        st.plotly_chart(fig_portal, use_container_width=True)

    with col2:
        top_motivos = (
            df[df['Eh_Novo_Episodio'] == 1]
            .groupby(['Portal', 'Motivo'])
            .size()
            .reset_index(name='Volume')
        )
        # top 5 motivos globais
        top5 = (
            top_motivos.groupby('Motivo')['Volume'].sum()
            .nlargest(5).index.tolist()
        )
        top_motivos = top_motivos[top_motivos['Motivo'].isin(top5)]

        fig_motivo = px.bar(
            top_motivos,
            x='Portal', y='Volume', color='Motivo',
            barmode='stack',
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_motivo.update_traces(marker_cornerradius=4)
        fig_motivo.update_layout(
            height=320,
            xaxis=dict(title=None, showgrid=False),
            yaxis=dict(title=None, showgrid=True, gridcolor=THEME['grid']),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=None, font=dict(size=11)),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=10, r=10, t=40, b=10)
        )
        st.markdown(f"<p style='{CHART_TITLE_STYLE}'>📌 Top 5 Motivos por Portal</p>", unsafe_allow_html=True)
        st.plotly_chart(fig_motivo, use_container_width=True)

    # ── Linha 2: Reincidência ────────────────────────────────────────────────
    st.markdown(f"<p style='{CHART_TITLE_STYLE}'>🔁 Pedidos com Reincidência (mais de 1 atendimento)</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    df_reinc = (
        df[df['Eh_Novo_Episodio'] == 1]
        .groupby('Numero_Pedido')
        .agg(
            Atendimentos=('Eh_Novo_Episodio', 'count'),
            Portal=('Portal', 'first'),
            Motivo=('Motivo', lambda x: x.mode()[0] if len(x) > 0 else '-'),
            Colaborador=('Colaborador', lambda x: ', '.join(x.unique()[:3]))
        )
        .reset_index()
    )
    df_reinc = df_reinc[df_reinc['Atendimentos'] > 1].sort_values('Atendimentos', ascending=False)

    col_chart, col_table = st.columns([1, 2])

    with col_chart:
        dist = df_reinc['Atendimentos'].value_counts().sort_index().reset_index()
        dist.columns = ['Atendimentos', 'Pedidos']
        dist['Label'] = dist['Atendimentos'].astype(str) + 'x'

        fig_dist = go.Figure(go.Bar(
            x=dist['Label'],
            y=dist['Pedidos'],
            marker=dict(
                color=dist['Pedidos'],
                colorscale=[[0, '#fef3c7'], [1, THEME['danger']]],
                showscale=False,
                cornerradius=6
            ),
            text=dist['Pedidos'],
            textposition='outside',
        ))
        fig_dist.update_layout(
            height=280,
            xaxis=dict(title='Nº de atendimentos', showgrid=False),
            yaxis=dict(title='Pedidos', showgrid=True, gridcolor=THEME['grid']),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=10, r=10, t=20, b=10)
        )
        st.plotly_chart(fig_dist, use_container_width=True)

    with col_table:
        if df_reinc.empty:
            st.success("✅ Nenhum pedido com reincidência no período!")
        else:
            st.markdown(f"""
                <p style="font-size:13px; color:#6b7280; margin-bottom:8px;">
                    Exibindo os <b>{min(50, len(df_reinc))}</b> pedidos com maior reincidência
                </p>
            """, unsafe_allow_html=True)

            def highlight_rows(row):
                if row['Atendimentos'] >= 4:
                    return ['background-color: #fee2e2; color: #991b1b'] * len(row)
                elif row['Atendimentos'] == 3:
                    return ['background-color: #fef3c7; color: #92400e'] * len(row)
                else:
                    return ['background-color: #f0fdf4; color: #166534'] * len(row)

            df_display = df_reinc[['Numero_Pedido', 'Atendimentos', 'Portal', 'Motivo', 'Colaborador']].head(50)
            df_display.columns = ['Pedido', 'Atendimentos', 'Portal', 'Motivo Principal', 'Colaboradores']

            st.dataframe(
                df_display.style.apply(highlight_rows, axis=1),
                use_container_width=True,
                height=260,
                hide_index=True
            )
