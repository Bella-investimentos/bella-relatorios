import os
import requests
import pandas as pd
from datetime import date, timedelta
from typing import List, Dict, Optional
from src.services.carteiras.make_report import (
    calculate_technical_indicators,
    _to_weekly,
    _weekly_df_to_bars
)

FMP_API_KEY = os.getenv("FMP_API_KEY")

def _last_friday_for_weekly_change(d: date) -> date:
    # regra: se hoje for sexta, usa a SEXTA ANTERIOR; senão, usa a sexta ≤ hoje
    if d.weekday() == 4:  # 4 = sexta
        d = d - timedelta(days=7)
    while d.weekday() != 4:
        d -= timedelta(days=1)
    return d
def compute_simple_analysis(
    symbols_targets: List[Dict[str, object]],
    scores_dict: Optional[Dict[str, float]] = None
) -> pd.DataFrame:
    """
    Retorna, por sÃ­mbolo:
      symbol, preco_atual, preco_indicado(Ãºlt. sexta), VS, ema10, ema20,
      preco_alvo (payload), VP, score, VR(None).
    """
    results = []

    for item in symbols_targets or []:
        symbol = str(item.get("symbol", "")).strip().upper()
        target_price = item.get("target_price")

        if not symbol:
            continue

        try:
            # ---- preÃ§o atual (quote) ----
            q = requests.get(
                f"https://financialmodelingprep.com/api/v3/quote/{symbol}",
                params={"apikey": FMP_API_KEY}, timeout=20
            ).json()
            preco_atual = float(q[0]["price"]) if isinstance(q, list) and q else None

            # ---- histÃ³rico diÃ¡rio (~1 ano) ----
            h = requests.get(
                f"https://financialmodelingprep.com/api/v3/historical-price-full/{symbol}",
                params={"apikey": FMP_API_KEY, "timeseries": 260}, timeout=20
            ).json()
            hist = h.get("historical", []) if isinstance(h, dict) else []
            df_daily = pd.DataFrame(hist)
            if not df_daily.empty:
                df_daily["date"] = pd.to_datetime(df_daily["date"])
                df_daily = df_daily.sort_values("date")
            else:
                df_daily = pd.DataFrame(columns=["date", "close"])

            # ---- preÃ§o indicado = close da Ãºltima sexta ----
            preco_indicado = None
            vs = None
            if not df_daily.empty:
                lf = _last_friday_for_weekly_change(date.today())
                last_friday = pd.Timestamp(lf)
                ref = df_daily.loc[df_daily["date"] <= last_friday, "close"]
                if not ref.empty:
                    preco_indicado = float(ref.iloc[-1])
                    if preco_atual and preco_indicado > 0:
                        vs = (preco_atual / preco_indicado - 1.0) * 100.0

            # ---- EMAs semanais (reaproveitando funÃ§Ãµes do make_report) ----
            weekly = _to_weekly(df_daily)            # aceita df com 'date' e 'close'
            bars = _weekly_df_to_bars(weekly)        # converte pra lista de bars
            ema10, ema20, _, _ = calculate_technical_indicators(bars)

            # ---- VP (% atÃ© o alvo) ----
            vp = None
            if target_price is not None and preco_atual and preco_atual > 0:
                vp = (float(target_price) / float(preco_atual) - 1.0) * 100.0

            results.append({
                "symbol": symbol,
                "preco_atual": round(preco_atual, 2) if preco_atual is not None else None,
                "preco_indicado": round(preco_indicado, 2) if preco_indicado is not None else None,
                "VS": round(vs, 2) if vs is not None else None,
                "ema10": round(ema10, 2) if ema10 is not None else None,
                "ema20": round(ema20, 2) if ema20 is not None else None,
                "preco_alvo": target_price,
                "VP": round(vp, 2) if vp is not None else None,
                "score": (scores_dict or {}).get(symbol),
                "VR": None
            })

        except Exception as e:
            print(f"âš ï¸ compute_simple_analysis({symbol}) erro: {e}")
            results.append({
                "symbol": symbol,
                "preco_atual": None,
                "preco_indicado": None,
                "VS": None,
                "ema10": None,
                "ema20": None,
                "preco_alvo": target_price,
                "VP": None,
                "score": (scores_dict or {}).get(symbol),
                "VR": None
            })

    return pd.DataFrame(results)