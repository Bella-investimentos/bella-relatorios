# src/services/fmp/targets.py
from __future__ import annotations
import os, time, logging
from dataclasses import dataclass
from typing import Iterable, List, Dict, Optional, Tuple
import requests

log = logging.getLogger(__name__)

FMP_V4 = "https://financialmodelingprep.com/api/v4/price-target-summary"

# ---------- Model ----------
@dataclass(frozen=True)
class PriceTargetSummary:
    symbol: str
    target_avg: Optional[float]
    target_high: Optional[float]
    target_low: Optional[float]
    last_updated: Optional[str]  # iso string quando a FMP fornece
    source: str = "fmp"

# ---------- Helpers ----------
def _get_api_key(api_key: Optional[str] = None) -> str:
    k = api_key or os.getenv("FMP_API_KEY") or ""
    if not k:
        raise RuntimeError("FMP_API_KEY não definido.")
    return k

def _norm_symbol(sym: str) -> str:
    # A FMP geralmente usa símbolos “puros” (AAPL, MSFT, AMZN). Para cripto/pares, você já trata em outros pontos.
    return (sym or "").strip().upper()

def _get(url: str, params: dict, tries: int = 3, backoff: float = 1.6, timeout: int = 20) -> dict | list | None:
    last_err = None
    for i in range(tries):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            if r.ok:
                return r.json()
            last_err = RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
        except Exception as e:
            last_err = e
        time.sleep(backoff ** (i + 1))
    log.warning("FMP GET falhou: %s", last_err)
    return None

def _parse_summary(sym: str, js: dict | list | None):
    if not js:
        return None
    row = js[0] if isinstance(js, list) and js else js

    def pick_float(*keys):
        for k in keys:
            v = row.get(k)
            if v is not None:
                try: return float(v)
                except: pass
        return None

    # 1) tenta campos clássicos
    target_avg = pick_float("priceTargetAverage", "targetMean", "average", "target_avg")

    # 2) fallback pros agregados do seu payload
    if target_avg is None:
        target_avg = (
            pick_float("lastMonthAvgPriceTarget")
            or pick_float("lastQuarterAvgPriceTarget")
            or pick_float("lastYearAvgPriceTarget")
            or pick_float("allTimeAvgPriceTarget")
        )

    target_high = pick_float("priceTargetHigh", "targetHigh", "high", "target_high")
    target_low  = pick_float("priceTargetLow",  "targetLow",  "low",  "target_low")

    last_updated = row.get("lastUpdated") or row.get("updatedAt") or row.get("date")

    return PriceTargetSummary(
        symbol=sym,
        target_avg=target_avg,
        target_high=target_high,
        target_low=target_low,
        last_updated=last_updated,
        source="fmp",
    )

# ---------- Public API ----------
def fetch_price_target_summary(symbol: str, api_key: Optional[str] = None) -> PriceTargetSummary | None:
    """
    Busca o resumo de price target na FMP para 1 símbolo.
    """
    sym = _norm_symbol(symbol)
    k = _get_api_key(api_key)
    js = _get(FMP_V4, {"symbol": sym, "apikey": k})
    return _parse_summary(sym, js)

def fetch_price_targets_batch(symbols: Iterable[str], api_key: Optional[str] = None) -> Dict[str, PriceTargetSummary]:
    """
    Busca price targets para vários símbolos (chamadas 1 a 1, com backoff).
    Retorna um dict {SYMBOL: PriceTargetSummary}.
    """
    out: Dict[str, PriceTargetSummary] = {}
    k = _get_api_key(api_key)
    for s in symbols:
        sym = _norm_symbol(s)
        if not sym:
            continue
        js = _get(FMP_V4, {"symbol": sym, "apikey": k})
        pt = _parse_summary(sym, js)
        if pt:
            out[sym] = pt
    return out

def enrich_targets(items: List[Dict], *, prefer_payload: bool = True, api_key: Optional[str] = None) -> List[Dict]:
    """
    Recebe uma lista de dicts com pelo menos {"symbol": "..."} e opcional "target_price".
    Preenche/ajusta "target_price" e marca "target_source" como "payload" ou "fmp".
    """
    # 1) símbolos únicos
    symbols = sorted({ _norm_symbol(d.get("symbol","")) for d in items if d.get("symbol") })
    # 2) consulta FMP
    m = fetch_price_targets_batch(symbols, api_key=api_key)
    # 3) enriquece
    out: List[Dict] = []
    for d in items:
        sym = _norm_symbol(d.get("symbol",""))
        if not sym:
            out.append(d); continue
        payload_target = d.get("target_price")
        if prefer_payload and payload_target not in (None, ""):
            # mantém o do payload
            d["target_price"] = float(payload_target)
            d["target_source"] = "payload"
        else:
            pt = m.get(sym)
            if pt and pt.target_avg is not None:
                d["target_price"] = float(pt.target_avg)
                d["target_source"] = "fmp"
            else:
                # nada encontrado — mantém como está
                d.setdefault("target_price", None)
                d["target_source"] = d.get("target_source") or "none"
        out.append(d)
    return out

def build_target_map(items: List[Dict], *, prefer_payload: bool = True, api_key: Optional[str] = None) -> Dict[str, float | None]:
    """
    Atalho: devolve {SYMBOL: target_price} após enriquecer.
    """
    enriched = enrich_targets(items, prefer_payload=prefer_payload, api_key=api_key)
    return { _norm_symbol(d.get("symbol","")): d.get("target_price") for d in enriched if d.get("symbol") }
