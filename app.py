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
# 2. ETL & CÁLCULOS AVANÇADOS (TMA E REINCIDÊNCIA)
# ==============================================================================
@st.cache_data(ttl=600)
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df = conn.read(worksheet="Página1")
    except:
        df = conn.read()

    # --- TRATAMENTO BÁSICO ---
    df['Data'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['Data'])

    # Padronização de Textos
    cols_texto = ['Colaborador', 'Setor', 'Portal', 'Transportadora', 'Motivo', 'Motivo_CRM', 'Numero_Pedido', 'Nota_Fiscal']
    for col in cols_texto:
        if col in df.columns:
            df[col] = df[col].fillna("Não Informado").astype(str).replace("nan", "Não Informado").str.strip()

    # Data e Hora
    if 'Hora' in df.columns:
        df['Hora_Str'] = df['Hora'].astype(str)
        df['Hora_Cheia'] = df['Hora_Str'].str.slice(0, 2) + ":00"
    else:
        df['Hora_Cheia'] = df['Data'].dt.hour.astype(str).str.zfill(2) + ":00"
        df['Hora_Str'] = df['Data'].dt.strftime('%H:%M:%S')

    # Cria Data Completa (Datetime real) para cálculos de tempo
    try:
        df['Data_Completa'] = df['Data'] + pd.to_timedelta(df['Hora_Str'])
    except:
        df['Data_Completa'] = df['Data']

    # Chave Única
    df['ID_Ref'] = np.where(df['Numero_Pedido'] != "Não Informado", df['Numero_Pedido'], df['Nota_Fiscal'])
    df['Data_Str'] = df['Data'].dt.strftime('%Y-%m-%d')
    # Nota: A chave única abaixo é para contagem simples diária
    df['Chave_Unica_Dia'] = df['Data_Str'] + "_" + df['Colaborador'] + "_" + df['ID_Ref']

    # --- 1. LÓGICA DE DUPLICIDADE (JANELA DE 2 HORAS) ---
    df = df.sort_values(by=['ID_Ref', 'Data_Completa'])
    df['Tempo_Desde_Ultimo_Contato'] = df.groupby('ID_Ref')['Data_Completa'].diff()
    
    # Se passou mais de 2 horas (ou é o primeiro), é um novo episódio
    df['Eh_Novo_Episodio'] = np.where(
        (df['Tempo_Desde_Ultimo_Contato'].isnull()) | (df['Tempo_Desde_Ultimo_Contato'] > pd.Timedelta(hours=2)), 
        1, 
        0
    )

    # --- 2. CÁLCULO DE TMA ESTIMADO (Produtividade) ---
    # Ordena por Colaborador e Hora para ver a "Esteira de Trabalho"
    df = df.sort_values(by=['Colaborador', 'Data_Completa'])
    
    # Calcula diferença para o PRÓXIMO registro do mesmo colaborador
    df['Tempo_Ate_Proximo'] = df.groupby('Colaborador')['Data_Completa'].shift(-1) - df['Data_Completa']
    df['Minutos_No_Atendimento'] = df['Tempo_Ate_Proximo'].dt.total_seconds() / 60
    
    # Filtro de Higiene para TMA: 
    # Consideramos apenas tempos entre 30 segundos (evita copy/paste rápido) e 40 minutos (evita pausas/almoço)
    df['TMA_Valido'] = np.where(
        (df['Minutos_No_Atendimento'] > 0.5) & (df['Minutos_No_Atendimento'] <= 40),
        df['Minutos_No_Atendimento'],
        np.nan
    )

    return df

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
start_date, end_date = st.sidebar.date_input("Período", [min_date, max_date], min_value=min_date, max_value=max_date, format="DD/MM/YYYY")

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
# 4. DASHBOARD
# ==============================================================================
st.title("DASHBOARD OPERACIONAL")

# KPIs Principais
total_bruto = df_filtered.shape[0]
total_liquido = df_filtered['Eh_Novo_Episodio'].sum() # Usa a nova lógica de 2h
taxa_reincidencia = ((total_bruto - total_liquido) / total_bruto * 100) if total_bruto > 0 else 0
crm_ok = df_filtered[~df_filtered['Motivo_CRM'].isin(['SEM ABERTURA DE CRM', 'Não Informado'])].shape[0]
aderencia_crm = (crm_ok / total_bruto * 100) if total_bruto > 0 else 0

k1, k2, k3, k4 = st.columns(4)
k1.metric("📦 Total Registros (Bruto)", f"{total_bruto}")
k2.metric("✅ Atendimentos Reais (2h)", f"{total_liquido}", help="Agrupado por janela de 2 horas")
k3.metric("⚠️ Taxa de Retrabalho", f"{taxa_reincidencia:.1f}%", delta_color="inverse")
k4.metric("🛡️ Aderência CRM", f"{aderencia_crm:.1f}%")

st.markdown("---")

tab1, tab2, tab3 = st.tabs(["🚀 Produtividade & Capacidade", "🔥 Causa Raiz", "🕵️ Reincidentes (Casos Críticos)"])

# --- ABA 1: PRODUTIVIDADE E CAPACIDADE (NOVO) ---
with tab1:
    st.subheader("1. Análise de Capacidade Individual (Projeção)")
    
    # Cálculo do TMA por Colaborador
    df_tma = df_filtered.groupby('Colaborador')['TMA_Valido'].agg(['mean', 'count']).reset_index()
    df_tma.columns = ['Colaborador', 'TMA_Medio', 'Amostra_Atendimentos']
    
    # Filtra quem tem pouca amostra para não distorcer
    df_tma = df_tma[df_tma['Amostra_Atendimentos'] > 5]
    
    # Lógica de Cálculo de Capacidade (Sua fórmula)
    # 8 horas = 480 min. -30% ociosidade = 336 min úteis.
    TEMPO_UTIL_DIA = 480 * 0.70 # 336 minutos
    
    df_tma['Capacidade_Diaria'] = TEMPO_UTIL_DIA / df_tma['TMA_Medio']
    df_tma['Capacidade_Diaria'] = df_tma['Capacidade_Diaria'].fillna(0).astype(int)
    
    # Visualização Combinada
    col_p1, col_p2 = st.columns([2, 1])
    
    with col_p1:
        st.markdown("**Capacidade de Entregas por Dia (Meta vs Real)**")
        # Gráfico de Barras com Linha de TMA
        fig_cap = go.Figure()
        
        # Barra de Capacidade
        fig_cap.add_trace(go.Bar(
            x=df_tma['Colaborador'],
            y=df_tma['Capacidade_Diaria'],
            name='Projeção Entregas/Dia',
            marker_color='#00CC96',
            text=df_tma['Capacidade_Diaria'],
            textposition='auto'
        ))
        
        # Linha de TMA (Eixo secundário)
        fig_cap.add_trace(go.Scatter(
            x=df_tma['Colaborador'],
            y=df_tma['TMA_Medio'],
            name='TMA (Minutos)',
            yaxis='y2',
            mode='lines+markers+text',
            line=dict(color='#EF553B', width=3),
            text=df_tma['TMA_Medio'].apply(lambda x: f"{x:.1f}'"),
            textposition='top center'
        ))
        
        fig_cap.update_layout(
            height=450,
            yaxis=dict(title='Qtd Atendimentos (Projeção)'),
            yaxis2=dict(title='TMA (Minutos)', overlaying='y', side='right', showgrid=False),
            legend=dict(orientation='h', y=1.1, x=0.5, xanchor='center')
        )
        st.plotly_chart(fig_cap, use_container_width=True)
        st.caption(f"ℹ️ Cálculo: (480min - 30% Ociosidade) / TMA Médio. Amostra mínima de 5 atendimentos.")

    with col_p2:
        st.markdown("**Volume Realizado (Total Período)**")
        df_vol = df_filtered['Colaborador'].value_counts().reset_index()
        df_vol.columns = ['Colaborador', 'Total']
        
        fig_vol = px.bar(df_vol, x='Total', y='Colaborador', orientation='h', text='Total', color='Total', color_continuous_scale='Blues')
        fig_vol.update_layout(height=450, coloraxis_showscale=False)
        st.plotly_chart(fig_vol, use_container_width=True)

    st.markdown("---")
    
    # Heatmap continua útil para ver horário de pico
    st.subheader("2. Mapa de Calor (Momentos de Maior Pressão)")
    dias_ordem = ['Segunda-Feira', 'Terça-Feira', 'Quarta-Feira', 'Quinta-Feira', 'Sexta-Feira', 'Sábado', 'Domingo']
    df_heat = df_filtered.groupby(['Dia_Semana', 'Hora_Cheia']).size().reset_index(name='Chamados')
    fig_heat = px.density_heatmap(df_heat, x='Dia_Semana', y='Hora_Cheia', z='Chamados',
                                  category_orders={"Dia_Semana": dias_ordem}, color_continuous_scale='Viridis', text_auto=True)
    st.plotly_chart(fig_heat, use_container_width=True)

# --- ABA 2: CAUSA RAIZ ---
with tab2:
    st.subheader("1. Pareto de Motivos (80/20)")
    df_pareto = df_filtered['Motivo'].value_counts().reset_index()
    df_pareto.columns = ['Motivo', 'Qtd']
    df_pareto = df_pareto[df_pareto['Motivo'] != 'Não Informado']
    df_pareto['Acumulado'] = df_pareto['Qtd'].cumsum()
    df_pareto['Perc'] = (df_pareto['Acumulado'] / df_pareto['Qtd'].sum()) * 100

    fig_pareto = go.Figure()
    fig_pareto.add_trace(go.Bar(x=df_pareto['Motivo'], y=df_pareto['Qtd'], name='Volume', marker_color='#636EFA', text=df_pareto['Qtd'], textposition='auto'))
    fig_pareto.add_trace(go.Scatter(x=df_pareto['Motivo'], y=df_pareto['Perc'], name='% Acumulado', yaxis='y2', mode='lines+markers+text', 
                                    line=dict(color='red', width=3), text=df_pareto['Perc'].apply(lambda x: f'{x:.0f}%'), textposition='top center'))
    fig_pareto.update_layout(height=450, yaxis=dict(title='Volume'), yaxis2=dict(title='% Acumulado', overlaying='y', side='right', range=[0, 115], showgrid=False))
    st.plotly_chart(fig_pareto, use_container_width=True)
    
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        st.subheader("Matriz: Portal vs Motivo")
        df_matrix = df_filtered[(df_filtered['Motivo'] != 'Não Informado') & (df_filtered['Portal'] != 'Não Informado')]
        if not df_matrix.empty:
            matrix_data = pd.crosstab(df_matrix['Portal'], df_matrix['Motivo'])
            fig_matrix = px.imshow(matrix_data, text_auto=True, aspect="auto", color_continuous_scale='Reds')
            st.plotly_chart(fig_matrix, use_container_width=True)
            
    with col_c2:
        st.subheader("Transportadoras (Quem gera mais volume?)")
        df_transp = df_filtered[~df_filtered['Transportadora'].isin(['-', 'Não Informado'])]
        df_tree = df_transp['Transportadora'].value_counts().reset_index()
        df_tree.columns = ['Transportadora', 'Volume']
        fig_bar_trans = px.bar(df_tree.head(10), y='Transportadora', x='Volume', orientation='h', text='Volume', color='Volume', color_continuous_scale='Blues')
        fig_bar_trans.update_layout(yaxis={'categoryorder':'total ascending'}, coloraxis_showscale=False)
        st.plotly_chart(fig_bar_trans, use_container_width=True)

# --- ABA 3: REINCIDENTES (SEM FOCO EM TEMPO DE RESOLUÇÃO) ---
with tab3:
    st.subheader("🕵️ Fregueses do Problema (Intensidade de Contato)")
    st.markdown("Como não temos a data de fim do chamado, analisamos aqui a **intensidade**: Clientes que precisaram entrar em contato múltiplas vezes (intervalos > 2h).")

    # Agrupa por ID_Ref (Pedido/NF)
    df_reinc = df_filtered.groupby('ID_Ref').agg(
        Episodios_Reais=('Eh_Novo_Episodio', 'sum'),
        Total_Interacoes=('Data', 'count'),
        Primeiro_Contato=('Data_Completa', 'min'),
        Ultimo_Contato=('Data_Completa', 'max'),
        Motivos_Lista=('Motivo', lambda x: ", ".join(sorted(list(set(x))))),
        Transportadora=('Transportadora', 'first'),
        Portal=('Portal', 'first')
    ).reset_index()
    
    df_reinc = df_reinc[df_reinc['ID_Ref'] != 'Não Informado']
    
    # Janela de Contato (Dias entre o primeiro e o último "oi")
    # Isso NÃO é tempo de resolução, é tempo de "incomodação"
    df_reinc['Janela_Contato_Dias'] = (df_reinc['Ultimo_Contato'] - df_reinc['Primeiro_Contato']).dt.total_seconds() / 86400
    df_reinc['Janela_Contato_Dias'] = df_reinc['Janela_Contato_Dias'].apply(lambda x: round(x, 1))
    
    # Filtra apenas quem voltou a ligar (>1 episódio)
    df_criticos = df_reinc[df_reinc['Episodios_Reais'] > 1].copy()
    
    col_g1, col_g2 = st.columns([2, 1])
    
    with col_g1:
        st.markdown("#### Top 10 Clientes com Mais Episódios")
        if not df_criticos.empty:
            # Gráfico de barras simples e direto: Quem são os campeões de contato
            top_10 = df_criticos.sort_values('Episodios_Reais', ascending=False).head(10)
            fig_top = px.bar(
                top_10, 
                x='Episodios_Reais', 
                y='ID_Ref', 
                orientation='h',
                text='Episodios_Reais',
                color='Janela_Contato_Dias', # Pinta pela duração da janela
                title="Top 10 Reincidentes (Cor = Janela de Dias em Aberto)",
                labels={'ID_Ref': 'Pedido/NF', 'Episodios_Reais': 'Qtd de Atendimentos (>2h)'},
                color_continuous_scale='Reds'
            )
            fig_top.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_top, use_container_width=True)
        else:
            st.info("Nenhum reincidente encontrado com a janela de 2h.")

    with col_g2:
        st.markdown("#### Onde está a Reincidência?")
        opt = st.radio("Agrupar por:", ["Transportadora", "Portal"], horizontal=True, key='reinc_opt')
        df_grp = df_criticos[~df_criticos[opt].isin(['-', 'Não Informado'])]
        df_grp = df_grp[opt].value_counts().reset_index()
        df_grp.columns = [opt, 'Qtd Clientes Reincidentes']
        
        if not df_grp.empty:
            fig_r = px.bar(df_grp.head(8), x='Qtd Clientes Reincidentes', y=opt, orientation='h', text='Qtd Clientes Reincidentes', color_discrete_sequence=['#FFA15A'])
            fig_r.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_r, use_container_width=True)
        else:
            st.warning("Sem dados.")

    st.markdown("### 📋 Lista Completa para Baixar")
    if not df_criticos.empty:
        df_export = df_criticos[['ID_Ref', 'Episodios_Reais', 'Janela_Contato_Dias', 'Motivos_Lista', 'Transportadora', 'Portal']].sort_values('Episodios_Reais', ascending=False)
        
        csv = df_export.to_csv(index=False, sep=';').encode('utf-8')
        st.download_button("📥 Baixar CSV (Excel)", data=csv, file_name='reincidentes_criticos.csv', mime='text/csv')
        
        max_val = int(df_criticos['Episodios_Reais'].max())
        st.dataframe(
            df_export.head(50),
            column_config={
                "ID_Ref": "Pedido/NF",
                "Episodios_Reais": st.column_config.ProgressColumn("Episódios", format="%d", min_value=0, max_value=max_val),
                "Janela_Contato_Dias": st.column_config.NumberColumn("Janela (Dias)", help="Tempo entre o primeiro e o último registro"),
                "Motivos_Lista": "Histórico de Motivos"
            },
            hide_index=True,
            use_container_width=True
        )
