# src/services/carteiras/assembleia/monthly_calc.py
from __future__ import annotations
import os, requests, datetime as dt, calendar
from typing import Dict, Any, List, Tuple, Optional

try:
    import yfinance as yf
except Exception:
    yf = None

def _collect_symbols(payload: Dict[str, Any]) -> List[Tuple[str, str]]:
    """
    Retorna [(symbol, kind)] deduplicado a partir dos grupos do payload.
    kind: "EQUITY" | "CRYPTO" (para tratativas de símbolo).
    """
    groups_equity = [
        "etfs_cons", "etfs_mod", "etfs_agr",
        "stocks_mod", "stocks_arj", "stocks_opp",
        "reits_cons", "smallcaps_arj", "hedge",
    ]
    groups_crypto = ["crypto"]

    out: List[Tuple[str, str]] = []
    seen = set()

    def add(sym: str, kind: str):
        s = (sym or "").strip().upper()
        if not s or s in seen:
            return
        seen.add(s)
        out.append((s, kind))

    for g in groups_equity:
        for it in (payload.get(g) or []):
            add(it.get("symbol") or it.get("ticker"), "EQUITY")

    for it in (payload.get("crypto") or []):
        add(it.get("symbol"), "CRYPTO")

    return out

def _month_bounds(today: Optional[dt.date] = None) -> Tuple[dt.date, dt.date]:
    """Início/fim do mês corrente."""
    if today is None:
        today = dt.date.today()
    first = today.replace(day=1)
    last_day = calendar.monthrange(today.year, today.month)[1]
    last = today.replace(day=last_day)
    return first, last

def _first_friday(d1: dt.date, d2: dt.date) -> dt.date:
    """Primeira sexta em [d1, d2]."""
    d = d1
    while d <= d2:
        if d.weekday() == 4:  # sexta
            return d
        d += dt.timedelta(days=1)
    return d1  # fallback

def _last_friday(d1: dt.date, d2: dt.date) -> dt.date:
    """Última sexta em [d1, d2] (ou a mais recente <= d2)."""
    d = d2
    while d >= d1:
        if d.weekday() == 4:
            return d
        d -= dt.timedelta(days=1)
    return d2  # fallback

def _fmt_fmp_symbol(sym: str, kind: str) -> str:
    """
    FMP usa 'BTCUSD' etc. Para crypto, removo hífen e sufixo USD se vier variante.
    Para ações/ETFs/REITs, deixo como está.
    """
    if kind == "CRYPTO":
        s = sym.replace("-", "").replace("USDT", "USD")
        if s.endswith("USD"):
            return s
        return s + "USD"
    return sym

def _yf_symbol(sym: str, kind: str) -> str:
    """yfinance usa 'BTC-USD' etc."""
    if kind == "CRYPTO":
        if "-" in sym:
            return sym.upper()
        # tenta mapear BTC → BTC-USD
        return f"{sym.upper()}-USD"
    return sym.upper()

def _fmp_hist_prices(sym: str, start: dt.date, end: dt.date, kind: str) -> Dict[str, float]:
    """
    Baixa fechamento diário via FMP. Retorna { 'YYYY-MM-DD': close }.
    """
    api = os.getenv("FMP_API_KEY")
    if not api:
        return {}
    fmp_sym = _fmt_fmp_symbol(sym, kind)
    url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{fmp_sym}"
    params = {"from": start.isoformat(), "to": end.isoformat(), "apikey": api}
    try:
        r = requests.get(url, params=params, timeout=10)
        if not r.ok:
            return {}
        data = r.json() or {}
        hist = data.get("historical") or []
        out = {}
        for row in hist:
            d = row.get("date")
            c = row.get("close")
            if d and c is not None:
                out[str(d)] = float(c)
        return out
    except Exception:
        return {}

def _yf_hist_prices(sym: str, start: dt.date, end: dt.date, kind: str) -> Dict[str, float]:
    """Fallback com yfinance."""
    if yf is None:
        return {}
    try:
        yf_sym = _yf_symbol(sym, kind)
        t = yf.Ticker(yf_sym)
        df = t.history(start=start.isoformat(), end=(end + dt.timedelta(days=1)).isoformat(), interval="1d", auto_adjust=True)
        if df is None or df.empty or "Close" not in df.columns:
            return {}
        out = {}
        for idx, row in df.iterrows():
            d = idx.date().isoformat()
            c = float(row["Close"])
            out[d] = c
        return out
    except Exception:
        return {}

def _pick_price_for_day(prices: Dict[str, float], target: dt.date, start: dt.date, end: dt.date) -> Optional[float]:
    """
    Tenta pegar o preço de 'target'. Se não há nesse dia (feriado),
    procura o dia útil mais próximo ANTERIOR dentro do intervalo.
    """
    d = target
    while d >= start:
        v = prices.get(d.isoformat())
        if v is not None:
            return v
        d -= dt.timedelta(days=1)
    # se nada anterior, tenta pra frente (muito raro; evita ficar sem dado)
    d = target + dt.timedelta(days=1)
    while d <= end:
        v = prices.get(d.isoformat())
        if v is not None:
            return v
        d += dt.timedelta(days=1)
    return None

def _build_row(sym: str, kind: str, name_lookup: Dict[str, str],
               start: dt.date, end: dt.date,
               fwd_label: str) -> Optional[Dict[str, Any]]:
    """Monta uma linha da tabela mensal para um símbolo."""
    # baixa históricos
    prices = _fmp_hist_prices(sym, start, end, kind) or _yf_hist_prices(sym, start, end, kind)
    if not prices:
        return None

    f1 = _first_friday(start, end)
    f2 = _last_friday(start, end)

    p0 = _pick_price_for_day(prices, f1, start, end)
    p1 = _pick_price_for_day(prices, f2, start, end)

    if p0 is None and p1 is None:
        return None

    chg = None
    if p0 not in (None, 0) and p1 is not None:
        try:
            chg = (float(p1) / float(p0) - 1.0) * 100.0
        except Exception:
            chg = None

    return {
        "symbol": sym,
        "company_name": name_lookup.get(sym, sym),
        "p0": p0,
        "p1": p1,
        "chg": chg,
        "label": fwd_label,  # redundante, útil se quiser
    }

def build_monthly_rows(payload: Dict[str, Any], *, today: Optional[dt.date] = None) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Calcula linhas para a tabela mensal a partir de TODOS os ativos do payload.
    Retorna (monthly_label, rows).
    """
    if today is None:
        today = dt.date.today()
    start, end = _month_bounds(today)

    # etiqueta tipo "Setembro/2025"
    month_name = calendar.month_name[start.month]
    monthly_label = f"{month_name}/{start.year}"

    # lookup de nomes legíveis
    name_lookup: Dict[str, str] = {}
    for group in [
        "etfs_cons", "etfs_mod", "etfs_agr",
        "stocks_mod", "stocks_arj", "stocks_opp",
        "reits_cons", "smallcaps_arj", "hedge", "crypto"
    ]:
        for it in (payload.get(group) or []):
            sym = (it.get("symbol") or "").strip().upper()
            nm  = it.get("company_name") or it.get("name") or it.get("longName") or sym
            if sym:
                name_lookup[sym] = nm

    rows: List[Dict[str, Any]] = []
    for sym, kind in _collect_symbols(payload):
        row = _build_row(sym, kind, name_lookup, start, end, monthly_label)
        if row:
            rows.append(row)

    # ordena por maior/menor variação (opcional)
    rows.sort(key=lambda r: (r["chg"] is None, -(r["chg"] or -1e9)))
    return monthly_label, rows
