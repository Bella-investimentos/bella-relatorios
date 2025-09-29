# src/services/carteiras/selecaoAtivos/fetch_sheets.py
import pandas as pd

def fetch_and_save_sheets(ABAS: dict, pasta: str | None = None, save: bool = False):
    frames = []
    for _, url in ABAS.items():
        frames.append(pd.read_csv(url))
    df_all = pd.concat(frames, ignore_index=True)

    if save and pasta:
        import os
        os.makedirs(pasta, exist_ok=True)
        out = os.path.join(pasta, "todos_tickers.csv")
        df_all.to_csv(out, index=False)
        return df_all, out

    return df_all
