# --- Standard library
from io import BytesIO
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
import os
import shutil
import subprocess
import tempfile

# --- Third-party
import matplotlib
matplotlib.use("Agg")  # usar backend não interativo antes de importar pyplot
import matplotlib.pyplot as plt
import pandas as pd
import requests
import yfinance as yf
from dotenv import load_dotenv

# --- Local application
from src.services.carteiras.pdf_generator import generate_pdf_buffer
from src.services.carteiras.metrics.vr_utils import compute_vr_for_symbol
from src.services.carteiras.fmp.targets import fetch_price_target_summary



load_dotenv()
FMP_API_KEY = os.getenv("FMP_API_KEY")

# =========================
# Cálculos e gráficos
# =========================
def _last_friday_for_weekly_change(d: date) -> date:
    if d.weekday() == 4:          # se hoje for sexta, usar a sexta ANTERIOR
        d = d - timedelta(days=7)
    while d.weekday() != 4:       # senão, usa a sexta ≤ hoje
        d -= timedelta(days=1)
    return d
def calculate_technical_indicators(bars: List[Any]):
    """
    Calcula indicadores técnicos (EMA10, EMA20, EMA200) a partir dos dados históricos.
    Retorna (ema10, ema20, ema200, df).
    Se dados insuficientes, retorna (None, None, None, DataFrame vazio).
    """
    if not bars or len(bars) < 10:  # Mínimo para EMA10
        return None, None, None, pd.DataFrame()

    df = pd.DataFrame([{'date': bar.date, 'close': bar.close} for bar in bars])
    df.set_index('date', inplace=True)

    # EMA10
    df['ema_10'] = df['close'].ewm(span=10).mean()
    ema_10_value = float(df['ema_10'].iloc[-1])

    # EMA20
    if len(bars) >= 20:
        df['ema_20'] = df['close'].ewm(span=20).mean()
        ema_20_value = float(df['ema_20'].iloc[-1])
    else:
        ema_20_value = None

    # EMA200
    if len(bars) >= 200:
        df['ema_200'] = df['close'].ewm(span=200).mean()
        ema_200_value = float(df['ema_200'].iloc[-1])
    else:
        ema_200_value = None

    return ema_10_value, ema_20_value, ema_200_value, df

def generate_chart(symbol: str, weekly_bars: List[Any], target_price: Optional[float], current_price: Optional[float] = None, outdir="templates/static"):
    """
    Gera gráfico SEMANAL com EMA10, EMA20 e EMA200.
    Retorna caminho absoluto do PNG ou None se dados insuficientes.
    """
    if not weekly_bars or len(weekly_bars) < 10:
        print(f"⚠️ Dados semanais insuficientes para {symbol} (mín. 10 candles).")
        return None

    # DataFrame semanal
    df = pd.DataFrame([{'date': b.date, 'close': b.close} for b in weekly_bars])
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date').sort_index()

    # EMAs semanais
    df['ema_10'] = df['close'].ewm(span=10, adjust=False).mean()
    ema_10_value = float(df['ema_10'].iloc[-1])

    df['ema_20'] = df['close'].ewm(span=20, adjust=False).mean()
    ema_20_value = float(df['ema_20'].iloc[-1])

    ema_200_value = None
    if len(df) >= 200:
        df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
        ema_200_value = float(df['ema_200'].iloc[-1])

    os.makedirs(outdir, exist_ok=True)
    chart_path = os.path.join(outdir, f"chart_{symbol}.png")

    plt.figure(figsize=(10, 5))

    # Preço semanal
    if current_price is None:
        current_price = df['close'].iloc[-1]
    plt.plot(df.index, df['close'], label=f'Preço Atual: ${current_price:.2f}', linewidth=2.5, color='#2E86AB')

    # Preço-alvo (se houver)
    if target_price is not None:
        plt.axhline(y=target_price, color='#C73E1D', linestyle='-.', linewidth=2, label=f'Preço alvo: ${target_price:.2f}')

    # EMA10
    plt.plot(df.index, df['ema_10'], label=f'EMA10: ${ema_10_value:.2f}', linestyle='-', linewidth=1.8, color='#228B22')

    # EMA20
    plt.plot(df.index, df['ema_20'], label=f'EMA20: ${ema_20_value:.2f}', linestyle='--', linewidth=2, color='#A23B72')

    # EMA200 (se disponível)
    if 'ema_200' in df.columns and ema_200_value is not None:
        plt.plot(df.index, df['ema_200'], label=f'EMA200: ${ema_200_value:.2f}', linestyle=':', linewidth=2, color='#F18F01')

    plt.title(f'Análise Técnica - {symbol}', fontsize=14, fontweight='bold')
    ax = plt.gca()
    ax.set_xlabel('Período', fontsize=12)
    ax.set_ylabel('Preço (USD)', fontsize=12)
    plt.legend(loc='upper left', frameon=True, fancybox=True, shadow=True, fontsize=10, bbox_to_anchor=(0.02, 0.98))
    ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)

    # >>> SUBSTITUA tudo daqui até o tight_layout() <<<
    from matplotlib.ticker import FuncFormatter, MaxNLocator
    import numpy as np
    # 1) Limites Y baseados no dado (close/EMAs + target)
    series = [df['close'], df['ema_10'], df['ema_20']]
    if 'ema_200' in df.columns:
        series.append(df['ema_200'])
    vals = pd.concat(series)
    y_min, y_max = float(vals.min()), float(vals.max())
    if target_price is not None:
        y_min = min(y_min, float(target_price))
        y_max = max(y_max, float(target_price))
    margin = max((y_max - y_min) * 0.08, 1e-6)  # ~8% de folga
    ax.set_ylim(y_min - margin, y_max + margin)

    # 2) Grade e ticks padronizados
    ax.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
    ax.yaxis.set_major_locator(MaxNLocator(nbins=6))                 # mesma qtde de ticks
    fmt = FuncFormatter(lambda v, _: f'${v:,.2f}')                   # sempre 2 casas e milhar
    ax.yaxis.set_major_formatter(fmt)
    ax.tick_params(axis='y', pad=4, labelleft=True, left=True)       # só configura o da esquerda

    # 3) Duplicar no lado direito **com os MESMOS** limites/ticks/formatter
    ax_r = ax.twinx()
    ax_r.set_ylim(ax.get_ylim())
    ax_r.yaxis.set_major_locator(ax.yaxis.get_major_locator())
    ax_r.yaxis.set_major_formatter(fmt)
    ax_r.tick_params(axis='y', pad=4, labelright=True, right=True)

    # (opcional) alinhar visualmente as labels à borda interna
    for lbl in ax.get_yticklabels():
        lbl.set_horizontalalignment('right')
    for lbl in ax_r.get_yticklabels():
        lbl.set_horizontalalignment('left')

    plt.tight_layout()

    plt.savefig(chart_path)
    plt.close()

    return os.path.abspath(chart_path)

def _crypto_daily_from_fmp(symbol: str, years: int = 1) -> pd.DataFrame:
    """
    Busca histórico DIÁRIO de cripto na FMP (ex.: BTCUSD/ETHUSD) e
    retorna SOMENTE o último ano por padrão.
    Retorna DF com colunas: date, open, high, low, close, volume.
    """
    api_key = os.getenv("FMP_API_KEY")
    if not api_key:
        return pd.DataFrame()

    pair = symbol.upper().strip()
    if not pair.endswith("USD"):
        pair = f"{pair}USD"

    sess = requests.Session()
    sess.headers.update({"User-Agent": "make_report-crypto/1.0"})

    def _full():
        url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{pair}"
        try:
            r = sess.get(url, params={"apikey": api_key}, timeout=20)
            r.raise_for_status()
            data = r.json()
            return data.get("historical") if isinstance(data, dict) else None
        except Exception:
            return None

    def _chart_1d():
        url = f"https://financialmodelingprep.com/api/v3/historical-chart/1day/{pair}"
        try:
            r = sess.get(url, params={"apikey": api_key}, timeout=20)
            r.raise_for_status()
            return r.json()  # lista de dicts
        except Exception:
            return None

    hist = _full() or _chart_1d()
    if not hist:
        return pd.DataFrame()

    df = pd.DataFrame(hist).rename(columns={"datetime": "date"})
    if "date" not in df or "close" not in df:
        return pd.DataFrame()

    # normalização
    df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce").dt.tz_localize(None)
    df = df.dropna(subset=["date", "close"]).sort_values("date")
    df = df[~df["date"].duplicated(keep="last")]

    # apenas o último ano
    cutoff = pd.Timestamp.today().normalize() - pd.DateOffset(years=years or 1)
    df = df[df["date"] >= cutoff]

    # garante colunas esperadas
    for col in ("open", "high", "low", "volume"):
        if col not in df:
            df[col] = pd.NA

    # tipos numéricos
    for col in ("open", "high", "low", "close", "volume"):
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df[["date", "open", "high", "low", "close", "volume"]]

def _to_weekly(df_daily: pd.DataFrame) -> pd.DataFrame:
    """Agrega diário → semanal, fechando na sexta (W-FRI)."""
    if df_daily is None or df_daily.empty:
        return pd.DataFrame()
    weekly = (
        df_daily.resample("W-FRI", on="date")
        .agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
        .dropna()
        .reset_index()
    )
    return weekly

def fetch_equity(
    symbol: str,
    quantity: float,
    is_etf: bool = False,
    antifragile: bool = False,
    target_price: Optional[float] = None,
    score: str = "–",
    vr: Optional[float] = None,   # <<< NOVO: volatilidade vinda do payload
    vs: Optional[float] = None    # <<< OPCIONAL: valorização semanal vinda do payload
):
    """
    Busca preço (FMP), calcula indicadores semanais, dividend yield (FMP→YF fallback),
    CAGR 10y (FMP→YF fallback), nome/segmento e gera gráfico semanal.
    Retorna dict pronto para o template.
    """

    # ----------------------------
    # Helpers internos
    # ----------------------------

    def _dividend_yield_fallback(symbol_: str, price_: float | None) -> float | None:
        if price_ is None or price_ <= 0:
            return None
        try:
            t = yf.Ticker(symbol_)
            dv = t.dividends
            if dv is not None and not dv.empty:
                cutoff = pd.Timestamp.today() - pd.DateOffset(years=1)
                ult12 = dv[dv.index >= cutoff].sum()
                if ult12 and ult12 > 0:
                    return float(ult12) / float(price_)
        except Exception:
            pass
        return None

    def _dividend_yield_fmp(symbol_: str, price_: float | None, api_key: Optional[str] = None) -> float | None:
        if price_ is None or price_ <= 0:
            return None
        api_key = api_key or FMP_API_KEY
        if not api_key:
            return None
        try:
            url = f"https://financialmodelingprep.com/api/v3/historical-price-full/stock_dividend/{symbol_.upper()}?apikey={api_key}"
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()
            hist = data.get("historical") or data.get("historicalDividends")
            if not hist:
                return None
            df = pd.DataFrame(hist)
            if df.empty or "date" not in df.columns or "dividend" not in df.columns:
                return None
            df["date"] = pd.to_datetime(df["date"])
            cutoff = pd.Timestamp.today() - pd.DateOffset(years=1)
            ult12 = df.loc[df["date"] >= cutoff, "dividend"].sum()
            if ult12 and ult12 > 0:
                return float(ult12) / float(price_)
        except Exception:
            pass
        return None

    def dividend_yield_calc(symbol__: str, price__: float | None, api_key: Optional[str] = None) -> float | None:
        sym = symbol__.strip().upper()
        try:
            res = _dividend_yield_fmp(sym, price__, api_key=api_key)
            if res is not None:
                return res
        except Exception:
            pass
        return _dividend_yield_fallback(sym, price__)

    def _growth_1y_pct(symbol: str, api_key: Optional[str] = FMP_API_KEY) -> float | None:
        """
        Retorna o crescimento acumulado (fração) dos ÚLTIMOS ~12 meses:
            (preço_final / preço_inicial) - 1

        - Usa FMP (serietype=line) como primária.
        - Faz fallback para Yahoo Finance (1y, ajustado).
        - Retorna None se não houver dados suficientes.
        """
        sym = (symbol or "").strip().upper()
        if not sym:
            return None

        cutoff = pd.Timestamp.today() - pd.DateOffset(years=1)

        # ---------- 1) Tenta FMP (linha diária) ----------
        if api_key:
            try:
                url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{sym}?serietype=line&apikey={api_key}"
                r = requests.get(url, timeout=20)
                r.raise_for_status()
                raw = (r.json() or {}).get("historical", [])
                if isinstance(raw, list) and raw:
                    df = pd.DataFrame(raw)
                    if {"date", "close"}.issubset(df.columns):
                        df["date"] = pd.to_datetime(df["date"])
                        df = df.sort_values("date")

                        # Janela de ~1 ano
                        df_win = df[df["date"] >= cutoff]
                        # Se muito ralo (ex.: poucos pregões), amplia levemente a janela
                        if len(df_win) < 2:
                            cutoff2 = pd.Timestamp.today() - pd.DateOffset(days=420)
                            df_win = df[df["date"] >= cutoff2]

                        if len(df_win) >= 2:
                            first = float(df_win["close"].iloc[0])
                            last  = float(df_win["close"].iloc[-1])
                            if first > 0:
                                return (last / first) - 1.0
            except Exception as e:
                print(f"[WARN] FMP 1y growth falhou p/ {sym}: {e}")

        # ---------- 2) Fallback Yahoo (1y ajustado) ----------
        try:
            if yf is None:
                raise RuntimeError("yfinance não disponível")
            t = yf.Ticker(sym)
            # 1 ano, mensal geralmente basta; se quiser mais granular, use '1wk' ou '1d'
            hist = t.history(period="1y", interval="1mo", auto_adjust=True)
            if not hist.empty and "Close" in hist:
                s = hist["Close"].dropna()
                if len(s) >= 2:
                    first = float(s.iloc[0])
                    last  = float(s.iloc[-1])
                    if first > 0:
                        return (last / first) - 1.0
        except Exception as e:
            print(f"[WARN] YF 1y growth falhou p/ {sym}: {e}")

        return None
    try:
        sym = symbol.strip().upper()

        # --- preço atual ---
        price_response = requests.get(
            f"https://financialmodelingprep.com/api/v3/quote/{sym}?apikey={FMP_API_KEY}",
            timeout=20
        )
        price_response.raise_for_status()
        price_data = price_response.json()
        if not isinstance(price_data, list) or not price_data:
            raise ValueError(f"Dados de preço inválidos para {sym}")
        price = price_data[0].get("price")
        if price is None:
            raise ValueError(f"Não foi possível obter preço para {sym}")
        price = float(price)

        # --- histórico diário -> weekly bars + VS semanal ---
        vs_pct = None
        weekly_bars: list = []
        historical_response = requests.get(
            f"https://financialmodelingprep.com/api/v3/historical-price-full/{sym}?timeseries=260&apikey={FMP_API_KEY}",
            timeout=20
        )
        if historical_response.ok:
            historical_data = historical_response.json()
            if "historical" in historical_data:
                # já vem em ordem decrescente; inverter para crescente
                daily_data = historical_data["historical"][::-1]
                if daily_data:
                    df_daily = pd.DataFrame(daily_data)
                    df_daily["date"] = pd.to_datetime(df_daily["date"])
                    df_daily = df_daily.set_index("date").sort_index()

                    # VS semanal: spot vs última sexta
                    try:
                        last_friday = pd.Timestamp.today().normalize() - pd.offsets.Week(weekday=4)
                        s_close = df_daily["close"].dropna()
                        ref = s_close.loc[s_close.index <= last_friday]
                        if not ref.empty:
                            friday_close = float(ref.iloc[-1])
                            if friday_close > 0:
                                vs_pct = (price / friday_close - 1.0) * 100.0
                    except Exception:
                        vs_pct = None

                    # gera barras semanais
                    for _, week_data in df_daily.groupby(pd.Grouper(freq="W")):
                        if not week_data.empty:
                            bar = type("Bar", (), {
                                "open": week_data["open"].iloc[0],
                                "high": week_data["high"].max(),
                                "low": week_data["low"].min(),
                                "close": week_data["close"].iloc[-1],
                                "volume": week_data["volume"].sum(),
                                "date": week_data.index[-1].strftime("%Y-%m-%d"),
                            })()
                            weekly_bars.append(bar)

        # --- TARGET: payload tem prioridade; se não vier, tenta FMP ---
        final_target = None
        if target_price is not None:
            try:
                final_target = float(target_price)
            except Exception:
                final_target = None
        if final_target is None:
            try:
                pt = fetch_price_target_summary(sym)
                final_target = float(pt.target_avg) if pt and pt.target_avg is not None else None
            except Exception:
                final_target = None

        # --- VP: distância até o alvo em % ---
        vp_pct = (final_target / price - 1.0) * 100.0 if (final_target is not None and price > 0) else None

        # --- VR: usa payload, senão calcula ---
        vr_pct = None
        if vr is not None:
            try:
                vr_pct = float(vr)
            except Exception:
                vr_pct = None
        else:
            try:
                res_vr = compute_vr_for_symbol(sym, benchmark="SPY", years=5, min_obs=150)
                vr_pct = res_vr.get("VR")
            except Exception:
                vr_pct = None

        # --- dividend yield ---
        div_yield = dividend_yield_calc(sym, price)

        # --- nome e setor ---
        company_name, sector = None, None
        try:
            r = requests.get(
                f"https://financialmodelingprep.com/api/v3/profile/{sym}?apikey={FMP_API_KEY}",
                timeout=20
            )
            if r.ok:
                data = r.json()
                if isinstance(data, list) and data:
                    company_name = data[0].get("companyName")
                    sector = data[0].get("sector")
        except Exception:
            pass
        if not company_name or not sector:
            try:
                info = yf.Ticker(sym).info
                company_name = company_name or info.get("longName") or info.get("shortName")
                sector = sector or info.get("sector")
            except Exception:
                pass

        # --- crescimento 1y ---
        _growth_1y = _growth_1y_pct(sym)

        # --- EMAs e gráfico (USAR o mesmo alvo do card) ---
        ema10, ema20, ema200, _ = calculate_technical_indicators(weekly_bars)
        chart_path = generate_chart(sym, weekly_bars, final_target)  # <<<<<< CORRIGIDO

        inv = price * float(quantity)

        antifragile_entry_price = None
        if is_etf and antifragile and price is not None:
            antifragile_entry_price = float(price) * 1.03

        return {
            "symbol": sym,
            "unit_price": price,
            "unitPrice": price,
            "quantity": float(quantity),
            "target_price": final_target,     # <<<<<< CARD LÊ DAQUI
            "targetPrice": final_target,
            "score": score,
            "dividend_yield": div_yield,
            "dividendYield": div_yield,
            "investment": inv,
            "type": "ETF" if is_etf else "STOCK",
            "company_name": company_name,
            "sector": sector,
            "chart": chart_path,
            "ema_10": ema10, "ema10": ema10,
            "ema_20": ema20, "ema20": ema20,
            "ema_200": ema200, "ema200": ema200,
            "average_growth": round(_growth_1y * 100, 1) if _growth_1y is not None else None,
            "averageGrowth": round(_growth_1y * 100, 1) if _growth_1y is not None else None,
            "antifragile_entry_price": round(antifragile_entry_price, 4) if antifragile_entry_price else None,
            "antifragileEntryPrice": round(antifragile_entry_price, 4) if antifragile_entry_price else None,
            "vs": round(vs_pct, 2) if vs_pct is not None else None,
            "vp": round(vp_pct, 2) if vp_pct is not None else None,
            "vr": round(vr_pct, 2) if vr_pct is not None else None,
        }

    except Exception as e:
        print(f"[ERRO] fetch_equity falhou para {symbol}: {e}")
        raise

def _weekly_df_to_bars(weekly_df: pd.DataFrame):
    """Converte o DataFrame semanal em lista de 'bars' (obj. com attrs), como generate_chart espera."""
    bars = []
    if weekly_df is None or weekly_df.empty:
        return bars
    for _, r in weekly_df.iterrows():
        Bar = type("Bar", (), {})  # objeto leve
        b = Bar()
        b.date   = r["date"].strftime("%Y-%m-%d") if hasattr(r["date"], "strftime") else str(r["date"])
        b.open   = float(r["open"])
        b.high   = float(r["high"])
        b.low    = float(r["low"])
        b.close  = float(r["close"])
        b.volume = float(r.get("volume", 0) or 0)
        bars.append(b)
    return bars

def fetch_crypto(
    symbol: str,
    quantity: float = 0.0,
    company_name: Optional[str] = None,
    entry_price: Optional[float] = None,      # pode vir override externo
    target_price: Optional[float] = None,     # pode vir override externo
    expected_growth: Optional[float] = None,
    want_chart: bool = True,
) -> dict:
    """
    Preço: FMP -> yfinance -> CoinGecko
    Gráfico: FMP (histórico diário -> semanal W-FRI) + target
    Retorna:
      - unit_price = preço atual (spot) para o card
      - entry_price = EMA20 semanal
      - target_price = máximo de 12 meses, salvo override
      - vs = variação semanal em %, comparando o spot com o fechamento da “sexta de referência”
            (se hoje for sexta, usa a sexta ANTERIOR; senão, a sexta ≤ hoje).
    """
    sym_raw = symbol.strip()
    sym_fmp = sym_raw.upper().replace("-", "")
    if not sym_fmp.endswith("USD"):
        sym_fmp = f"{sym_fmp}USD"  # FMP: BTCUSD
    sym_yf = sym_raw.upper() if "-" in sym_raw else f"{sym_raw.upper()}-USD"  # yfinance: BTC-USD

    # -------- helpers de preço "spot" --------
    def _fmp_price() -> Optional[float]:
        api = os.getenv("FMP_API_KEY")
        if not api:
            return None
        try:
            r = requests.get(
                f"https://financialmodelingprep.com/api/v3/quote/{sym_fmp}",
                params={"apikey": api}, timeout=10
            )
            if r.ok:
                data = r.json()
                if isinstance(data, list) and data and data[0].get("price") is not None:
                    return float(data[0]["price"])
        except Exception:
            pass
        return None

    def _yf_price() -> Optional[float]:
        t = yf.Ticker(sym_yf)
        for period, interval in [("2d","1d"),("5d","1d"),("1mo","1d"),("7d","1h")]:
            try:
                h = t.history(period=period, interval=interval, auto_adjust=True)
                if h is not None and not h.empty and "Close" in h:
                    s = h["Close"].dropna()
                    if not s.empty:
                        return float(s.iloc[-1])
            except Exception:
                pass
        try:
            fi = getattr(t, "fast_info", None)
            lp = getattr(fi, "last_price", None) if fi is not None else None
            if lp is not None:
                return float(lp)
        except Exception:
            pass
        try:
            info = t.info
            rmp = info.get("regularMarketPrice")
            if rmp is not None:
                return float(rmp)
        except Exception:
            pass
        return None

    def _coingecko_price() -> Optional[float]:
        mapping = {
            "BTC-USD": "bitcoin", "ETH-USD": "ethereum",
            "SOL-USD": "solana",  "ADA-USD": "cardano", "BNB-USD": "binancecoin"
        }
        cg_id = mapping.get(sym_yf.upper()) or sym_yf.split("-")[0].lower()
        try:
            r = requests.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": cg_id, "vs_currencies": "usd"},
                timeout=10
            )
            if r.ok:
                data = r.json()
                if cg_id in data and "usd" in data[cg_id]:
                    return float(data[cg_id]["usd"])
        except Exception:
            pass
        return None

    # -------- começa a montar o dict de saída --------
    d: dict[str, Any] = {
        "symbol": sym_raw.upper(),
        "company_name": (company_name or sym_raw.upper()),
        "quantity": float(quantity or 0.0),
        "type": "CRYPTO",
        "unit_price": None,     # spot (card)
        "entry_price": None,    # EMA20 semanal
        "target_price": None,   # máx 12m (ou override)
        "vs": None,             # % semanal
        "chart": None,
        "average_growth": expected_growth,
        "averageGrowth": expected_growth,
    }

    # -------- preço "spot" (fallback) --------
    spot_price = _fmp_price() or _yf_price() or _coingecko_price()
    if spot_price is None:
        raise RuntimeError(f"Sem preço disponível para {symbol}")
    d["unit_price"] = float(spot_price)
    # -------- histórico + semanais + indicadores --------
    chart_path = None
    try:
        # 1) Diário (último ano)
        df_daily = _crypto_daily_from_fmp(sym_fmp, years=1)
        if df_daily is None or df_daily.empty:
            # fallback por yfinance
            t = yf.Ticker(sym_yf)
            yf_hist = t.history(period="1y", interval="1d", auto_adjust=True)
            if yf_hist is not None and not yf_hist.empty:
                df_daily = (
                    yf_hist.reset_index()[["Date","Close"]]
                    .rename(columns={"Date":"date","Close":"close"})
                )
            else:
                raise ValueError("Sem dados diários (último ano).")
        if not pd.api.types.is_datetime64_any_dtype(df_daily["date"]):
            df_daily["date"] = pd.to_datetime(df_daily["date"])

        # 2) Semanal (W-FRI) para o gráfico
        weekly_df = _to_weekly(df_daily)
        if weekly_df is None or weekly_df.empty:
            raise ValueError("Sem dados semanais após o resample.")

        # 3b) sexta de referência para VS: "sexta anterior se hoje for sexta"
        from datetime import date, timedelta
        def _last_friday_for_weekly_change(dref: date) -> date:
            if dref.weekday() == 4:  # sexta
                dref = dref - timedelta(days=7)
            while dref.weekday() != 4:
                dref -= timedelta(days=1)
            return dref

        ref_friday = _last_friday_for_weekly_change(date.today())

        # Normalizar datas para comparação correta
        df_daily["date"] = pd.to_datetime(df_daily["date"]).dt.tz_localize(None).dt.normalize()

        # garanta ORDEM ASC
        df_daily = df_daily.sort_values("date")

        # Normalizar ref_friday para pd.Timestamp
        ref_friday_ts = pd.Timestamp(ref_friday).normalize()

        # pegue o ÚLTIMO registro <= sexta de referência
        row = df_daily.loc[df_daily["date"] <= ref_friday_ts].tail(1)
        last_friday_close = float(row["close"].iloc[0]) if not row.empty else None

        # 4) entry_price: EMA20 semanal
        wk_close = weekly_df.set_index("date")["close"]
        ema20 = wk_close.ewm(span=20, adjust=False, min_periods=20).mean()
        last_ema20 = ema20.iloc[-1]
        d["entry_price"] = float(last_ema20) if pd.notna(last_ema20) else None

        # 5) target: máximo fechamento do último ano (override se vier)
        computed_target = float(df_daily["close"].max())
        final_target = target_price if target_price is not None else computed_target
        d["target_price"] = final_target

        # 6) VS correto em %
        d["vs"] = ((float(spot_price) / last_friday_close) - 1.0) if last_friday_close else None

        
        
        # 7) Gráfico: semanais + (opcional) linha do preço atual
        if want_chart:
            bars = _weekly_df_to_bars(weekly_df)
            if bars:
                # garante pasta de saída
                os.makedirs("templates/static", exist_ok=True)
                try:
                    chart_path = generate_chart(
                        d["symbol"],
                        weekly_bars=bars,
                        target_price=final_target,
                        current_price=float(spot_price),  # se a função aceitar
                        outdir="templates/static",
                    )
                except TypeError:
                    # compat: se generate_chart não aceitar current_price
                    chart_path = generate_chart(
                        d["symbol"],
                        weekly_bars=bars,
                        target_price=final_target,
                        outdir="templates/static",
                    )
                d["chart"] = chart_path

    except Exception as e:
        print(f"⚠️ Erro ao preparar cripto {symbol}: {e}")
        if d["unit_price"] is None:
            d["unit_price"] = float(spot_price)

    # 8) investimento
    d["investment"] = float(d["unit_price"] or spot_price) * d["quantity"]
    return d

def make_real_estate_position(name: str, invested_value: float, appreciation: float):
    """
    Cria registro de 'Imóveis'.
    - appreciation aceita 0.12 ou 12 (interpreta 12%).
    """
    appr = float(appreciation)
    if appr > 1.5:
        appr = appr / 100.0

    current_value = float(invested_value) * (1.0 + appr)

    return {
        'symbol': name,
        'unit_price': None,
        'unitPrice': None,
        'quantity': None,
        'target_price': None,
        'targetPrice': None,
        'score': None,
        'dividend_yield': None,
        'dividendYield': None,
        'investment': float(invested_value),
        'type': 'REAL_ESTATE',
        'company_name': None,
        'sector': 'Real Estate',
        'chart': None,
        'ema_10': None,
        'ema10': None,
        'ema_20': None,
        'ema20': None,
        'ema_200': None,
        'ema200': None,
        'average_growth': None,
        'averageGrowth': None,
        'appreciation_pct': appr,
        'appreciationPct': appr,
        'current_value': round(current_value, 2),
        'currentValue': round(current_value, 2),
    }

def html_to_pdf_from_string(html_content: str) -> bytes:
    """
    Converte HTML para PDF usando Playwright Chromium headless.
    Retorna o PDF como bytes.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html_content, wait_until="networkidle")
        pdf_bytes = page.pdf(format="A4", margin={"top": "1cm", "bottom": "1cm"})
        browser.close()
    return pdf_bytes

def link_callback(uri, rel, base_url):
    """
    Callback para imagens e CSS externas.
    """
    import os
    if base_url:
        if uri.startswith("http://") or uri.startswith("https://"):
            return uri
        path = os.path.join(base_url, uri)
        if os.path.isfile(path):
            return path
        else:
            raise Exception(f"Arquivo não encontrado: {path}")
    return uri

# =========================
# Builder a partir do payload do front
# =========================
def build_report_from_payload(payload: Dict[str, Any]) -> BytesIO:
    """
    Consome o payload canônico do front e gera HTML+PDF.
    Retorna caminho do PDF gerado.
    Espera chaves:
      investor (str), bonds[], stocks[], opp_stocks[], etfs[], etfs_op[], etfs_af[], cryptos[], real_estates[]
    """
    investor = payload.get("investor") or "Investidor"

    # Bonds já chegam com unit_price/quantity
    bonds_in = payload.get("bonds") or []
    bonds: List[Dict[str, Any]] = []
    for b in bonds_in:
        unit = float(b["unit_price"])
        qty = float(b["quantity"])
        bonds.append({
            'name': b['name'],
            'code': b['code'],
            'maturity': b['maturity'],
            'unit_price': unit,
            'quantity': qty,
            'investment': unit * qty,
            'coupon': float(b.get('coupon', 0) or 0),
            'description': b.get('description') if isinstance(b.get('description'), list) else ([b.get('description')] if b.get('description') else []),
        })

    def _num(x):
        if x is None: 
            return None
        if isinstance(x, (int, float)): 
            return float(x)
        s = str(x).strip().replace(".", "").replace(",", ".")
        try:
            return float(s)
        except Exception:
            return None


    # Equities e ETFs (buscam dados de mercado)
    def _mk_equities(items: List[Dict[str, Any]], is_etf: bool, antifragile: bool = False):
        out = []
        for it in items or []:
            sym   = str(it.get("symbol", "")).upper().strip()
            qty   = _num(it.get("quantity")) or 0.0
            tp    = _num(it.get("target_price"))
            score = _num(it.get("score"))
            vr    = _num(it.get("vr"))   # <<< volatilidade vinda do payload
            vs    = _num(it.get("vs"))   # <<< valorização semanal (se vier no payload)

            out.append(
                fetch_equity(
                    sym, qty,
                    is_etf=is_etf,
                    antifragile=antifragile,
                    target_price=tp,
                    score=score,
                    vr=vr,          # <<< passe adiante
                    vs=vs           # <<< opcional: passe adiante
                )
            )
        return out

    reits = _mk_equities(payload.get("reits"), is_etf=False)
    stocks = _mk_equities(payload.get("stocks"), is_etf=False)
    opp_stocks = _mk_equities(payload.get("opp_stocks"), is_etf=False)
    etfs = _mk_equities(payload.get("etfs"), is_etf=True)
    etfs_op = _mk_equities(payload.get("etfs_op"), is_etf=True)
    etfs_af = _mk_equities(payload.get("etfs_af"), is_etf=True, antifragile=True)

    # Criptos
    cryptos_in = payload.get("cryptos") or []
    cryptos: List[Dict[str, Any]] = []
    for c in cryptos_in:
        cryptos.append(
            fetch_crypto(
                symbol=str(c["symbol"]).upper().strip(),
                quantity=float(c["quantity"]),
                company_name=c.get("company_name"),
                expected_growth=float(c["expected_growth"]) if c.get("expected_growth") is not None else None
            )
        )

    # Imóveis
    real_estates_in = payload.get("real_estates") or []
    real_estates: List[Dict[str, Any]] = []
    for r in real_estates_in:
        real_estates.append(
            make_real_estate_position(
                name=r["name"],
                invested_value=float(r["invested_value"]),
                appreciation=float(r["appreciation"])
            )
        )

    # Renderiza e exporta
    pdf_buffer = generate_pdf_buffer(
    investor=investor,
    bonds=bonds,
    reits=reits,
    stocks=stocks,
    etfs=etfs,
    etfs_op=etfs_op,
    etfs_af=etfs_af,
    opp_stocks=opp_stocks,
    cryptos=cryptos,
    real_estates=real_estates
    )
    return pdf_buffer
