import pandas as pd
import os

def filter_top50(pasta: str, setores_map: dict):
    """
    Filtra os top 25 tickers por setor.
    
    Args:
        pasta: Diretório onde estão os arquivos CSV
        setores_map: Dicionário {nome_setor: nome_arquivo_csv}
    
    Returns:
        dict: {nome_setor: DataFrame} com os top 25 de cada setor
    """
    top50_por_setor = {}

    for setor, arquivo in setores_map.items():
        try:
            caminho_arquivo = os.path.join(pasta, arquivo)
            
            # Verifica se o arquivo existe
            if not os.path.exists(caminho_arquivo):
                print(f"⚠️ Arquivo não encontrado: {caminho_arquivo}")
                continue
            
            print(f"🔄 Processando setor: {setor} (arquivo: {arquivo})")
            
            # Lê o arquivo CSV
            df = pd.read_csv(caminho_arquivo)
            
            if df.empty:
                print(f"⚠️ {setor}: DataFrame vazio em {arquivo}")
                continue
            
            print(f"📊 {setor}: {len(df)} linhas, colunas: {list(df.columns)}")
            
            # Verifica se tem as colunas necessárias
            colunas_disponiveis = df.columns.tolist()
            
            # Tenta identificar as colunas de Ticker e Score
            ticker_col = None
            score_col = None
            
            # Possíveis nomes para a coluna de ticker
            ticker_names = ['Ticker', 'ticker', 'Symbol', 'symbol', 'TICKER', 'SYMBOL']
            for col_name in ticker_names:
                if col_name in colunas_disponiveis:
                    ticker_col = col_name
                    break
            
            # Possíveis nomes para a coluna de score
            score_names = ['Score', 'score', 'SCORE', 'Value', 'value', 'Rating', 'rating']
            for col_name in score_names:
                if col_name in colunas_disponiveis:
                    score_col = col_name
                    break
            
            # Se não encontrou as colunas pelos nomes, usa as duas primeiras
            if not ticker_col and len(colunas_disponiveis) >= 1:
                ticker_col = colunas_disponiveis[0]
                print(f"🔄 {setor}: Usando '{ticker_col}' como coluna de Ticker")
            
            if not score_col and len(colunas_disponiveis) >= 2:
                score_col = colunas_disponiveis[1]
                print(f"🔄 {setor}: Usando '{score_col}' como coluna de Score")
            
            # Verifica se conseguiu identificar as colunas
            if not ticker_col:
                print(f"❌ {setor}: Não foi possível identificar coluna de Ticker em {arquivo}")
                continue
                
            if not score_col:
                print(f"❌ {setor}: Não foi possível identificar coluna de Score em {arquivo}")
                continue
            
            # Cria DataFrame padronizado
            df_padronizado = df[[ticker_col, score_col]].copy()
            df_padronizado.columns = ['Ticker', 'Score']
            
            # Remove linhas com valores vazios
            df_padronizado = df_padronizado.dropna()
            
            # Remove linhas com ticker vazio
            df_padronizado = df_padronizado[df_padronizado['Ticker'].astype(str).str.strip() != '']
            
            if df_padronizado.empty:
                print(f"⚠️ {setor}: Nenhuma linha válida após limpeza")
                continue
            
            # Converte Score para numérico se necessário
            if df_padronizado['Score'].dtype == 'object':
                # Limpa e converte Score
                df_padronizado['Score'] = (
                    df_padronizado['Score']
                    .astype(str)
                    .str.replace(',', '.')
                    .str.replace(r'[^\d.-]', '', regex=True)
                )
                df_padronizado['Score'] = pd.to_numeric(df_padronizado['Score'], errors='coerce')
                df_padronizado = df_padronizado.dropna(subset=['Score'])
            
            if df_padronizado.empty:
                print(f"⚠️ {setor}: Nenhuma linha válida após conversão de Score")
                continue
            
            # Remove duplicatas pelo Ticker
            tamanho_antes = len(df_padronizado)
            df_padronizado = df_padronizado.drop_duplicates(subset='Ticker', keep='first')
            duplicatas = tamanho_antes - len(df_padronizado)
            
            if duplicatas > 0:
                print(f"🔄 {setor}: Removidas {duplicatas} duplicatas")
            
            # Seleciona os 25 melhores (assumindo que Score maior é melhor)
            df_top50 = df_padronizado.sort_values(by='Score', ascending=False).head(5)
            
            if df_top50.empty:
                print(f"⚠️ {setor}: Top 50 resultou em DataFrame vazio")
                continue
            
            # ✅ NOVO: cria dicionário ticker -> score para uso posterior
            scores_dict = dict(zip(df_top50['Ticker'], df_top50['Score']))
            df_top50.attrs['scores_dict'] = scores_dict  # Anexa ao DataFrame
            
            top50_por_setor[setor] = df_top50
            
            # Salvar em arquivo novo
            caminho_top50 = os.path.join(pasta, f"tickers_{setor.lower().replace(' ', '_')}_top50.csv")
            df_top50.to_csv(caminho_top50, index=False, encoding='utf-8')
            
            print(f"✅ {setor}: Top 25 tickers salvos ({len(df_top50)} linhas) em {caminho_top50}")
            
            # Mostra alguns exemplos
            if len(df_top50) > 0:
                print(f"   📈 Exemplo - Melhor: {df_top50.iloc[0]['Ticker']} (Score: {df_top50.iloc[0]['Score']:.2f})")
                if len(df_top50) > 1:
                    print(f"   📈 Exemplo - Último: {df_top50.iloc[-1]['Ticker']} (Score: {df_top50.iloc[-1]['Score']:.2f})")
            
        except Exception as e:
            print(f"❌ Erro ao processar setor {setor} (arquivo: {arquivo}): {e}")
            import traceback
            traceback.print_exc()
            continue

    print(f"\n📊 RESUMO: Processados {len(top50_por_setor)} setores com sucesso")
    for setor, df in top50_por_setor.items():
        print(f"  - {setor}: {len(df)} tickers")
    
    return top50_por_setor