# selecaoAtivos_report.py

import os
import re
import pandas as pd
from datetime import datetime

# Sheets -> DF (sem salvar) — a função pode retornar path OU DataFrame; tratamos ambos
from .selecaoAtivos.fetch_sheets import fetch_and_save_sheets

# Agrupamento por setor em MEMÓRIA (não salva CSVs)
from src.services.carteiras.selecaoAtivos.organize_sectors import organize_by_sector_from_df

# Builder do Excel final
from .selecaoAtivos.report_builder import export_deri_mevar

# Métricas por símbolo (preço atual, última sexta, VS, EMAs, alvo, VP)
from src.services.carteiras.selecaoAtivos.simple_analysis import compute_simple_analysis

# VR unificado (DERI/MEVAR -> VR)
from src.services.carteiras.metrics.vr_utils import calculate_vr

# Targets FMP (payload > FMP fallback)
from src.services.carteiras.fmp.targets import build_target_map

# Cálculo de DERI/MEVAR por setor
from .selecaoAtivos.compute_metrics import compute_group

# Quais abas (planilhas publicadas em CSV) compõem o consolidado
ABAS = {
    # "BLUSHIP": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQBQkGisTbFcAESZNa9CXtkQmyzKuxQK3zmF5mNrA4No5vEf7f2A9OZJh-W2tOdPUHXedUZr3qNDvgL/pub?gid=243135025&single=true&output=csv",
    # "INDUSTRIA": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQBQkGisTbFcAESZNa9CXtkQmyzKuxQK3zmF5mNrA4No5vEf7f2A9OZJh-W2tOdPUHXedUZr3qNDvgL/pub?gid=2059114322&single=true&output=csv",
    # "ENERGIA": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQBQkGisTbFcAESZNa9CXtkQmyzKuxQK3zmF5mNrA4No5vEf7f2A9OZJh-W2tOdPUHXedUZr3qNDvgL/pub?gid=1064838865&single=true&output=csv",
    # "UTILITIES": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQBQkGisTbFcAESZNa9CXtkQmyzKuxQK3zmF5mNrA4No5vEf7f2A9OZJh-W2tOdPUHXedUZr3qNDvgL/pub?gid=1388939024&single=true&output=csv",
    # "CONSUMER CYCLICALS": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQBQkGisTbFcAESZNa9CXtkQmyzKuxQK3zmF5mNrA4No5vEf7f2A9OZJh-W2tOdPUHXedUZr3qNDvgL/pub?gid=1392568327&single=true&output=csv",
    # "ACADEMIC E EDUCATIONAL SERVICES": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQBQkGisTbFcAESZNa9CXtkQmyzKuxQK3zmF5mNrA4No5vEf7f2A9OZJh-W2tOdPUHXedUZr3qNDvgL/pub?gid=832344307&single=true&output=csv",
    # "BASIC MATERIALS": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQBQkGisTbFcAESZNa9CXtkQmyzKuxQK3zmF5mNrA4No5vEf7f2A9OZJh-W2tOdPUHXedUZr3qNDvgL/pub?gid=91996730&single=true&output=csv",
    # "CONSUMER NON-CYCLICALS": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQBQkGisTbFcAESZNa9CXtkQmyzKuxQK3zmF5mNrA4No5vEf7f2A9OZJh-W2tOdPUHXedUZr3qNDvgL/pub?gid=791688509&single=true&output=csv",
    # "FINANCIALS": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQBQkGisTbFcAESZNa9CXtkQmyzKuxQK3zmF5mNrA4No5vEf7f2A9OZJh-W2tOdPUHXedUZr3qNDvgL/pub?gid=574429269&single=true&output=csv",
    # "HEALTHCARE": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQBQkGisTbFcAESZNa9CXtkQmyzKuxQK3zmF5mNrA4No5vEf7f2A9OZJh-W2tOdPUHXedUZr3qNDvgL/pub?gid=1088163130&single=true&output=csv",
    # "REAL ESTATE": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQBQkGisTbFcAESZNa9CXtkQmyzKuxQK3zmF5mNrA4No5vEf7f2A9OZJh-W2tOdPUHXedUZr3qNDvgL/pub?gid=376149182&single=true&output=csv",
    "TECHNOLOGY": "https://docs.google.com/spreadsheets/d/e/2PACX-1vQBQkGisTbFcAESZNa9CXtkQmyzKuxQK3zmF5mNrA4No5vEf7f2A9OZJh-W2tOdPUHXedUZr3qNDvgL/pub?gid=1558764950&single=true&output=csv",
}

# ===== Parâmetros =====
TOP_N = 5  # altere aqui para 25/100/etc.


# ===== Utilidades locais =====

_TICKER_RE = re.compile(r'\b([A-Z]{1,5}(?:\.[A-Z]{1,2})?)\b')  # ex: NVDA, MSFT, BRK.B

def _infer_ticker_from_row(row) -> str | None:
    """
    Examina todas as células da linha; procura um token estilo ticker:
      - 1 a 5 letras maiúsculas (opcional sufixo .XX)
    Retorna o primeiro que achar.
    """
    for col in row.index:
        val = row[col]
        if pd.isna(val):
            continue
        s = str(val).strip().upper()
        # ignora entradas óbvias que não são tickers
        if s in {"", "NAN", "NULL", "NONE"}:
            continue
        # tenta achar algo tipo NVDA, AAPL, BRK.B
        m = _TICKER_RE.search(s)
        if m:
            token = m.group(1)
            # filtro leve: evita capturar palavras de cor/tamanho, etc.
            if token not in {"TAMANHO", "SCORE", "COR", "ORDEM"} and not token.startswith("UNNAMED"):
                return token
    return None
def _ensure_dataframe(obj) -> pd.DataFrame:
    """Aceita path (str) ou DataFrame e devolve sempre um DataFrame."""
    if isinstance(obj, pd.DataFrame):
        return obj
    return pd.read_csv(obj)

def _pick_col(df: pd.DataFrame, prefer: list[str], substr_any: list[str]) -> str | None:
    low = {c.lower(): c for c in df.columns}
    for p in prefer:
        if p.lower() in low:
            return low[p.lower()]
    for c in df.columns:
        if any(s in c.lower() for s in substr_any):
            return c
    return None

def _normalize_scores_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Padroniza para Ticker/Score. Se não houver coluna de Ticker/Symbol,
    tenta inferir o ticker a partir das células (todas as colunas) por regex.
    """
    df = df.copy()

    # 1) Detecta (case-insensitive) colunas de Ticker/Score, se existirem
    def _pick_col(df: pd.DataFrame, prefer: list[str], substr_any: list[str]) -> str | None:
        low = {c.lower(): c for c in df.columns}
        for p in prefer:
            if p.lower() in low:
                return low[p.lower()]
        for c in df.columns:
            lc = c.lower()
            if any(s in lc for s in substr_any):
                return c
        return None

    col_tk = _pick_col(df, ["Ticker", "Symbol"], ["ticker", "symbol", "símbolo", "cod", "ativo"])
    col_sc = _pick_col(df, ["Score"], ["score", "pontu", "nota", "rank"])

    # 2) Renomeia se encontrou
    if col_tk and col_tk != "Ticker":
        df.rename(columns={col_tk: "Ticker"}, inplace=True)
    if col_sc and col_sc != "Score":
        df.rename(columns={col_sc: "Score"}, inplace=True)

    # 3) Se ainda não há "Ticker", inferir linha a linha
    if "Ticker" not in df.columns:
        df["Ticker"] = df.apply(_infer_ticker_from_row, axis=1)

    # 4) Limpeza
    df["Ticker"] = df["Ticker"].astype(str).str.strip().str.upper()
    df = df[~df["Ticker"].isin(["", "NAN", "NONE", "NULL"])]

    # 5) Score (opcional)
    if "Score" in df.columns:
        df["Score"] = pd.to_numeric(df["Score"], errors="coerce")

    # 6) Se nada foi inferido, agora sim falha com informação
    if df["Ticker"].isna().all() or len(df) == 0:
        raise ValueError(f"Não foi possível inferir tickers. Colunas originais: {list(df.columns)}")

    return df

# ===== Pipeline principal =====
def generate_selecaoAtivos_report(payload: dict | None = None):
    """
    Fluxo:
      1) Baixa as abas do Google Sheets e consolida em DF (memória)
      2) Organiza por setor (memória)
      3) Top N por setor (memória)
      4) DERI/MEVAR por setor
      5) Targets (payload > FMP)
      6) Análise simples + merge + VR
      7) Exporta Excel (somente abas de grupo)
    """
    pasta = "dados_selecaoAtivos"
    os.makedirs(pasta, exist_ok=True)

    try:
        # 1) Sheets -> DF consolidado (sem salvar CSV)
        sheets_res = fetch_and_save_sheets(ABAS, pasta, save=False)  # se sua função não aceita save=, remova o arg
        df_all = _ensure_dataframe(sheets_res)
        df_all = _normalize_scores_df(df_all)

        # 2) Organiza por setor em memória
        api_key = os.getenv("FMP_API_KEY")
        if not api_key:
            raise ValueError("FMP_API_KEY não encontrada no ambiente")

        # Se a função de setor reclamar de ausência de 'Ticker', já passamos padronizado
        setores_map = organize_by_sector_from_df(df_all, api_key)  # dict[str, DataFrame]

        if not setores_map:
            print("Nenhum setor retornado.")
            return None

        # 3) Top N por setor (sem salvar)
        topN_por_setor: dict[str, pd.DataFrame] = {}
        for setor, df_setor in setores_map.items():
            if df_setor is None or df_setor.empty:
                continue
            df_setor = _normalize_scores_df(df_setor)  # garante Ticker/Score
            if "Score" in df_setor.columns:
                df_sorted = df_setor.sort_values("Score", ascending=False)
            else:
                df_sorted = df_setor
            topN_por_setor[setor] = df_sorted.head(TOP_N).reset_index(drop=True)

        if not topN_por_setor:
            print("Nenhum setor com Top N disponível.")
            return None

        # 4) DERI/MEVAR por setor
        dfs_metrics: dict[str, pd.DataFrame] = {}
        for setor, df_top in topN_por_setor.items():
            if df_top is None or df_top.empty:
                continue
            tickers = df_top["Ticker"].dropna().astype(str).str.upper().tolist()

            scores_dict = {}
            if "Score" in df_top.columns:
                scores_dict = dict(zip(df_top["Ticker"], df_top["Score"]))

            df_metrics = compute_group(tickers, setor, scores_dict=scores_dict)
            if df_metrics is not None and not df_metrics.empty:
                dfs_metrics[setor] = df_metrics

        if not dfs_metrics:
            print("Nenhum setor processado com sucesso para DERI/MEVAR.")
            return None

        # 5) Targets — payload > FMP
        if payload and isinstance(payload.get("symbols_targets"), list) and payload["symbols_targets"]:
            target_map = build_target_map(payload["symbols_targets"], prefer_payload=True)
        else:
            all_syms = sorted({s for dfm in dfs_metrics.values() for s in dfm["symbol"].astype(str)})
            target_map = build_target_map([{"symbol": s} for s in all_syms], prefer_payload=True)

        # 6) Análise simples + merge + VR
        dfs_finais: dict[str, pd.DataFrame] = {}
        for setor, df_metrics in dfs_metrics.items():
            symbols_targets = [
                {"symbol": s, "target_price": target_map.get(str(s).upper())}
                for s in df_metrics["symbol"].tolist()
            ]

            # score opcional (se veio das planilhas)
            scores_dict = {}
            if "Score" in df_metrics.columns:
                scores_dict = dict(zip(df_metrics["symbol"], df_metrics["Score"]))

            df_simple = compute_simple_analysis(symbols_targets, scores_dict=scores_dict)
            base = df_metrics.merge(df_simple, on="symbol", how="left")
            base["VR"] = base.apply(lambda r: calculate_vr(r["DERI"], r["MEVAR"]), axis=1)
            base.insert(0, "grupo", setor)

            col_order = [
                "grupo", "symbol", "DERI", "MEVAR",
                "preco_indicado", "preco_atual", "VS",
                "ema10", "ema20",
                "preco_alvo", "VP", "VR", "score",
            ]
            for c in col_order:
                if c not in base.columns:
                    base[c] = None

            dfs_finais[setor] = base[col_order].copy()

        # 7) Exporta Excel final (sem fallback de CSV)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        outname = os.path.join(pasta, f"selecaoAtivos_report_{ts}.xlsx")
        export_deri_mevar(dfs_finais, outname, only_group_sheets=True)
        return outname

    except Exception as e:
        # log/raise “limpo” (o caller mostra 500)
        print(f"[ERRO] generate_selecaoAtivos_report: {e}")
        import traceback; traceback.print_exc()
        raise


# ===== (Opcional) relatório de análise completa =====
def generate_complete_analysis_report(payload: dict | None = None):
    """Gera um Excel apenas com a análise completa (quando você passa symbols_targets)."""
    from .selecaoAtivos.compute_metrics import compute_complete_analysis

    if not payload or not payload.get("symbols_targets"):
        raise ValueError("Payload deve conter 'symbols_targets'.")

    pasta = "dados_analise_completa"
    os.makedirs(pasta, exist_ok=True)

    # Scores do Sheets (em memória)
    sheets_res = fetch_and_save_sheets(ABAS, pasta, save=False)
    df_scores = _ensure_dataframe(sheets_res)
    df_scores = _normalize_scores_df(df_scores)

    scores_dict = {}
    if {"Ticker", "Score"}.issubset(df_scores.columns):
        tmp = df_scores.dropna(subset=["Ticker", "Score"]).copy()
        scores_dict = dict(zip(tmp["Ticker"], tmp["Score"]))

    df_res = compute_complete_analysis(
        symbols_targets=payload["symbols_targets"],
        group_name="Analise_Completa",
        scores_dict=scores_dict,
    )
    if df_res is None or df_res.empty:
        return None

    # Ordena e exporta
    cols = [
        "setor", "symbol", "DERI", "MEVAR", "preco_indicado",
        "preco_atual", "vs", "preco_alvo", "VP", "score",
        "ema10", "ema20", "VR",
    ]
    for c in cols:
        if c not in df_res.columns:
            df_res[c] = None

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    outname = os.path.join(pasta, f"analise_completa_{ts}.xlsx")
    df_res[cols].to_excel(outname, index=False, engine="openpyxl")
    return outname


if __name__ == "__main__":
    generate_selecaoAtivos_report()
