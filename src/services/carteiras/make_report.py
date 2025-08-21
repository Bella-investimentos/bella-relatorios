import os
import shutil
import subprocess
from datetime import datetime
from typing import Optional, List, Dict, Any
import os
import shutil
import subprocess
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import requests
import yfinance as yf
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader
import pandas as pd
import tempfile
from src.services.carteiras.pdf_generator import generate_pdf_buffer

# =========================
# Config / Env
# =========================
load_dotenv()
FMP_API_KEY = os.getenv("FMP_API_KEY")

# =========================
# Cálculos e gráficos
# =========================
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



def generate_chart(symbol: str, weekly_bars: List[Any], target_price: Optional[float], outdir="templates/static"):
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
    ax.tick_params(axis='y', which='both', labelleft=True, labelright=True, left=True, right=True)
    ax.yaxis.set_ticks_position('both')

    ax_r = ax.twinx()
    ax_r.set_ylim(ax.get_ylim())
    ax_r.set_yticks(ax.get_yticks())
    ax_r.set_ylabel('Preço (USD)', fontsize=12)
    ax_r.grid(False)

    plt.tight_layout()
    plt.savefig(chart_path)
    plt.close()

    return os.path.abspath(chart_path)


# =========================
# Dados de mercado
# =========================
def fetch_equity(
    symbol: str,
    quantity: float,
    is_etf: bool = False,
    antifragile: bool = False,
    target_price: Optional[float] = None,
    score: str = "–"
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

    def _cagr_10y(symbol: str, api_key: Optional[str] = FMP_API_KEY) -> float | None:
        sym = symbol.strip().upper()

        # --- 1) Tenta via FMP ---
        try:
            url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{sym}?serietype=line&apikey={api_key}"
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            data = response.json()

            if "historical" in data and len(data["historical"]) > 2:
                hist = list(reversed(data["historical"]))  # FMP vem invertido
                first = float(hist[0]["close"])
                last = float(hist[-1]["close"])

                from datetime import datetime
                d0 = datetime.strptime(hist[0]["date"], "%Y-%m-%d")
                d1 = datetime.strptime(hist[-1]["date"], "%Y-%m-%d")
                years = (d1 - d0).days / 365.25

                if first > 0 and years > 0:
                    return (last / first) ** (1 / years) - 1.0
        except Exception as e:
            print(f"[WARN] FMP CAGR falhou para {sym}: {e}")

        # --- 2) Fallback via Yahoo Finance ---
        try:
            t = yf.Ticker(sym)
            hist = t.history(period="10y", interval="1mo", auto_adjust=True)
            if not hist.empty and 'Close' in hist:
                first = float(hist['Close'].iloc[0])
                last = float(hist['Close'].iloc[-1])
                years = (hist.index[-1] - hist.index[0]).days / 365.25
                if first > 0 and years > 0:
                    return (last / first) ** (1 / years) - 1.0
        except Exception as e:
            print(f"[WARN] YF CAGR falhou para {sym}: {e}")

        return None

    # ----------------------------
    # Corpo principal
    # ----------------------------
    try:
        sym = symbol.strip().upper()

        # preço atual via FMP
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

        # barras semanais via FMP
        weekly_bars: list = []
        historical_response = requests.get(
            f"https://financialmodelingprep.com/api/v3/historical-price-full/{sym}?timeseries=260&apikey={FMP_API_KEY}",
            timeout=20
        )
        if historical_response.ok:
            historical_data = historical_response.json()
            if "historical" in historical_data:
                daily_data = historical_data["historical"][::-1]
                if daily_data:
                    df_daily = pd.DataFrame(daily_data)
                    df_daily["date"] = pd.to_datetime(df_daily["date"])
                    df_daily = df_daily.set_index("date").sort_index()
                    for _, week_data in df_daily.groupby(pd.Grouper(freq="W")):
                        if not week_data.empty:
                            bar = type("Bar", (), {
                                "open": week_data["open"].iloc[0],
                                "high": week_data["high"].max(),
                                "low": week_data["low"].min(),
                                "close": week_data["close"].iloc[-1],
                                "volume": week_data["volume"].sum(),
                                "date": week_data.index[-1].strftime("%Y-%m-%d")
                            })()
                            weekly_bars.append(bar)

        # dividend yield
        div_yield = dividend_yield_calc(sym, price)

        # nome e setor
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

        # CAGR 10y
        cagr_10y = _cagr_10y(sym)

        # EMAs e gráfico
        ema10, ema20, ema200, _ = calculate_technical_indicators(weekly_bars)
        chart_path = generate_chart(sym, weekly_bars, target_price)

        inv = float(price) * float(quantity)

        antifragile_entry_price = None
        if is_etf and antifragile and price is not None:
            antifragile_entry_price = float(price) * 1.03

        return {
            "symbol": sym,
            "unit_price": float(price),
            "unitPrice": float(price),
            "quantity": float(quantity),
            "target_price": target_price,
            "targetPrice": target_price,
            "score": score,
            "dividend_yield": div_yield,
            "dividendYield": div_yield,
            "investment": inv,
            "type": "ETF" if is_etf else "STOCK",
            "company_name": company_name,
            "sector": sector,
            "chart": chart_path,
            "ema_10": ema10,
            "ema10": ema10,
            "ema_20": ema20,
            "ema20": ema20,
            "ema_200": ema200,
            "ema200": ema200,
            "average_growth": round(cagr_10y * 100, 1) if cagr_10y is not None else None,
            "averageGrowth": round(cagr_10y * 100, 1) if cagr_10y is not None else None,
            "antifragile_entry_price": round(antifragile_entry_price, 4) if antifragile_entry_price else None,
            "antifragileEntryPrice": round(antifragile_entry_price, 4) if antifragile_entry_price else None,
        }

    except Exception as e:
        print(f"[ERRO] fetch_equity falhou para {symbol}: {e}")
        raise

def fetch_crypto(
    symbol: str,
    quantity: float = 0.0,
    company_name: Optional[str] = None,
    expected_growth: Optional[float] = None
):
    """
    Busca preço de cripto com fallbacks:
    1) yfinance (vários períodos/intervalos + fast_info/info)
    2) FMP (se FMP_API_KEY existir)
    3) CoinGecko (sem API key)
    """
    def _yf_price(sym: str) -> Optional[float]:
        t = yf.Ticker(sym)
        for period, interval in [("2d", "1d"), ("5d", "1d"), ("1mo", "1d"), ("7d", "1h")]:
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

    def _fmp_price(sym: str) -> Optional[float]:
        api = os.getenv("FMP_API_KEY")
        if not api:
            return None
        fmp_sym = sym.replace("-", "")
        try:
            url = f"https://financialmodelingprep.com/api/v3/quote/{fmp_sym}?apikey={api}"
            r = requests.get(url, timeout=10)
            if r.ok:
                data = r.json()
                if isinstance(data, list) and data and data[0].get("price") is not None:
                    return float(data[0]["price"])
        except Exception:
            pass
        return None

    def _coingecko_price(sym: str) -> Optional[float]:
    
        mapping = {
            "BTC-USD": "bitcoin",
            "ETH-USD": "ethereum",
            "SOL-USD": "solana",
            "ADA-USD": "cardano",
            "BNB-USD": "binancecoin"
        }
        cg_id = mapping.get(sym.upper())
        if not cg_id:
            
            cg_id = sym.split("-")[0].lower()
        try:
            url = f"https://api.coingecko.com/api/v3/simple/price"
            r = requests.get(url, params={"ids": cg_id, "vs_currencies": "usd"}, timeout=10)
            if r.ok:
                data = r.json()
                if cg_id in data and "usd" in data[cg_id]:
                    return float(data[cg_id]["usd"])
        except Exception:
            pass
        return None

    try:
        price = _fmp_price(symbol) or _yf_price(symbol) or _coingecko_price(symbol)
        if price is None:
            raise ValueError(f"Sem preço disponível para {symbol}")

        return {
            "symbol": symbol.upper(),
            "company_name": company_name if company_name else symbol.upper(),
            "unit_price": price,
            "unitPrice": price,
            "quantity": quantity,
            "investment": price * quantity,
            "type": "CRYPTO",
            "average_growth": expected_growth,
            "averageGrowth": expected_growth,
        }
    except Exception as e:
        raise RuntimeError(f"Falha ao obter dados da criptomoeda {symbol}: {e}")

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

def render_report(
    investor: str,
    bonds: List[Dict[str, Any]],
    stocks: List[Dict[str, Any]],
    etfs: List[Dict[str, Any]],
    etfs_op: Optional[List[Dict[str, Any]]] = None,
    etfs_af: Optional[List[Dict[str, Any]]] = None,
    opp_stocks: Optional[List[Dict[str, Any]]] = None,
    cryptos: Optional[List[Dict[str, Any]]] = None,
    real_estates: Optional[List[Dict[str, Any]]] = None
) -> str:  
    date = datetime.now().strftime('%d/%m/%Y')
    opp_stocks = opp_stocks or []
    etfs_op = etfs_op or []
    etfs_af = etfs_af or []
    cryptos = cryptos or []
    real_estates = real_estates or []

    bonds_total = sum(b.get('investment', 0) for b in bonds)
    stocks_total = sum(a.get('investment', 0) for a in stocks)
    opp_stocks_total = sum(a.get('investment', 0) for a in opp_stocks)
    etfs_total = sum(e.get('investment', 0) for e in etfs)
    etfs_op_total = sum(e.get('investment', 0) for e in etfs_op)
    etfs_af_total = sum(e.get('investment', 0) for e in etfs_af)
    cryptos_total = sum(c.get('investment', 0) for c in cryptos)
    real_estates_total = sum(r.get('current_value') or 0 for r in real_estates)

    total_value = (
        bonds_total + stocks_total + opp_stocks_total +
        etfs_total + etfs_op_total + etfs_af_total +
        cryptos_total + real_estates_total
    )

    env = Environment(loader=FileSystemLoader('templates'), autoescape=True)
    tpl = env.get_template('relatorio_acoes_etfs.html.j2')
    html = tpl.render(
        investor=investor,
        date=date,
        bonds=bonds, bonds_total=bonds_total,
        stocks=stocks, stocks_total=stocks_total,
        opp_stocks=opp_stocks, opp_stocks_total=opp_stocks_total,
        etfs=etfs, etfs_total=etfs_total,
        etfs_op=etfs_op, etfs_op_total=etfs_op_total,
        etfs_af=etfs_af, etfs_af_total=etfs_af_total,
        cryptos=cryptos, cryptos_total=cryptos_total,
        real_estates=real_estates, real_estates_total=real_estates_total,
        total_value=total_value
    )
    print("✅ HTML gerado em memória")
    return html  # retorna HTML em memória

# =========================
# Builder a partir do payload do front
# =========================
def build_report_from_payload(payload: Dict[str, Any]) -> str:
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

    # Equities e ETFs (buscam dados de mercado)
    def _mk_equities(items: List[Dict[str, Any]], is_etf: bool, antifragile: bool = False):
        out = []
        for it in items or []:
            sym = str(it["symbol"]).upper().strip()
            qty = float(it["quantity"])
            tp = it.get("target_price")
            tp = float(tp) if tp is not None else None
            score = it.get("score")
            score = float(score) if score is not None else None
            
            out.append(fetch_equity(sym, qty, is_etf=is_etf, antifragile=antifragile, 
                                target_price=tp, score=score))  
        return out

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
    stocks=stocks,
    etfs=etfs,
    etfs_op=etfs_op,
    etfs_af=etfs_af,
    opp_stocks=opp_stocks,
    cryptos=cryptos,
    real_estates=real_estates
)
    return pdf_buffer

