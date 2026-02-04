import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# --- AQUI VEM O SEU CÓDIGO DE CARREGAR DADOS E A BARRA LATERAL ---
# (Não apague a parte onde você carrega o arquivo excel/csv e cria o 'df_selection')
# --- INÍCIO DA SUBSTITUIÇÃO: PROJEÇÃO DE CAPACIDADE ---
st.markdown("---")
st.subheader("2. Projeção de Capacidade (Meta Ajustada ao Horário)")

col_cap1, col_cap2 = st.columns(2)
with col_cap1:
    meta_tma_input = st.number_input("Meta TMA (seg)", min_value=10, value=180, step=10)
with col_cap2:
    # Este input ajuda a definir o teto, mas o cálculo priorizará o horário real
    horas_jornada = st.number_input("Jornada Máxima (h)", value=8)

# Verifica se há dados filtrados
if not df_selection.empty:
    # 1. Agrupar dados por colaborador
    # Pegamos a primeira hora (entrada) e a última hora (saída/atual)
    df_perf = df_selection.groupby('Colaborador').agg(
        Qtd_Realizada=('ID', 'count'),
        Hora_Entrada=('Data', 'min'),
        Hora_Ultima_Acao=('Data', 'max')
    ).reset_index()

    # 2. Função para calcular a meta proporcional ao tempo trabalhado
    def calcular_meta_proporcional(row):
        # Calcula quantos segundos a pessoa trabalhou (Do 1º registro até o último)
        # Se quiser considerar até o momento "agora", poderia usar datetime.now(), 
        # mas usar 'Hora_Ultima_Acao' é mais seguro para dados históricos.
        segundos_ativos = (row['Hora_Ultima_Acao'] - row['Hora_Entrada']).total_seconds()
        
        # Se a pessoa acabou de entrar (ex: menos de 10 min), consideramos 1 hora mínima para não zerar a meta
        segundos_considerados = max(segundos_ativos, 3600) 
        
        # A meta é: Tempo Disponível / TMA Alvo
        meta = segundos_considerados / meta_tma_input
        return int(meta)

    # 3. Aplica a lógica
    df_perf['Meta_Fixa'] = df_perf.apply(calcular_meta_proporcional, axis=1)
    
    # Adiciona a cor (Verde se bateu a meta, Vermelho se não)
    df_perf['Cor'] = df_perf.apply(lambda x: '#00CC96' if x['Qtd_Realizada'] >= x['Meta_Fixa'] else '#EF553B', axis=1)

    # 4. Gráfico
    # Ordena do maior realizado para o menor
    df_perf = df_perf.sort_values('Qtd_Realizada', ascending=False)
    
    fig_cap = go.Figure()

    # Barra de Realizado
    fig_cap.add_trace(go.Bar(
        x=df_perf['Colaborador'], 
        y=df_perf['Qtd_Realizada'], 
        name="Realizado",
        text=df_perf['Qtd_Realizada'],
        textposition='auto',
        marker_color='#2E86C1'
    ))

    # Barra de Meta (Calculada proporcionalmente)
    fig_cap.add_trace(go.Bar(
        x=df_perf['Colaborador'], 
        y=df_perf['Meta_Fixa'], 
        name="Meta (Proporcional ao Horário)",
        text=df_perf['Meta_Fixa'],
        textposition='auto',
        marker_color='rgba(50, 50, 50, 0.2)', # Cor neutra para meta
        marker_line_color='#00CC96',
        marker_line_width=2,
        opacity=0.6
    ))

    fig_cap.update_layout(
        title="Capacidade: Real vs Meta (Ajustada pelo horário de entrada)",
        barmode='overlay', # Sobrepõe as barras para facilitar comparação
        height=400
    )

    st.plotly_chart(fig_cap, use_container_width=True)

else:
    st.warning("Sem dados para calcular capacidade.")
# --- FIM DA SUBSTITUIÇÃO ---
