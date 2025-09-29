# organize_sectors_memory.py

from __future__ import annotations
import re
import requests
import pandas as pd
from typing import Dict, Iterable, Tuple, List
from collections import defaultdict

# ---------- Helpers de rede ----------

def _get_profiles_batch(tickers: Iterable[str], api_key: str, timeout: int = 20) -> Dict[str, Tuple[str, str]]:
    """
    Chama a FMP para até 50 tickers por vez e retorna
    { 'AAPL': ('Technology','Consumer Electronics'), ... }.
    """
    tickers = [t for t in tickers if t]  # defensivo
    if not tickers:
        return {}

    url = f"https://financialmodelingprep.com/api/v3/profile/{','.join(tickers)}"
    params = {"apikey": api_key}
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    data = r.json()

    out: Dict[str, Tuple[str, str]] = {}
    for item in data if isinstance(data, list) else []:
        sym = (item.get("symbol") or "").strip().upper()
        sec = item.get("sector") or "Unknown"
        ind = item.get("industry") or "Unknown"
        if sym:
            out[sym] = (sec, ind)
    return out


def fetch_profiles(tickers: List[str], api_key: str, chunk_size: int = 50) -> Dict[str, Tuple[str, str]]:
    """
    Faz batching de até `chunk_size` tickers por requisição e
    consolida um dicionário {symbol: (sector, industry)}.
    """
    profiles: Dict[str, Tuple[str, str]] = {}
    for i in range(0, len(tickers), chunk_size):
        batch = tickers[i:i + chunk_size]
        try:
            profiles.update(_get_profiles_batch(batch, api_key))
        except Exception:
            # tolerante a falhas por batch; segue adiante
            pass
    return profiles


# ---------- Normalizações ----------

def _norm_ticker(x) -> str:
    s = str(x).strip().upper()
    return "" if s == "NAN" else s

def _to_float_or_none(x):
    try:
        # aceita "9,5" e "9.5"
        return float(str(x).replace(",", "."))
    except Exception:
        return None


# ---------- Função principal (em memória) ----------

def organize_by_sector_from_df(df: pd.DataFrame, api_key: str) -> Dict[str, pd.DataFrame]:
    """
    Recebe um DataFrame consolidado com (pelo menos) colunas:
      - 'Ticker' (string)
      - 'Score'  (numérico ou string conversível)
    Retorna um dicionário { 'Technology': df_tech, 'Financials': df_fin, ... },
    já com colunas adicionadas 'Sector' e 'Industry', e ordenado por Score desc.
    Nada é salvo em disco.
    """
    if df is None or df.empty:
        return {}

    # Normaliza colunas essenciais
    if "Ticker" not in df.columns:
        raise ValueError("DataFrame não contém coluna 'Ticker'.")

    # Score é opcional; se existir, normalizamos
    if "Score" in df.columns:
        df = df.copy()
        df["Score"] = df["Score"].apply(_to_float_or_none)
    else:
        # se não houver Score, criamos para evitar KeyError em sort
        df = df.copy()
        df["Score"] = None

    # Limpa tickers
    df["Ticker"] = df["Ticker"].apply(_norm_ticker)
    df = df[df["Ticker"] != ""].dropna(subset=["Ticker"])

    # Busca perfis (sector/industry) na FMP
    unique_tickers = sorted(df["Ticker"].unique().tolist())
    profiles = fetch_profiles(unique_tickers, api_key=api_key)

    # Anexa Sector/Industry (fallback 'Unknown')
    df["Sector"] = df["Ticker"].apply(lambda t: profiles.get(t, ("Unknown", "Unknown"))[0])
    df["Industry"] = df["Ticker"].apply(lambda t: profiles.get(t, ("Unknown", "Unknown"))[1])

    # Agrupa por setor e retorna dict de DataFrames ordenados por Score
    out: Dict[str, pd.DataFrame] = {}
    for setor, df_setor in df.groupby("Sector", dropna=False, sort=True):
        df_sorted = df_setor.sort_values("Score", ascending=False).reset_index(drop=True)
        out[setor] = df_sorted

    return out
