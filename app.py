# --- ABA 3: DEEP DIVE (REINCIDÊNCIA AVANÇADA) ---
with tab3:
    st.subheader("🕵️ Raio-X da Reincidência (Onde perdemos tempo?)")
    
    # 1. PREPARAÇÃO DOS DADOS
    df_reincidencia = df_filtered.groupby('ID_Ref').agg(
        Episodios_Reais=('Eh_Novo_Episodio', 'sum'),
        Total_Bruto=('Data', 'count'),
        Primeiro_Contato=('Data_Completa', 'min'),
        Ultimo_Contato=('Data_Completa', 'max'),
        # CORREÇÃO 1: Junta a lista em uma string única para evitar erro de serialização
        Motivos_Lista=('Motivo', lambda x: ", ".join(sorted(list(set(x))))),
        Transportadora=('Transportadora', 'first'),
        Portal=('Portal', 'first')
    ).reset_index()

    df_reincidencia = df_reincidencia[df_reincidencia['ID_Ref'] != 'Não Informado']
    
    # Cálculos de Tempo
    df_reincidencia['Dias_Em_Aberto'] = (df_reincidencia['Ultimo_Contato'] - df_reincidencia['Primeiro_Contato']).dt.total_seconds() / 86400
    df_reincidencia['Dias_Em_Aberto'] = df_reincidencia['Dias_Em_Aberto'].apply(lambda x: round(x, 1))

    # SEGMENTAÇÃO (CLIENTE ANSIOSO VS CRÔNICO)
    def classificar_reincidencia(row):
        if row['Episodios_Reais'] <= 1:
            return "✅ Resolvido de Primeira"
        elif row['Dias_Em_Aberto'] <= 2 and row['Episodios_Reais'] > 2:
            return "🔥 Cliente Ansioso (Pânico)"
        elif row['Dias_Em_Aberto'] > 5:
            return "🐢 Problema Crônico (Lento)"
        else:
            return "⚠️ Retrabalho Padrão"

    df_reincidencia['Perfil_Cliente'] = df_reincidencia.apply(classificar_reincidencia, axis=1)

    # Filtrar apenas quem tem problema real (>1 episódio)
    df_criticos = df_reincidencia[df_reincidencia['Episodios_Reais'] > 1].copy()

    # 2. KPIS
    total_pedidos_unicos = df_reincidencia.shape[0]
    total_reincidentes = df_criticos.shape[0]
    taxa_reincidencia_global = (total_reincidentes / total_pedidos_unicos * 100) if total_pedidos_unicos > 0 else 0
    contatos_excedentes = df_criticos['Total_Bruto'].sum() - df_criticos.shape[0]
    horas_desperdicadas = (contatos_excedentes * 15) / 60 
    
    col_k1, col_k2, col_k3, col_k4 = st.columns(4)
    col_k1.metric("Taxa de Reincidência Global", f"{taxa_reincidencia_global:.1f}%", help="% de pedidos que voltaram a gerar contato após 24h")
    col_k2.metric("Pedidos com Problema", f"{total_reincidentes}", help="Volume de clientes que retornaram")
    col_k3.metric("Horas de Equipe 'Jogadas Fora'", f"{horas_desperdicadas:.0f}h", help="Estimativa: 15min por contato excedente")
    col_k4.metric("Média Dias para Resolução", f"{df_criticos['Dias_Em_Aberto'].mean():.1f} dias", help="Tempo médio entre o primeiro e último contato dos reincidentes")
    
    st.markdown("---")

    # 3. GRÁFICOS
    col_g1, col_g2 = st.columns([2, 1])
    
    with col_g1:
        st.markdown("#### 🔍 Matriz de Dispersão: Quem são os casos graves?")
        if not df_criticos.empty:
            fig_scatter = px.scatter(
                df_criticos,
                x='Dias_Em_Aberto',
                y='Episodios_Reais',
                color='Perfil_Cliente',
                size='Total_Bruto',
                hover_data=['ID_Ref', 'Motivos_Lista', 'Transportadora'],
                color_discrete_map={
                    "🔥 Cliente Ansioso (Pânico)": "#FF4B4B", 
                    "🐢 Problema Crônico (Lento)": "#FFA15A", 
                    "⚠️ Retrabalho Padrão": "#636EFA"
                }
            )
            fig_scatter.add_vline(x=5, line_width=1, line_dash="dash", line_color="grey")
            fig_scatter.add_hline(y=3, line_width=1, line_dash="dash", line_color="grey")
            fig_scatter.update_layout(height=450, xaxis_title="Dias em Aberto (Duração)", yaxis_title="Qtd de Episódios (Insistência)")
            st.plotly_chart(fig_scatter, use_container_width=True)
        else:
            st.info("Sem dados de reincidência para plotar.")

    with col_g2:
        st.markdown("#### 🏆 Quem gera mais Retrabalho?")
        opt_view = st.radio("Ver por:", ["Transportadora", "Portal"], horizontal=True)
        
        df_view = df_criticos[opt_view].value_counts().reset_index()
        df_view.columns = [opt_view, 'Qtd Reincidentes']
        
        fig_bar_r = px.bar(
            df_view.head(8), x='Qtd Reincidentes', y=opt_view, orientation='h',
            text='Qtd Reincidentes', color='Qtd Reincidentes', color_continuous_scale='Reds'
        )
        fig_bar_r.update_layout(height=400, yaxis={'categoryorder':'total ascending'}, coloraxis_showscale=False)
        st.plotly_chart(fig_bar_r, use_container_width=True)

    # 4. TABELA (CORRIGIDA)
    st.markdown("### 📋 Lista de Fregueses (Top 50 Críticos)")
    if not df_criticos.empty:
        df_table = df_criticos[['ID_Ref', 'Episodios_Reais', 'Dias_Em_Aberto', 'Perfil_Cliente', 'Motivos_Lista', 'Transportadora']].copy()
        df_table = df_table.sort_values(by=['Episodios_Reais', 'Dias_Em_Aberto'], ascending=False).head(50)
        
        # CORREÇÃO 2: Convertendo o valor máximo para int padrão do Python
        max_val = int(df_criticos['Episodios_Reais'].max())

        st.dataframe(
            df_table,
            column_config={
                "ID_Ref": st.column_config.TextColumn("Pedido/NF"),
                "Episodios_Reais": st.column_config.ProgressColumn(
                    "Episódios", 
                    format="%d", 
                    min_value=0, 
                    max_value=max_val # Usando o valor corrigido aqui
                ),
                "Dias_Em_Aberto": st.column_config.NumberColumn("Dias Aberto", format="%.1f d"),
                "Perfil_Cliente": st.column_config.TextColumn("Diagnóstico"),
                "Motivos_Lista": "Motivos Citados",
                "Transportadora": "Transp."
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.success("Nenhum caso crítico encontrado!")
