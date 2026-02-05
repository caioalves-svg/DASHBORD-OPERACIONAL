import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import datetime, timedelta, time
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
            # Remove ponto e vírgula e quebras de linha para CSV seguro
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
# 3. FILTROS (LÓGICA DO DIA ATUAL)
# ==============================================================================
st.sidebar.header("🔍 Filtros")
st.sidebar.markdown("---")

min_date = df_raw['Data'].min().date()
# Garante que o calendário vá pelo menos até HOJE, mesmo que a planilha esteja atrasada
max_date = max(df_raw['Data'].max().date(), datetime.now().date())
today = datetime.now().date()

# Se 'hoje' for menor que a data mínima da planilha (caso raro de planilha futura), ajusta
if today < min_date:
    default_val = [min_date, min_date]
else:
    default_val = [today, today]

date_range = st.sidebar.date_input(
    "Período",
    value=default_val, # Valor padrão: Hoje
    min_value=min_date,
    max_value=max_date,
    format="DD/MM/YYYY"
)

if len(date_range) == 2:
    start_date, end_date = date_range
elif len(date_range) == 1:
    start_date, end_date = date_range[0], date_range[0]
else:
    start_date, end_date = today, today

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

# KPI CARDS
k1, k2, k3 = st.columns(3)
k1.metric("📦 Total Registros (Bruto)", f"{total_bruto}")
k2.metric("✅ Atendimentos Reais (2h)", f"{total_liquido}")
k3.metric("⚠️ Taxa de Duplicidade", f"{taxa_duplicidade:.1f}%", delta_color="inverse")

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
    
    # --- CÁLCULO DE META DINÂMICA (07:30 - 17:18) ---
    TMA_TARGET_SAC = 5 + (23/60)  # 5.383 min
    TMA_TARGET_PEND = 5 + (8/60)  # 5.133 min
    FIM_JORNADA_HORA = 17.3       # 17:18

    # Identifica Hora de Chegada
    df_presenca = df_filtered.groupby(['Colaborador', 'Data_Str', 'Setor'])['Data_Completa'].min().reset_index()
    df_presenca.rename(columns={'Data_Completa': 'Hora_Entrada'}, inplace=True)

    def calcular_meta_individual(row):
        hora_entrada = row['Hora_Entrada'].hour + (row['Hora_Entrada'].minute / 60)
        
        # Início Jornada: 07:30 (7.5)
        hora_inicio_valida = max(7.5, hora_entrada)
        
        horas_disponiveis = FIM_JORNADA_HORA - hora_inicio_valida
        if horas_disponiveis <= 0:
            return 0, 0
        
        minutos_totais = horas_disponiveis * 60
        minutos_uteis = minutos_totais * 0.70 # 30% Ociosidade
        
        setor_str = str(row['Setor']).upper()
        tma_alvo = TMA_TARGET_SAC 
        if 'PEND' in setor_str or 'ÊNCIA' in setor_str:
            tma_alvo = TMA_TARGET_PEND
        
        meta = int(minutos_uteis / tma_alvo)
        
        meta_sac = meta if tma_alvo == TMA_TARGET_SAC else 0
        meta_pend = meta if tma_alvo == TMA_TARGET_PEND else 0
        
        return meta_sac, meta_pend

    metas = df_presenca.apply(calcular_meta_individual, axis=1)
    df_presenca['Meta_SAC'] = [x[0] for x in metas]
    df_presenca['Meta_PEND'] = [x[1] for x in metas]

    # Totais
    meta_total_sac = df_presenca['Meta_SAC'].sum()
    meta_total_pend = df_presenca['Meta_PEND'].sum()

    # Realizado
    realizado_sac = 0
    realizado_pend = 0
    if 'Setor' in df_filtered.columns:
        realizado_sac = df_filtered[df_filtered['Setor'].astype(str).str.contains('SAC', case=False, na=False)]['Eh_Novo_Episodio'].sum()
        realizado_pend = df_filtered[df_filtered['Setor'].astype(str).str.contains('Pend', case=False, na=False)]['Eh_Novo_Episodio'].sum()

    # Projeção (Cor)
    agora = datetime.now()
    horas_restantes_hoje = max(0, 17.3 - (agora.hour + agora.minute/60))
    is_today = end_date == datetime.today().date()

    def get_status_cor(realizado, meta, tma_target, colaboradores_ativos_setor):
        if meta == 0: return "off"
        if is_today:
            capacidade_restante = (colaboradores_ativos_setor * horas_restantes_hoje * 60 * 0.70) / tma_target
            projecao_final = realizado + capacidade_restante
            return "normal" if projecao_final >= meta else "inverse"
        else:
            return "normal" if realizado >= meta else "inverse"

    qtd_pessoas_sac = df_presenca[df_presenca['Meta_SAC'] > 0].shape[0]
    qtd_pessoas_pend = df_presenca[df_presenca['Meta_PEND'] > 0].shape[0]

    cor_sac = get_status_cor(realizado_sac, meta_total_sac, TMA_TARGET_SAC, qtd_pessoas_sac)
    cor_pend = get_status_cor(realizado_pend, meta_total_pend, TMA_TARGET_PEND, qtd_pessoas_pend)
    
    perc_sac = (realizado_sac / meta_total_sac * 100) if meta_total_sac > 0 else 0
    perc_pend = (realizado_pend / meta_total_pend * 100) if meta_total_pend > 0 else 0

    # Cards de Meta (SEPARADOS E NO TOPO DO GRÁFICO DE CAPACIDADE)
    cm1, cm2 = st.columns(2)
    cm1.metric("🎯 Meta SAC (%)", f"{perc_sac:.1f}%", delta=f"{realizado_sac} / {meta_total_sac} (Meta)", delta_color=cor_sac)
    cm2.metric("⏳ Meta Pendência (%)", f"{perc_pend:.1f}%", delta=f"{realizado_pend} / {meta_total_pend} (Meta)", delta_color=cor_pend)
    
    st.markdown("<br>", unsafe_allow_html=True)

    # Gráfico de Capacidade Individual
    df_tma = df_filtered.groupby('Colaborador')['TMA_Valido'].agg(['mean', 'count']).reset_index()
    df_tma.columns = ['Colaborador', 'TMA_Medio', 'Amostra']
    df_tma = df_tma[df_tma['Amostra'] > 5] 
    
    # Dia Cheio: 07:30 a 17:18
    TEMPO_UTIL_DIA_GRAFICO = (17.3 - 7.5) * 60 * 0.70
    
    df_tma['Capacidade_Diaria'] = (TEMPO_UTIL_DIA_GRAFICO / df_tma['TMA_Medio']).fillna(0).astype(int)
    df_tma = df_tma.sort_values('Capacidade_Diaria', ascending=False)

    max_cap = df_tma['Capacidade_Diaria'].max() if not df_tma.empty else 100
    y_limit = max_cap * 1.25

    fig_cap = go.Figure()
    fig_cap.add_trace(go.Bar(
        x=df_tma['Colaborador'], y=df_tma['Capacidade_Diaria'], 
        name='Capacidade Projetada (Dia Cheio)', marker_color='#00CC96', text=df_tma['Capacidade_Diaria'], textposition='outside'
    ))
    fig_cap.add_trace(go.Scatter(
        x=df_tma['Colaborador'], y=df_tma['TMA_Medio'], 
        mode='lines+markers+text',
        name='TMA Atual (min)', marker=dict(color='#EF553B', size=8), line=dict(color='#EF553B', width=2),
        text=df_tma['TMA_Medio'].apply(lambda x: f"{x:.1f}'"), textposition='top center', yaxis='y2'
    ))
    
    fig_cap.update_layout(
        height=450,
        yaxis=dict(title='Capacidade (Qtd Atendimentos)', side='left', range=[0, y_limit]),
        yaxis2=dict(title='TMA (Minutos)', overlaying='y', side='right', showgrid=False),
        legend=dict(orientation="h", y=-0.2, x=0.5, xanchor='center'),
        xaxis=dict(title='Colaborador')
    )
    st.plotly_chart(fig_cap, use_container_width=True)
    st.caption("Nota: O gráfico projeta um dia cheio (07:30 às 17:18) para fins comparativos.")

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
