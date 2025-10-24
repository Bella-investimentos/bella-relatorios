# src/services/carteiras/metrics/vr_utils.py
from __future__ import annotations

import os, math, time
from typing import List, Optional, Dict
import numpy as np
import pandas as pd
import requests

FMP_API = os.getenv("FMP_API_KEY")
FMP_V3 = "https://financialmodelingprep.com/api/v3"
FMP_STABLE = "https://financialmodelingprep.com/stable"

# -------------------- HTTP util --------------------
def _get(url: str, params: Optional[Dict] = None, tries: int = 3, backoff: float = 1.5):
    params = dict(params or {})
    if FMP_API:
        params["apikey"] = FMP_API
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, params=params, timeout=20)
            if r.status_code == 200:
                return r.json()
            last = RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
        except Exception as e:
            last = e
        time.sleep(backoff ** (i + 1))
    raise last

# -------------------- Data fetch --------------------
def fetch_prices(symbol: str, start: str, end: str) -> pd.DataFrame:
    """Baixa preços históricos (close/adjClose) do símbolo [start, end]."""
    js = _get(f"{FMP_V3}/historical-price-full/{symbol}", {"from": start, "to": end})
    hist = js.get("historical") if isinstance(js, dict) else js
    df = pd.DataFrame(hist or [])
    if df.empty:
        return pd.DataFrame(columns=["date","close","adjClose","volume"])
    keep = [c for c in df.columns if c in {"date","close","adjClose","unadjustedClose","volume"}]
    df = df[keep].copy()
    if "adjClose" not in df.columns and "unadjustedClose" in df.columns:
        df.rename(columns={"unadjustedClose": "close"}, inplace=True)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)

def fetch_splits(symbol: str, start: str, end: str) -> pd.DataFrame:
    """Baixa splits (numerator/denominator) e calcula ratio_float."""
    try:
        js = _get(f"{FMP_STABLE}/splits", {"symbol": symbol, "from": start, "to": end})
        if isinstance(js, list) and js:
            df = pd.DataFrame(js)
            df["date"] = pd.to_datetime(df["date"])
            df["numerator"] = pd.to_numeric(df.get("numerator"), errors="coerce")
            df["denominator"] = pd.to_numeric(df.get("denominator"), errors="coerce")
            df["ratio_float"] = df["numerator"] / df["denominator"]
            return df.sort_values("date").reset_index(drop=True)
    except Exception:
        pass
    return pd.DataFrame(columns=["date","numerator","denominator","ratio_float"])

# -------------------- Adjust & returns --------------------
def backadjust_adjclose(df_price: pd.DataFrame, df_splits: pd.DataFrame) -> pd.Series:
    """Usa adjClose quando disponível; senão reconstrói com splits retroativos."""
    if "adjClose" in df_price.columns and df_price["adjClose"].notna().any():
        return df_price["adjClose"].astype(float)
    if df_price.empty:
        return pd.Series(dtype=float)
    adj = df_price["close"].astype(float).copy()
    if not df_splits.empty:
        for _, row in df_splits.dropna(subset=["ratio_float"]).iterrows():
            ratio = float(row["ratio_float"])
            if ratio <= 0 or np.isnan(ratio):
                continue
            d = row["date"]
            adj.loc[df_price["date"] < d] *= (1.0 / ratio)
    return adj

def build_returns(df_price: pd.DataFrame, adj: pd.Series, split_dates: List[pd.Timestamp]) -> pd.DataFrame:
    """Retornos log; zera dias de split e outliers extremos."""
    df = df_price[["date"]].copy()
    df["adj"] = adj.values
    df["r"] = np.log(df["adj"]).diff()
    split_set = set(pd.to_datetime(split_dates).date)
    df.loc[df["date"].dt.date.isin(split_set), "r"] = np.nan
    df.loc[df["r"].abs() > 0.40, "r"] = np.nan
    return df.dropna(subset=["r"]).reset_index(drop=True)

# -------------------- Metrics --------------------
def annualized_vol(r: pd.Series) -> float:
    return float(r.std(ddof=1) * np.sqrt(252)) if len(r) > 1 else float("nan")

def annualized_mean_abs(r: pd.Series) -> float:
    return float(r.abs().mean() * np.sqrt(252)) if len(r) > 0 else float("nan")

def compute_deri(r_asset: pd.Series, r_bench: pd.Series) -> float:
    return annualized_vol(r_asset) / annualized_vol(r_bench)

def compute_mevar(r_asset: pd.Series, r_bench: pd.Series) -> float:
    return annualized_mean_abs(r_asset) / annualized_mean_abs(r_bench)

def calculate_vr(deri: float, mevar: float) -> float:
    """
    Fórmula VR (mesma do Excel):
    =((2.5*(100/(1+EXP(-(LN(1.5)/0.35)*(DERI-1.15)))))+(2*(100/(1+EXP(-(LN(1.5)/0.25)*(MEVAR-0.75))))))/4.5
    """
    if pd.isna(deri) or pd.isna(mevar):
        return float("nan")
    try:
        ln_1_5 = math.log(1.5)
        deri_part  = 2.5 * (100 / (1 + math.exp(-(ln_1_5/0.35) * (deri  - 1.15))))
        mevar_part = 2.0 * (100 / (1 + math.exp(-(ln_1_5/0.25) * (mevar - 0.75))))
        vr = (deri_part + mevar_part) / 4.5
        return round(vr, 2)
    except (ValueError, ZeroDivisionError):
        return float("nan")

# -------------------- High-level helper --------------------
def pick_benchmark(group: str) -> str:
    g = (group or "").lower()
    if g == "reits":
        return "VNQ"
    return "SPY"

def compute_vr_for_symbol(symbol: str, benchmark: Optional[str] = None,
                          years: int = 5, min_obs: int = 150) -> Dict[str, float]:
    """
    Calcula DERI/MEVAR/VR para um único símbolo vs benchmark (default SPY).
    Retorna: {"symbol","benchmark","DERI","MEVAR","VR"}
    """
    from datetime import date, timedelta
    today = date.today()
    start = (today - timedelta(days=int(365.25 * years))).isoformat()
    end   = today.isoformat()

    bench = benchmark or pick_benchmark("default")

    # Benchmark
    p_b = fetch_prices(bench, start, end)
    s_b = fetch_splits(bench, "1900-01-01", end)
    adj_b = backadjust_adjclose(p_b, s_b)
    df_b = build_returns(p_b, adj_b, s_b["date"].tolist())

    # Ativo
    p = fetch_prices(symbol, start, end)
    if p.empty or (p["date"].min() > pd.to_datetime(start) + pd.Timedelta(days=60)):
        p = fetch_prices(symbol, "1900-01-01", end)
    s = fetch_splits(symbol, "1900-01-01", end)
    adj = backadjust_adjclose(p, s)
    df_a = build_returns(p, adj, s["date"].tolist())

    df_m = (
        pd.merge(
            df_a[["date","adj","r"]].rename(columns={"adj":"adj_a","r":"r_a"}),
            df_b[["date","r"]].rename(columns={"r":"r_b"}),
            on="date", how="inner"
        ).dropna().sort_values("date")
    )

    if len(df_m) < min_obs:
        return {"symbol": symbol.upper(), "benchmark": bench, "DERI": np.nan, "MEVAR": np.nan, "VR": np.nan}

    deri  = compute_deri(df_m["r_a"], df_m["r_b"])
    mevar = compute_mevar(df_m["r_a"], df_m["r_b"])
    vr    = calculate_vr(deri, mevar)
    return {"symbol": symbol.upper(), "benchmark": bench, "DERI": round(deri, 4), "MEVAR": round(mevar, 4), "VR": vr}
