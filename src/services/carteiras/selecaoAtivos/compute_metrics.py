# import os, time, datetime as dt
# from typing import List, Optional, Dict
# import numpy as np
# import pandas as pd
# import requests

# # Helpers de EMA/semana vindos do make_report
# from src.services.carteiras.make_report import (
#     fetch_equity, _to_weekly, _weekly_df_to_bars, calculate_technical_indicators
# )

# # <<< NOVO: importe o núcleo de VR do módulo isolado >>>
# from src.services.carteiras.metrics.vr_utils import (
#     fetch_prices, fetch_splits, backadjust_adjclose, build_returns,
#     compute_deri, compute_mevar, calculate_vr,  # métricas
#     # opcional: compute_vr_for_symbol,
# )

# API = os.getenv("FMP_API_KEY")
# if not API:
#     raise ValueError("Defina FMP_API_KEY no seu .env")

# FMP_V3 = "https://financialmodelingprep.com/api/v3"
# FMP_STABLE = "https://financialmodelingprep.com/stable"


# # ========== HELPERS ==========

# def dedupe_preserving_order(seq: List[str]) -> List[str]:
#     seen, out = set(), []
#     for x in seq:
#         if x not in seen:
#             seen.add(x)
#             out.append(x)
#     return out


# def _get(url, params=None, tries=3, backoff=1.5):
#     """
#     Pequena wrapper GET com backoff. (Mantida para funções locais que ainda usam)
#     """
#     params = dict(params or {})
#     params["apikey"] = API
#     last = None
#     for i in range(tries):
#         try:
#             r = requests.get(url, params=params, timeout=20)
#             if r.status_code == 200:
#                 return r.json()
#             last = RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
#         except Exception as e:
#             last = e
#         time.sleep(backoff ** (i + 1))
#     raise last


# def get_friday_price_and_current(symbol: str) -> tuple:
#     """
#     Retorna (preco_atual, preco_ultima_sexta, vs_pct)
#     VS semanal = variação em % do preço ATUAL (spot) vs o fechamento da ÚLTIMA SEXTA-FEIRA.
#     """
#     try:
#         # Preço atual via quote
#         quote_response = requests.get(f"{FMP_V3}/quote/{symbol}?apikey={API}", timeout=20)
#         quote_data = quote_response.json()
#         preco_atual = float(quote_data[0]["price"]) if quote_data else None

#         # Histórico (últimos ~60 dias) para achar a última sexta
#         hist_response = requests.get(
#             f"{FMP_V3}/historical-price-full/{symbol}?apikey={API}&timeseries=60",
#             timeout=20
#         )
#         hist_data = hist_response.json()
#         historical = hist_data.get("historical", []) if isinstance(hist_data, dict) else []

#         preco_indicado = None
#         vs_pct = None

#         if historical:
#             df_daily = pd.DataFrame(historical)
#             df_daily["date"] = pd.to_datetime(df_daily["date"])
#             df_daily = df_daily.sort_values("date")

#             # âncora: “sexta anterior” se hoje for sexta; senão, a sexta ≤ hoje
#             today = pd.Timestamp.today().normalize()
#             lf = today - pd.offsets.Week(weekday=4)
#             if today.weekday() == 4:  # se hoje é sexta, volte uma semana
#                 lf = lf - pd.Timedelta(weeks=1)

#             # garanta dtype datetime
#             if not pd.api.types.is_datetime64_any_dtype(df_daily["date"]):
#                 df_daily["date"] = pd.to_datetime(df_daily["date"])

#             # busque regressivamente até 7 dias por um candle ≤ sexta-âncora
#             preco_indicado = None
#             for delta in range(0, 8):
#                 probe = lf - pd.Timedelta(days=delta)
#                 ref = df_daily.loc[df_daily["date"] <= probe, "close"]
#                 if not ref.empty:
#                     preco_indicado = float(ref.iloc[-1])
#                     break
#             # se ainda não achou, deixe como None (não force para o último close geral)


#             if not ref.empty:
#                 preco_indicado = float(ref.iloc[-1])
#                 if preco_atual is not None and preco_indicado > 0:
#                     vs_pct = (preco_atual / preco_indicado - 1.0) * 100.0

#         return preco_atual, preco_indicado, vs_pct

#     except Exception as e:
#         print(f"Erro ao buscar preços para {symbol}: {e}")
#         return None, None, None


# def get_emas_for_symbol(symbol: str) -> tuple:
#     """
#     Retorna (ema10, ema20) semanais para o símbolo.
#     """
#     try:
#         # Histórico mais longo para EMAs semanais (~260 pregões ~ 5 anos)
#         hist_response = requests.get(
#             f"{FMP_V3}/historical-price-full/{symbol}?apikey={API}&timeseries=260",
#             timeout=20
#         )
#         hist_data = hist_response.json()
#         historical = hist_data.get("historical", []) if isinstance(hist_data, dict) else []

#         if not historical:
#             return None, None

#         df_daily = pd.DataFrame(historical)
#         df_daily["date"] = pd.to_datetime(df_daily["date"])
#         df_daily = df_daily.sort_values("date")

#         # Semanal + indicadores
#         weekly_df = _to_weekly(df_daily)  # resample('W-FRI').last() (na sua helper)
#         bars = _weekly_df_to_bars(weekly_df)

#         if len(bars) >= 20:  # mínimo para EMA20 "real"
#             ema10, ema20, _, _ = calculate_technical_indicators(bars)
#             return ema10, ema20

#         return None, None

#     except Exception as e:
#         print(f"Erro ao calcular EMAs para {symbol}: {e}")
#         return None, None


# # ========== MÉTRICAS (VR) ==========

# def annualized_vol(r: pd.Series) -> float:
#     return float(r.std(ddof=1) * np.sqrt(252)) if len(r) > 1 else float("nan")


# def annualized_mean_abs(r: pd.Series) -> float:
#     return float(r.abs().mean() * np.sqrt(252)) if len(r) > 0 else float("nan")


# def compute_group(
#     tickers: List[str],
#     group_name: str,
#     start_years: int = 5,
#     min_obs: int = 150,
#     benchmark: Optional[str] = None,
#     scores_dict: Optional[dict] = None,
# ) -> pd.DataFrame:
#     """
#     Calcula métricas (DERI, MEVAR), classes e VR para um grupo de tickers.
#     NÃO busca preço atual, EMA, VS ou target. Somente métricas (históricas).
#     """
#     # normaliza lista de tickers
#     tickers = dedupe_preserving_order(tickers)
#     tickers = [t.strip().upper() for t in tickers if t and str(t).lower() != "nan"]
#     if not tickers:
#         return pd.DataFrame(columns=["symbol", "DERI", "MEVAR", "VR", "Classe DERI", "Classe MEVAR", "Score"])

#     today = dt.date.today()
#     start = (today - dt.timedelta(days=int(365.25 * start_years))).isoformat()
#     end = today.isoformat()

#     # benchmark
#     def _pick_benchmark(g: str) -> str:
#         g = (g or "").lower()
#         return "VNQ" if g == "reits" else "SPY"

#     bench = benchmark or _pick_benchmark(group_name)

#     # benchmark: preços, splits, retornos
#     p_b = fetch_prices(bench, start, end)
#     s_b = fetch_splits(bench, "1900-01-01", end)
#     adj_b = backadjust_adjclose(p_b, s_b)
#     df_b = build_returns(p_b, adj_b, s_b["date"].tolist())

#     out_rows = []
#     for sym in tickers:
#         try:
#             print(f"▶️ [{group_name}] Processando {sym}")

#             # preços do ativo (para gerar retornos)
#             p = fetch_prices(sym, start, end)
#             if p.empty or (p["date"].min() > pd.to_datetime(start) + pd.Timedelta(days=60)):
#                 p = fetch_prices(sym, "1900-01-01", end)

#             s = fetch_splits(sym, "1900-01-01", end)
#             adj = backadjust_adjclose(p, s)
#             df_a = build_returns(p, adj, s["date"].tolist())

#             # merge com benchmark para alinhar retornos (mesmas datas)
#             df_m = (
#                 pd.merge(
#                     df_a[["date", "adj", "r"]].rename(columns={"adj": "adj_a", "r": "r_a"}),
#                     df_b[["date", "r"]].rename(columns={"r": "r_b"}),
#                     on="date", how="inner",
#                 )
#                 .dropna()
#                 .sort_values("date")
#             )

#             score_val = scores_dict.get(sym) if scores_dict else None

#             if len(df_m) >= min_obs:
#                 deri = compute_deri(df_m["r_a"], df_m["r_b"])
#                 mevar = compute_mevar(df_m["r_a"], df_m["r_b"])
#                 vr = calculate_vr(deri, mevar)

#                 def _classify(val: float, metric: str) -> str:
#                     if np.isnan(val): return "—"
#                     if metric == "DERI":
#                         return "Agressivo" if val > 1.5 else ("Moderado" if val >= 0.8 else "Conservador")
#                     if metric == "MEVAR":
#                         return "Agressivo" if val > 1.0 else ("Moderado" if val >= 0.5 else "Conservador")
#                     return "—"

#                 out_rows.append(
#                     {
#                         "symbol": sym,
#                         "DERI": round(deri, 4),
#                         "MEVAR": round(mevar, 4),
#                         "VR": vr,
#                         "Classe DERI": _classify(deri, "DERI"),
#                         "Classe MEVAR": _classify(mevar, "MEVAR"),
#                         "Score": score_val,
#                     }
#                 )
#             else:
#                 out_rows.append(
#                     {
#                         "symbol": sym,
#                         "DERI": np.nan,
#                         "MEVAR": np.nan,
#                         "VR": np.nan,
#                         "Classe DERI": "—",
#                         "Classe MEVAR": "—",
#                         "Score": score_val,
#                     }
#                 )

#         except Exception as e:
#             print(f"⚠️ Erro ao processar {sym}: {e}")
#             out_rows.append(
#                 {
#                     "symbol": sym,
#                     "DERI": np.nan,
#                     "MEVAR": np.nan,
#                     "VR": np.nan,
#                     "Classe DERI": "erro",
#                     "Classe MEVAR": "erro",
#                     "Score": (scores_dict.get(sym) if scores_dict else None),
#                 }
#             )

#     df = pd.DataFrame(out_rows)
#     df.attrs["benchmark"] = bench
#     df.attrs["group"] = group_name
#     return df


# def compute_complete_analysis(
#     symbols_targets: List[Dict],
#     group_name: str = "Analise_Completa",
#     scores_dict: Optional[dict] = None
# ) -> pd.DataFrame:
#     results = []

#     # Extrair símbolos
#     symbols = [item.get("symbol", "").strip().upper() for item in symbols_targets if item.get("symbol")]
#     print(f"🗂️ scores_dict recebido: {scores_dict}")
#     print(f"🗂️ Exemplo de entrada: {symbols_targets[0] if symbols_targets else 'Nenhum'}")

#     # Calcular métricas (incluindo VR e Score)
#     df_metrics = compute_group(symbols, group_name, scores_dict=scores_dict)
#     print(f"🗂️ df_metrics colunas: {df_metrics.columns.tolist()}")
#     print(f"🗂️ VR válidos: {df_metrics['VR'].notna().sum()}")
#     print(f"🗂️ Score válidos: {df_metrics['Score'].notna().sum()}")

#     # Lookup das métricas por símbolo
#     metrics_lookup = {row["symbol"]: row.to_dict() for _, row in df_metrics.iterrows()}

#     # Processar cada símbolo
#     for item in symbols_targets:
#         symbol = item.get("symbol", "").strip().upper()
#         target_price = item.get("target_price")

#         if not symbol:
#             continue

#         try:
#             # Métricas já calculadas
#             metrics = metrics_lookup.get(symbol, {})

#             # Preços: atual, última sexta e VS (%)
#             preco_atual, preco_indicado, vs_pct = get_friday_price_and_current(symbol)

#             # EMAs semanais
#             ema10, ema20 = get_emas_for_symbol(symbol)

#             # VP (distância até o alvo) em %
#             vp_pct = None
#             if target_price and preco_atual and preco_atual > 0:
#                 vp_pct = (float(target_price) / float(preco_atual) - 1.0) * 100.0

#             results.append({
#                 "setor": group_name,
#                 "symbol": symbol,
#                 "DERI": metrics.get("DERI"),
#                 "MEVAR": metrics.get("MEVAR"),
#                 "preco_indicado": round(preco_indicado, 2) if preco_indicado else None,
#                 "preco_atual": round(preco_atual, 2) if preco_atual else None,
#                 "vs": round(vs_pct, 2) if vs_pct is not None else None,  # VS semanal (%)
#                 "preco_alvo": target_price,
#                 "VP": round(vp_pct, 2) if vp_pct is not None else None,
#                 "score": metrics.get("Score"),  # do metrics lookup
#                 "ema10": round(ema10, 2) if ema10 else None,
#                 "ema20": round(ema20, 2) if ema20 else None,
#                 "VR": metrics.get("VR"),       # do metrics lookup
#             })

#         except Exception as e:
#             print(f"⚠️ Erro ao processar {symbol}: {e}")
#             results.append({
#                 "setor": group_name, "symbol": symbol,
#                 "DERI": None, "MEVAR": None, "preco_indicado": None,
#                 "preco_atual": None, "vs": None, "preco_alvo": target_price,
#                 "VP": None, "score": None, "ema10": None, "ema20": None, "VR": None
#             })

#     return pd.DataFrame(results)

"""
Versão otimizada com paralelização e cache
"""
import os
from typing import List, Dict, Optional
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
import requests

from src.services.carteiras.metrics.vr_utils import (
    fetch_prices, fetch_splits, backadjust_adjclose, 
    build_returns, compute_deri, compute_mevar, calculate_vr
)

API = os.getenv("FMP_API_KEY")
FMP_V3 = "https://financialmodelingprep.com/api/v3"

# Cache de 1 hora para preços históricos
@lru_cache(maxsize=200)
def _cached_fetch_prices(symbol: str, start: str, end: str):
    """Cache de preços para evitar requisições repetidas"""
    return fetch_prices(symbol, start, end)

@lru_cache(maxsize=200)
def _cached_fetch_splits(symbol: str, start: str, end: str):
    return fetch_splits(symbol, start, end)


def process_single_symbol(
    symbol: str,
    start: str,
    end: str,
    bench_returns: pd.DataFrame,
    min_obs: int,
    score: Optional[float] = None
) -> Dict:
    """
    Processa UM símbolo isoladamente (paralelizável)
    Retorna dict com métricas ou erro
    """
    try:
        # Usa cache
        p = _cached_fetch_prices(symbol, start, end)
        if p.empty:
            p = _cached_fetch_prices(symbol, "1900-01-01", end)
        
        s = _cached_fetch_splits(symbol, "1900-01-01", end)
        adj = backadjust_adjclose(p, s)
        df_a = build_returns(p, adj, s["date"].tolist())
        
        # Merge com benchmark
        df_m = pd.merge(
            df_a[["date", "r"]].rename(columns={"r": "r_a"}),
            bench_returns[["date", "r"]].rename(columns={"r": "r_b"}),
            on="date", how="inner"
        ).dropna().sort_values("date")
        
        if len(df_m) < min_obs:
            return {
                "symbol": symbol, "DERI": np.nan, "MEVAR": np.nan,
                "VR": np.nan, "Classe DERI": "—", "Classe MEVAR": "—",
                "Score": score, "error": f"Dados insuficientes ({len(df_m)})"
            }
        
        deri = compute_deri(df_m["r_a"], df_m["r_b"])
        mevar = compute_mevar(df_m["r_a"], df_m["r_b"])
        vr = calculate_vr(deri, mevar)
        
        def classify(val: float, metric: str) -> str:
            if np.isnan(val): return "—"
            if metric == "DERI":
                return "Agressivo" if val > 1.5 else ("Moderado" if val >= 0.8 else "Conservador")
            return "Agressivo" if val > 1.0 else ("Moderado" if val >= 0.5 else "Conservador")
        
        return {
            "symbol": symbol,
            "DERI": round(deri, 4),
            "MEVAR": round(mevar, 4),
            "VR": vr,
            "Classe DERI": classify(deri, "DERI"),
            "Classe MEVAR": classify(mevar, "MEVAR"),
            "Score": score
        }
        
    except Exception as e:
        return {
            "symbol": symbol, "DERI": np.nan, "MEVAR": np.nan,
            "VR": np.nan, "Classe DERI": "erro", "Classe MEVAR": "erro",
            "Score": score, "error": str(e)
        }


def compute_group_parallel(
    tickers: List[str],
    group_name: str,
    start_years: int = 5,
    min_obs: int = 150,
    benchmark: Optional[str] = None,
    scores_dict: Optional[Dict] = None,
    max_workers: int = 8
) -> pd.DataFrame:
    """
    PARALELIZADO: processa múltiplos tickers simultaneamente
    """
    import datetime as dt
    
    # Remove duplicatas
    tickers = list(dict.fromkeys([t.strip().upper() for t in tickers if t]))
    
    today = dt.date.today()
    start = (today - dt.timedelta(days=int(365.25 * start_years))).isoformat()
    end = today.isoformat()
    
    # Benchmark
    bench = benchmark or ("VNQ" if group_name.lower() == "reits" else "SPY")
    p_b = _cached_fetch_prices(bench, start, end)
    s_b = _cached_fetch_splits(bench, "1900-01-01", end)
    adj_b = backadjust_adjclose(p_b, s_b)
    bench_returns = build_returns(p_b, adj_b, s_b["date"].tolist())
    
    # Paralelização
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                process_single_symbol,
                sym, start, end, bench_returns, min_obs,
                scores_dict.get(sym) if scores_dict else None
            ): sym for sym in tickers
        }
        
        for future in as_completed(futures):
            sym = futures[future]
            try:
                result = future.result(timeout=30)
                results.append(result)
                print(f"✓ {sym}: DERI={result.get('DERI', 'N/A')}")
            except Exception as e:
                print(f"✗ {sym}: {e}")
                results.append({
                    "symbol": sym, "DERI": np.nan, "MEVAR": np.nan,
                    "VR": np.nan, "Classe DERI": "timeout", "Classe MEVAR": "timeout",
                    "Score": scores_dict.get(sym) if scores_dict else None
                })
    
    df = pd.DataFrame(results)
    df.attrs["benchmark"] = bench
    df.attrs["group"] = group_name
    return df


# Compatibilidade: mantém função original como wrapper
def compute_group(*args, **kwargs):
    """Wrapper para manter compatibilidade"""
    return compute_group_parallel(*args, **kwargs)