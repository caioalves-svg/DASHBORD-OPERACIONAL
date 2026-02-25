import pandas as pd
import numpy as np
from datetime import timedelta

def process_data(df):
    """Realiza limpeza, tratamento e aplica regras de negócio."""
    
    # 1. Tratamento de Datas
    df['Data'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['Data'])

    # 2. Tratamento de Textos
    cols_texto = ['Colaborador', 'Setor', 'Portal', 'Transportadora', 'Motivo', 'Motivo_CRM', 'Numero_Pedido', 'Nota_Fiscal']
    for col in cols_texto:
        if col in df.columns:
            df[col] = df[col].fillna("Não Informado").astype(str).replace("nan", "Não Informado").str.strip().str.replace(';', ',').str.replace('\n', ' ')

    # 3. Construção de Data/Hora Completa
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

    # 4. IDs de Referência
    df['ID_Ref'] = np.where(df['Numero_Pedido'] != "Não Informado", df['Numero_Pedido'], df['Nota_Fiscal'])
    df['ID_Ref'] = df['ID_Ref'].astype(str)
    df['Data_Str'] = df['Data'].dt.strftime('%Y-%m-%d')

    # ==============================================================================
    # REGRA DE NEGÓCIO: DUPLICIDADE (COM EXCEÇÕES SOLICITADAS)
    # ==============================================================================
    df = df.sort_values(by=['ID_Ref', 'Data_Completa'])
    df['Tempo_Desde_Ultimo_Contato'] = df.groupby('ID_Ref')['Data_Completa'].diff()

    # Flags de verificação
    is_sac = df['Setor'].astype(str).str.upper().str.contains('SAC', na=False)
    is_sem_nf = df['Nota_Fiscal'].astype(str).str.upper().str.contains('SEM NF', na=False)
    is_reclame_aqui = df['Motivo'].astype(str).str.upper().str.contains('RECLAME AQUI', na=False)

    # Condição padrão: Passou 2 horas ou é o primeiro contato
    condicao_padrao_tempo = (df['Tempo_Desde_Ultimo_Contato'].isnull()) | (df['Tempo_Desde_Ultimo_Contato'] > pd.Timedelta(hours=2))

    # APLICAÇÃO DA LÓGICA DE EXCEÇÃO:
    # Conta como Novo Episódio (Produtividade) se:
    # 1. Regra de tempo padrão for atendida
    # 2. OU se for SAC e a nota for "SEM NF"
    # 3. OU se for SAC e o motivo for "RECLAME AQUI"
    df['Eh_Novo_Episodio'] = np.where(
        condicao_padrao_tempo | (is_sac & is_sem_nf) | (is_sac & is_reclame_aqui), 
        1, 
        0
    )

    # ==============================================================================
    # CÁLCULO DE TMA
    # ==============================================================================
    df = df.sort_values(by=['Colaborador', 'Data_Completa'])
    df['Tempo_Ate_Proximo'] = df.groupby('Colaborador')['Data_Completa'].shift(-1) - df['Data_Completa']
    df['Minutos_No_Atendimento'] = df['Tempo_Ate_Proximo'].dt.total_seconds() / 60
    
    df['TMA_Valido'] = np.where(
        (df['Minutos_No_Atendimento'] > 0.5) & (df['Minutos_No_Atendimento'] <= 40),
        df['Minutos_No_Atendimento'],
        np.nan
    )

    return df

def calculate_meta_logic(df_filtered, end_date):
    """Calcula as metas dinâmicas de SAC e Pendência."""
    # Constantes
    TMA_TARGET_SAC = 5 + (23/60)
    TMA_TARGET_PEND = 5 + (8/60)
    FIM_JORNADA_HORA = 17.3 # 17:18

    # Identifica Hora de Chegada
    df_presenca = df_filtered.groupby(['Colaborador', 'Data_Str', 'Setor'])['Data_Completa'].min().reset_index()
    df_presenca.rename(columns={'Data_Completa': 'Hora_Entrada'}, inplace=True)

    def _calc_row(row):
        hora_entrada = row['Hora_Entrada'].hour + (row['Hora_Entrada'].minute / 60)
        hora_inicio_valida = max(7.5, hora_entrada) # 07:30
        
        horas_disponiveis = FIM_JORNADA_HORA - hora_inicio_valida
        if horas_disponiveis <= 0: return 0, 0
        
        minutos_uteis = (horas_disponiveis * 60) * 0.70 # 30% Ociosidade
        
        setor_str = str(row['Setor']).upper()
        tma_alvo = TMA_TARGET_SAC 
        if 'PEND' in setor_str or 'ÊNCIA' in setor_str:
            tma_alvo = TMA_TARGET_PEND
        
        meta = int(minutos_uteis / tma_alvo)
        return (meta, 0) if tma_alvo == TMA_TARGET_SAC else (0, meta)

    metas = df_presenca.apply(_calc_row, axis=1)
    df_presenca['Meta_SAC'] = [x[0] for x in metas]
    df_presenca['Meta_PEND'] = [x[1] for x in metas]

    return df_presenca
