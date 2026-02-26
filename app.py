import streamlit as st
from datetime import datetime
from modules import data_loader, business_logic, ui_components
from modules import pedidos_portal

st.set_page_config(page_title="Dashboard Operacional", page_icon="🚛", layout="wide", initial_sidebar_state="expanded")
ui_components.load_css()

# Força sidebar sempre visível
st.markdown("""
    <style>
        [data-testid="collapsedControl"] { display: none; }
        section[data-testid="stSidebar"] { display: block !important; visibility: visible !important; }
    </style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### 🚛 Painel de Controle")
    if st.button("🔄 Atualizar Dados", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

try:
    df_raw = data_loader.get_raw_data()
except Exception as e:
    st.error(f"Erro: {e}")
    st.stop()

df_processed = business_logic.process_data(df_raw)
df_filtered, end_date = ui_components.render_sidebar_filters(df_processed)
df_metas = business_logic.calculate_meta_logic(df_filtered, end_date)

total_bruto = df_filtered.shape[0]
total_liquido = df_filtered['Eh_Novo_Episodio'].sum()
taxa_duplicidade = ((total_bruto - total_liquido) / total_bruto * 100) if total_bruto > 0 else 0

meta_total_sac = df_metas['Meta_SAC'].sum()
meta_total_pend = df_metas['Meta_PEND'].sum()

if 'Setor' in df_filtered.columns:
    realizado_sac = df_filtered[df_filtered['Setor'].str.contains('SAC', case=False, na=False)]['Eh_Novo_Episodio'].sum()
    realizado_pend = df_filtered[df_filtered['Setor'].str.contains('Pend', case=False, na=False)]['Eh_Novo_Episodio'].sum()
else:
    realizado_sac = realizado_pend = 0

perc_sac = (realizado_sac / meta_total_sac * 100) if meta_total_sac > 0 else 0
perc_pend = (realizado_pend / meta_total_pend * 100) if meta_total_pend > 0 else 0

# --- ABAS ---
ui_components.render_header()

aba1, aba2 = st.tabs(["📊 Operacional", "🛒 Pedidos & Portal"])

with aba1:
    media_meta = (perc_sac + perc_pend) / 2
    meta_color = "#10b981" if media_meta >= 100 else ("#f59e0b" if media_meta >= 75 else "#ef4444")
    dup_color  = "#10b981" if taxa_duplicidade < 15 else "#ef4444"

    kpi_style = """
        background: white;
        border-radius: 12px;
        padding: 18px 22px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.07);
        border-left: 4px solid {color};
        height: 100%;
    """
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f"""
        <div style="{kpi_style.format(color='#6366f1')}">
            <p style="margin:0;font-size:12px;color:#6b7280;font-weight:500;text-transform:uppercase;letter-spacing:.05em;">📋 Total Registros</p>
            <p style="margin:4px 0 2px;font-size:32px;font-weight:700;color:#6366f1;">{total_bruto:,}</p>
            <p style="margin:0;font-size:12px;color:#9ca3af;">entradas no período</p>
        </div>""", unsafe_allow_html=True)
    c2.markdown(f"""
        <div style="{kpi_style.format(color='#10b981')}">
            <p style="margin:0;font-size:12px;color:#6b7280;font-weight:500;text-transform:uppercase;letter-spacing:.05em;">✅ Atendimentos Reais</p>
            <p style="margin:4px 0 2px;font-size:32px;font-weight:700;color:#10b981;">{int(total_liquido):,}</p>
            <p style="margin:0;font-size:12px;color:#9ca3af;">episódios únicos</p>
        </div>""", unsafe_allow_html=True)
    c3.markdown(f"""
        <div style="{kpi_style.format(color=dup_color)}">
            <p style="margin:0;font-size:12px;color:#6b7280;font-weight:500;text-transform:uppercase;letter-spacing:.05em;">🔁 Taxa Duplicidade</p>
            <p style="margin:4px 0 2px;font-size:32px;font-weight:700;color:{dup_color};">{taxa_duplicidade:.1f}%</p>
            <p style="margin:0;font-size:12px;color:#9ca3af;">alvo: abaixo de 15%</p>
        </div>""", unsafe_allow_html=True)
    c4.markdown(f"""
        <div style="{kpi_style.format(color=meta_color)}">
            <p style="margin:0;font-size:12px;color:#6b7280;font-weight:500;text-transform:uppercase;letter-spacing:.05em;">🎯 Meta Global</p>
            <p style="margin:4px 0 2px;font-size:32px;font-weight:700;color:{meta_color};">{media_meta:.1f}%</p>
            <p style="margin:0;font-size:12px;color:#9ca3af;">média SAC + Pendência</p>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col_main_1, col_main_2 = st.columns([2, 1])
    with col_main_1:
        ui_components.render_main_bar_chart(df_filtered)
    with col_main_2:
        ui_components.render_gauges(
            perc_sac, perc_pend,
            realizado_sac=realizado_sac, meta_sac=meta_total_sac,
            realizado_pend=realizado_pend, meta_pend=meta_total_pend
        )

    ui_components.render_capacity_scatter(df_filtered)

    col_ev1, col_ev2 = st.columns(2)
    with col_ev1:
        ui_components.render_evolution_chart(df_filtered)
    with col_ev2:
        ui_components.render_heatmap_clean(df_filtered)

    ui_components.render_ranking_alertas(df_filtered)

with aba2:
    pedidos_portal.render_pedidos_portal(df_filtered)
