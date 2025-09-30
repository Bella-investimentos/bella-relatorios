# src/services/carteiras/selecaoAtivos/fetch_sheets.py
import pandas as pd
import numpy as np

def _norm_ticker(x: str) -> str:
    if x is None:
        return ""
    s = str(x).strip().upper()
    return "" if s in ("", "NAN", "NONE") else s

def _to_float_or_none(x):
    try:
        return float(str(x).strip().replace(",", "."))
    except Exception:
        return np.nan

def fetch_and_save_sheets(ABAS: dict, pasta: str | None = None, save: bool = False):
    frames = []
    for _, url in ABAS.items():
        # Lê sem cabeçalho e autodetecta separador ("," ou ";")
        df_raw = pd.read_csv(
            url,
            header=None,
            dtype=str,
            sep=None,           # autodetecta
            engine="python",    # necessário p/ sep=None
            on_bad_lines="skip" # ignora linhas quebradas
        )
        if df_raw.shape[1] < 2:
            # pula abas estranhas
            continue

        # Garante só as duas primeiras colunas (A=ticker, B=score)
        df = df_raw.iloc[:, :2].copy()
        df.columns = ["Ticker", "Score"]

        # Normalizações
        df["Ticker"] = df["Ticker"].map(_norm_ticker)
        df["Score"]  = df["Score"].map(_to_float_or_none)

        # Descarta linhas sem ticker
        df = df[df["Ticker"] != ""].reset_index(drop=True)

        frames.append(df)

    if not frames:
        return pd.DataFrame(columns=["Ticker", "Score"])

    df_all = pd.concat(frames, ignore_index=True)

    if save and pasta:
        import os
        os.makedirs(pasta, exist_ok=True)
        out = os.path.join(pasta, "todos_tickers.csv")
        df_all.to_csv(out, index=False)
        return df_all, out

    return df_all
