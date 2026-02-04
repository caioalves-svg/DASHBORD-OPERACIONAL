import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import timedelta
from streamlit_gsheets import GSheetsConnection

# ==============================================================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(
    page_title="Dashboard Operacional",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .metric-card { background-color: #f0f2f6; border-radius: 10px; padding: 15px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); }
    [data-testid="stMetricValue"] { font-size: 24px; font-weight: bold; }
    .js-plotly-plot .plotly .modebar { orientation: v; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. ETL & CÁLCULOS
# ==============================================================================
@st.cache_data(ttl=600)
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df = conn.read(worksheet="Página1")
    except:
        df = conn.read()

    # --- TRATAMENTO ---
    df['Data'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['Data'])

    cols_texto = ['Colaborador', 'Setor', 'Portal', 'Transportadora', 'Motivo', 'Motivo_CRM', 'Numero_Pedido', 'Nota_Fiscal']
    for col in cols_texto:
        if col in df.columns:
            df[col] = df[col].fillna("Não Informado").astype(str).replace("nan", "Não Informado").str.strip().str.replace(';', ',').str.replace('\n', ' ')

    # Data e Hora
    if 'Hora' in df.columns:
        df['Hora_Str'] = df['Hora'].astype(str)
        df['Hora_Cheia'] = df['Hora_Str'].str.slice(0, 2) + ":00"
    else:
        df['Hora_Cheia'] = df['Data'].dt.hour.astype(str).str.zfill(2) + ":00"
        df['Hora_Str'] = df['Data'].dt.strftime('%H:%M:%S')

    try:
        df['Data_Completa'] = df['Data'] + pd.to_timedelta(df['Hora_Str'])
    except:
        df['Data_Completa'] = df['Data']

    if 'Dia_Semana' in df.columns:
        df['Dia_Semana'] = df['Dia_Semana'].astype(str).str.title().str.strip()

    # Chave Única e ID Ref
    df['ID_Ref'] = np.where(df['Numero_Pedido'] != "Não Informado", df['Numero_Pedido'], df['Nota_Fiscal'])
    df['ID_Ref'] = df['ID_Ref'].astype(str)
    
    df['Data_Str'] = df['Data'].dt.strftime('%Y-%m-%d')
    df['Chave_Unica_Dia'] = df['Data_Str'] + "_" + df['Colaborador'] + "_" + df['ID_Ref']

    # --- LÓGICA 2 HORAS ---
    df = df.sort_values(by=['ID_Ref', 'Data_Completa'])
    df['Tempo_Desde_Ultimo_Contato'] = df.groupby('ID_Ref')['Data_Completa'].diff()
    
    df['Eh_Novo_Episodio'] = np.where(
        (df['Tempo_Desde_Ultimo_Contato'].isnull()) | (df['Tempo_Desde_Ultimo_Contato'] > pd.Timedelta(hours=2)), 
        1, 
        0
    )

    # --- CÁLCULO TMA ---
    df = df.sort_values(by=['Colaborador', 'Data_Completa'])
    df['Tempo_Ate_Proximo'] = df.groupby('Colaborador')['Data_Completa'].shift(-1) - df['Data_Completa']
    df['Minutos_No_Atendimento'] = df['Tempo_Ate_Proximo'].dt.total_seconds() / 60
    
    df['TMA_Valido'] = np.where(
        (df['Minutos_No_Atendimento'] > 0.5) & (df['Minutos_No_Atendimento'] <= 40),
        df['Minutos_No_Atendimento'],
        np.nan
    )

    return df

# --- BOTÃO DE REFRESH MANUAL ---
st.sidebar.title("Dashboard Operacional")
if st.sidebar.button("🔄 Atualizar Dados Agora"):
    st.cache_data.clear()
    st.rerun()

try:
    df_raw = load_data()
except Exception as e:
    st.error(f"Erro no processamento. Detalhe: {e}")
    st.stop()

# ==============================================================================
# 3. FILTROS
# ==============================================================================
st.sidebar.header("🔍 Filtros")
st.sidebar.markdown("---")

min_date = df_raw['Data'].min().date()
max_date = df_raw['Data'].max().date()

date_range = st.sidebar.date_input(
    "Período",
    value=[min_date, max_date],
    min_value=min_date,
    max_value=max_date,
    format="DD/MM/YYYY"
)

if len(date_range) == 2:
    start_date, end_date = date_range
elif len(date_range) == 1:
    start_date, end_date = date_range[0], date_range[0]
else:
    start_date, end_date = min_date, max_date

# CÁLCULO DE DIAS SELECIONADOS (ESSENCIAL PARA A MÉDIA DIÁRIA)
num_dias_selecionados = (end_date - start_date).days + 1
if num_dias_selecionados < 1: num_dias_selecionados = 1

if 'Setor' in df_raw.columns:
    setores = st.sidebar.multiselect("Setor", options=sorted(df_raw['Setor'].unique()))
else: setores = []

colaboradores = st.sidebar.multiselect("Colaborador", options=sorted(df_raw['Colaborador'].unique()))
portais = st.sidebar.multiselect("Portal", options=sorted(df_raw['Portal'].unique()))
transportadoras = st.sidebar.multiselect("Transportadora", options=sorted([t for t in df_raw['Transportadora'].unique() if t not in ['-', 'Não Informado']]))

# Aplica Filtros
df_filtered = df_raw.copy()
df_filtered = df_filtered[(df_filtered['Data'].dt.date >= start_date) & (df_filtered['Data'].dt.date <= end_date)]

if setores and 'Setor' in df_filtered.columns: df_filtered = df_filtered[df_filtered['Setor'].isin(setores)]
if colaboradores: df_filtered = df_filtered[df_filtered['Colaborador'].isin(colaboradores)]
if portais: df_filtered = df_filtered[df_filtered['Portal'].isin(portais)]
if transportadoras: df_filtered = df_filtered[df_filtered['Transportadora'].isin(transportadoras)]

# ==============================================================================
# 4. DASHBOARD & KPIS
# ==============================================================================
st.markdown("## 📊 Visão Geral") 

# KPIs Básicos
total_bruto = df_filtered.shape[0]
total_liquido = df_filtered['Eh_Novo_Episodio'].sum()
taxa_duplicidade = ((total_bruto - total_liquido) / total_bruto * 100) if total_bruto > 0 else 0

# --- CÁLCULO DE CAPACIDADE (META vs REAL) ---
if 'Setor' in df_filtered.columns:
    grp_cols = ['Colaborador', 'Setor']
else:
    grp_cols = ['Colaborador']
    
df_metrics = df_filtered.groupby(grp_cols)['TMA_Valido'].agg(['mean', 'count']).reset_index()
df_metrics = df_metrics[df_metrics['count'] > 5]

# Capacidade Individual Diária (336 min úteis)
TEMPO_UTIL_DIA = 480 * 0.70 
df_metrics['Capacidade_Diaria'] = (TEMPO_UTIL_DIA / df_metrics['mean']).fillna(0).astype(int)

# META: Soma Capacidade Diária do Time
meta_capacidade_dia = df_metrics['Capacidade_Diaria'].sum()

# REAL: Média de produção diária no período selecionado
realizado_medio_dia = int(total_liquido / num_dias_selecionados)

# GAP: Diferença (Se negativo, fica vermelho)
gap_capacidade = realizado_medio_dia - meta_capacidade_dia

# Separação SAC vs PENDENCIA (Para o Tooltip)
cap_sac = 0
cap_pend = 0
if 'Setor' in df_metrics.columns:
    cap_sac = df_metrics[df_metrics['Setor'].astype(str).str.contains('SAC', case=False, na=False)]['Capacidade_Diaria'].sum()
    cap_pend = df_metrics[df_metrics['Setor'].astype(str).str.contains('Pend', case=False, na=False)]['Capacidade_Diaria'].sum()

# Texto de ajuda detalhado
help_capacidade = f"Meta baseada no TMA atual.\n\nDivisão da Meta:\n- SAC: {cap_sac}\n- Pendência: {cap_pend}\n\nRealizado Médio: {realizado_medio_dia}/dia"

# KPI CARDS
k1, k2, k3, k4 = st.columns(4)
k1.metric("📦 Total Registros (Bruto)", f"{total_bruto}")
k2.metric("✅ Atendimentos Reais (2h)", f"{total_liquido}")
k3.metric("⚠️ Taxa de Duplicidade", f"{taxa_duplicidade:.1f}%", delta_color="inverse")

# CARD 4: CAPACIDADE COM ALERTA
# delta_color="normal" -> Positivo=Verde, Negativo=Vermelho
k4.metric(
    "🎯 Capacidade Diária (Meta)", 
    f"{meta_capacidade_dia}", 
    delta=f"{gap_capacidade} (Real: {realizado_medio_dia})",
    delta_color="normal",
    help=help_capacidade
)

st.markdown("---")

tab1, tab2, tab3 = st.tabs(["🚀 Produtividade & Capacidade", "🔥 Causa Raiz (Matrizes)", "🕵️ Risco de Cancelamento"])

# --- ABA 1: PRODUTIVIDADE ---
with tab1:
    st.subheader("1. Volume de Atendimento (Bruto vs Líquido)")
    
    df_vol = df_filtered.groupby('Colaborador').agg(
        Bruto=('Data', 'count'),
        Liquido=('Eh_Novo_Episodio', 'sum'),
        Erros_CRM=('Motivo_CRM', lambda x: x.isin(['SEM ABERTURA DE CRM', 'Não Informado']).sum())
    ).reset_index().sort_values('Liquido', ascending=True)
    
    df_melt = df_vol.melt(id_vars=['Colaborador', 'Erros_CRM'], value_vars=['Bruto', 'Liquido'], var_name='Métrica', value_name='Volume')
    
    max_vol = df_melt['Volume'].max()
    
    fig_prod = px.bar(df_melt, y='Colaborador', x='Volume', color='Métrica', barmode='group', orientation='h',
                      color_discrete_map={'Bruto': '#FFA15A', 'Liquido': '#19D3F3'}, text='Volume',
                      hover_data={'Erros_CRM': True, 'Métrica': True, 'Volume': True, 'Colaborador': False})
    
    fig_prod.update_traces(textposition='outside')
    fig_prod.update_layout(
        height=450, 
        margin=dict(r=50), 
        xaxis=dict(range=[0, max_vol * 1.15]),
        legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5)
    )
    st.plotly_chart(fig_prod, use_container_width=True)

    st.markdown("---")

    st.subheader("2. Projeção de Capacidade (Meta vs Real)")
    
    df_tma = df_filtered.groupby('Colaborador')['TMA_Valido'].agg(['mean', 'count']).reset_index()
    df_tma.columns = ['Colaborador', 'TMA_Medio', 'Amostra']
    df_tma = df_tma[df_tma['Amostra'] > 5] 
    
    df_tma['Capacidade_Diaria'] = (TEMPO_UTIL_DIA / df_tma['TMA_Medio']).fillna(0).astype(int)
    df_tma = df_tma.sort_values('Capacidade_Diaria', ascending=False)

    max_cap = df_tma['Capacidade_Diaria'].max() if not df_tma.empty else 100
    y_limit = max_cap * 1.25

    fig_cap = go.Figure()
    
    fig_cap.add_trace(go.Bar(
        x=df_tma['Colaborador'], y=df_tma['Capacidade_Diaria'], 
        name='Capacidade Projetada', marker_color='#00CC96', text=df_tma['Capacidade_Diaria'], textposition='outside'
    ))
    
    fig_cap.add_trace(go.Scatter(
        x=df_tma['Colaborador'], y=df_tma['TMA_Medio'], 
        mode='lines+markers+text',
        name='TMA Atual (min)', 
        marker=dict(color='#EF553B', size=8),
        line=dict(color='#EF553B', width=2),
        text=df_tma['TMA_Medio'].apply(lambda x: f"{x:.1f}'"), 
        textposition='top center',
        yaxis='y2'
    ))
    
    fig_cap.update_layout(
        height=450,
        yaxis=dict(title='Capacidade (Qtd Atendimentos)', side='left', range=[0, y_limit]),
        yaxis2=dict(title='TMA (Minutos)', overlaying='y', side='right', showgrid=False),
        legend=dict(orientation="h", y=-0.2, x=0.5, xanchor='center'),
        xaxis=dict(title='Colaborador')
    )
    st.plotly_chart(fig_cap, use_container_width=True)
    st.caption("Barra Verde = Capacidade (Eixo Esq). Linha Vermelha = TMA Atual (Eixo Dir).")

    st.markdown("---")

    st.subheader("3. Mapa de Calor (Segunda a Sexta)")
    dias_uteis = ['Segunda-Feira', 'Terça-Feira', 'Quarta-Feira', 'Quinta-Feira', 'Sexta-Feira']
    
    df_heat = df_filtered[df_filtered['Dia_Semana'].isin(dias_uteis)]
    df_heat_grp = df_heat.groupby(['Dia_Semana', 'Hora_Cheia']).size().reset_index(name='Chamados')
    
    fig_heat = px.density_heatmap(
        df_heat_grp, x='Dia_Semana', y='Hora_Cheia', z='Chamados',
        category_orders={"Dia_Semana": dias_uteis}, 
        color_continuous_scale='Viridis', text_auto=True
    )
    fig_heat.update_layout(height=400)
    st.plotly_chart(fig_heat, use_container_width=True)

# --- ABA 2: CAUSA RAIZ ---
with tab2:
    def plot_matrix(df_input, col_x, col_y, title):
        df_clean = df_input[(df_input[col_x] != 'Não Informado') & (df_input[col_y] != 'Não Informado')]
        matrix = pd.crosstab(df_clean[col_y], df_clean[col_x])
        matrix = matrix.loc[(matrix!=0).any(axis=1), (matrix!=0).any(axis=0)]
        
        matrix['Total_Row'] = matrix.sum(axis=1)
        matrix = matrix.sort_values('Total_Row', ascending=False)
        matrix = matrix.drop(columns='Total_Row')
        
        col_sums = matrix.sum().sort_values(ascending=False).index
        matrix = matrix[col_sums]

        if not matrix.empty:
            fig = px.imshow(matrix, text_auto=True, aspect="auto", color_continuous_scale='Reds', title=title)
            fig.update_layout(height=500)
            return fig
        return None

    fig_m1 = plot_matrix(df_filtered, 'Motivo', 'Portal', 'Matriz: Portal (Linha) x Motivo (Coluna)')
    if fig_m1: st.plotly_chart(fig_m1, use_container_width=True)
    else: st.warning("Dados insuficientes.")

    st.markdown("---")

    df_transp_clean = df_filtered[df_filtered['Transportadora'] != '-']
    fig_m2 = plot_matrix(df_transp_clean, 'Motivo', 'Transportadora', 'Matriz: Transportadora (Linha) x Motivo (Coluna)')
    if fig_m2: st.plotly_chart(fig_m2, use_container_width=True)
    else: st.warning("Dados insuficientes.")

# --- ABA 3: REINCIDÊNCIA ---
with tab3:
    st.subheader("🕵️ Risco de Cancelamento (Reincidência Crítica)")
    
    df_chrono = df_filtered.sort_values(by=['ID_Ref', 'Data_Completa'])

    df_reinc = df_chrono.groupby('ID_Ref').agg(
        Episodios_Reais=('Eh_Novo_Episodio', 'sum'),
        Ultimo_Motivo=('Motivo', 'last'),
        Historico_Completo=('Motivo', lambda x: " ➡️ ".join(x.astype(str))),
        Motivos_Unicos=('Motivo', lambda x: list(set(x))),
        Ultima_Data=('Data_Completa', 'max')
    ).reset_index()
    
    df_reinc = df_reinc[df_reinc['ID_Ref'] != 'Não Informado']
    
    df_reinc['Risco_Cancelamento'] = df_reinc['Ultimo_Motivo'].astype(str).str.contains('Cancelamento', case=False, na=False)
    df_reinc['Status_Risco'] = np.where(df_reinc['Risco_Cancelamento'], '🔴 Risco Cancelamento', '🔵 Em Tratativa')
    
    df_criticos = df_reinc[df_reinc['Episodios_Reais'] > 1].copy().sort_values('Episodios_Reais', ascending=False)
    
    qtd_risco = df_criticos[df_criticos['Risco_Cancelamento']].shape[0]
    st.metric("Clientes Reincidentes pedindo Cancelamento (Último Contato)", f"{qtd_risco}", delta="Atenção Prioritária", delta_color="inverse")
    
    st.markdown("---")

    col_chart, col_empty = st.columns([2, 1])
    with col_chart:
        st.markdown("**Quais motivos levam o cliente a voltar? (Top 10)**")
        all_motivos = df_criticos.explode('Motivos_Unicos')
        if not all_motivos.empty:
            counts = all_motivos['Motivos_Unicos'].value_counts().reset_index()
            counts.columns = ['Motivo', 'Volume']
            counts['Porcentagem'] = (counts['Volume'] / counts['Volume'].sum() * 100).map('{:,.1f}%'.format)
            
            fig_motivos = px.bar(
                counts.head(10).sort_values('Volume', ascending=True),
                x='Volume', y='Motivo', orientation='h', text='Porcentagem', color='Volume', color_continuous_scale='Blues'
            )
            fig_motivos.update_traces(textposition='outside')
            fig_motivos.update_layout(height=450, coloraxis_showscale=False, yaxis_title=None)
            st.plotly_chart(fig_motivos, use_container_width=True)
        else:
            st.info("Sem dados de motivos.")

    st.markdown("### 📋 Lista Detalhada de Reincidentes")
    
    df_export = df_criticos[['ID_Ref', 'Episodios_Reais', 'Ultimo_Motivo', 'Status_Risco', 'Historico_Completo', 'Ultima_Data']]
    
    csv = df_export.to_csv(index=False, sep=';').encode('utf-8-sig')
    st.download_button("📥 Baixar Relatório (CSV)", data=csv, file_name='relatorio_risco_cancelamento.csv', mime='text/csv')
    
    st.dataframe(
        df_export.head(50), 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "Historico_Completo": st.column_config.TextColumn("Histórico Cronológico (Evolução)", width="large"),
            "Ultima_Data": st.column_config.DatetimeColumn("Última Interação", format="DD/MM/YYYY HH:mm"),
            "Status_Risco": st.column_config.TextColumn("Status", help="Vermelho = Pedido de Cancelamento")
        }
    )
