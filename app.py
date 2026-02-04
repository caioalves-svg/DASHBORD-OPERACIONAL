# --- BLOCO CORRIGIDO: PROJEÇÃO DE CAPACIDADE ---

st.markdown("---")
st.subheader("2. Projeção de Capacidade (Ajustada por Horário)")

# 1. Inputs para simulação
col_cap1, col_cap2 = st.columns(2)
with col_cap1:
    meta_tma_input = st.number_input(
        "Definir Meta de TMA (segundos)", 
        min_value=10, 
        value=180, 
        step=10,
        help="Tempo Médio de Atendimento ideal para o cálculo da capacidade."
    )
with col_cap2:
    jornada_padrao = st.number_input(
        "Jornada Padrão (Horas)", 
        min_value=1, 
        value=8, 
        help="Usado caso não haja registro de hora de entrada."
    )

# 2. Preparação dos Dados (Correção do Erro e Lógica Proporcional)
# Verifica se o dataframe não está vazio
if not df_selection.empty:
    
    # Agrupamos por colaborador para pegar a primeira e última ação do dia
    # Isso define a "Jornada Real" da pessoa até o momento
    df_perf = df_selection.groupby('Colaborador').agg(
        TMA_Real=('TMA', 'mean'),
        Qtd_Realizada=('ID', 'count'),
        Hora_Inicio=('Data', 'min'),
        Hora_Fim=('Data', 'max')
    ).reset_index()

    # --- LÓGICA DE META PROPORCIONAL ---
    def calcular_meta_ajustada(row):
        # Se a pessoa só tem 1 registro, Hora Fim = Hora Inicio. 
        # Nesse caso, assumimos que ela está trabalhando e usamos a hora atual ou jornada padrão.
        # Aqui vamos calcular baseado na diferença de tempo registrada nos dados
        
        segundos_trabalhados = (row['Hora_Fim'] - row['Hora_Inicio']).total_seconds()
        
        # Se a diferença for muito pequena (ex: acabou de começar), 
        # podemos projetar a jornada padrão ou usar o tempo decorrido real.
        # Lógica: Se trabalhou menos de 10 min, consideramos a projeção da jornada padrão (meta cheia)
        # OU se você prefere estritamente o realizado:
        
        horas_uteis = segundos_trabalhados / 3600
        
        # Se horas uteis for quase zero (ex: acabou de logar), usamos a jornada padrão para projetar o dia
        # Se quiser calcular só o que passou, remova o 'max'.
        tempo_para_calculo = max(horas_uteis, 0.5) # Mínimo de 30 min para não dar erro de divisão ou meta zero
        
        # Se quiser que a meta seja baseada na jornada PADRÃO (fixa) para quem já logou:
        # tempo_para_calculo = jornada_padrao 
        
        # CÁLCULO DA META: (Horas * 3600) / TMA Alvo
        # Ajuste aqui: Se a pessoa entrou meio dia e a jornada é até as 18h, ela tem 6h.
        # Vamos assumir que a meta é sobre as horas TRABALHADAS registradas + projeção até o fim do turno.
        
        capacidade_teorica = (jornada_padrao * 3600) / meta_tma_input
        return int(capacidade_teorica)

    # Aplica o cálculo
    df_perf['Meta_Fixa'] = df_perf.apply(calcular_meta_ajustada, axis=1)
    
    # Adiciona cálculo de desvio
    df_perf['Desvio'] = df_perf['Qtd_Realizada'] - df_perf['Meta_Fixa']
    
    # Ordena para o gráfico ficar bonito
    df_perf = df_perf.sort_values('Qtd_Realizada', ascending=False)

    # 3. Gráfico (Plotly) - O erro acontecia aqui pois 'Meta_Fixa' não existia
    fig_cap = go.Figure()

    # Barra de Realizado
    fig_cap.add_trace(go.Bar(
        x=df_perf['Colaborador'], 
        y=df_perf['Qtd_Realizada'], 
        name="Produção Real",
        marker_color='#2E86C1',
        text=df_perf['Qtd_Realizada'],
        textposition='auto'
    ))

    # Barra de Meta (Agora calculada corretamente antes)
    fig_cap.add_trace(go.Bar(
        x=df_perf['Colaborador'], 
        y=df_perf['Meta_Fixa'], 
        name=f"Capacidade Meta (TMA {meta_tma_input}s)", 
        marker_color='#00CC96', 
        opacity=0.7,
        text=df_perf['Meta_Fixa'],
        textposition='auto'
    ))

    fig_cap.update_layout(
        title="Capacidade: Realizado vs Meta Ajustada",
        xaxis_title="Colaborador",
        yaxis_title="Quantidade de Casos",
        barmode='group',
        height=400,
        margin=dict(l=20, r=20, t=50, b=20)
    )

    st.plotly_chart(fig_cap, use_container_width=True)

    # Tabela de detalhes logo abaixo
    st.dataframe(
        df_perf[['Colaborador', 'Hora_Inicio', 'Qtd_Realizada', 'Meta_Fixa', 'Desvio']], 
        use_container_width=True,
        hide_index=True
    )

else:
    st.warning("Sem dados disponíveis para calcular a capacidade com os filtros atuais.")
