# src/services/carteiras/assembleia_report.py
from typing import Any, Dict, Optional
from io import BytesIO
import logging


from .assembleia.prep import enrich_payload_with_make_report, fill_auto_notes
from .assembleia.builder import generate_assembleia_report
from src.services.s3.aws_s3_service import upload_pdf_to_s3
from src.services.carteiras.assembleia.constants import NOME_RELATORIO_ASSEMBLEIA, BUCKET_RELATORIOS
from datetime import date, timedelta
import os, requests

logger = logging.getLogger(__name__)

def _first_friday(d: date) -> date:
    first = d.replace(day=1)
    shift = (4 - first.weekday()) % 7  # 4 = sexta
    return first + timedelta(days=shift)

def _last_friday(d: date) -> date:
    if d.month == 12:
        last = d.replace(day=31)
    else:
        last = (d.replace(month=d.month+1, day=1) - timedelta(days=1))
    while last.weekday() != 4:
        last -= timedelta(days=1)
    return last

def _fetch_close_price(symbol: str, day: date) -> float | None:
    api = os.getenv("FMP_API_KEY") or ""
    if not api:
        return None
    base = "https://financialmodelingprep.com/api/v3/historical-price-full"
    url = f"{base}/{symbol.upper()}?from={day:%Y-%m-%d}&to={day:%Y-%m-%d}&apikey={api}"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        js = r.json() or {}
        hist = js.get("historical") or []
        if hist:
            return float(hist[0].get("close"))
    except Exception:
        pass
    return None

def _collect_all_items(enriched: dict) -> list[dict]:
    buckets = [
        "bonds", "reits_cons","etfs_cons", 
        "etfs_mod", "stocks_mod",
        "etfs_agr", "stocks_arj","stocks_opp",
        "smallcaps_arj", "hedge",
        "crypto",
    ]
    out, seen = [], set()
    for g in buckets:
        for it in (enriched.get(g) or []):
            sym = (it.get("symbol") or "").strip().upper()
            if not sym or sym in seen:
                continue
            seen.add(sym)
            out.append(it)
    return out

def build_monthly_rows(enriched: dict) -> tuple[list[dict], str]:
    from datetime import timedelta, date  # ← import local para não alterar outros arquivos
    today = date.today()
    def _last_friday_on_or_before(d: date) -> date:
        while d.weekday() != 4:  # 4 = sexta
            d -= timedelta(days=1)
        return d
    last_friday = _last_friday_on_or_before(today)
    four_fridays_ago = last_friday - timedelta(weeks=4)
    label = f"{today:%B/%Y}".title()

    rows = []
    # --- placeholders para BONDS: 6 linhas vazias, em azul ---
    for _ in range(6):
        rows.append({
            "symbol": "",              # vazio → você preenche manualmente depois
            "company_name": "",
            "p0": None,
            "p1": None,
            "chg": None,
            "group": "bonds",          # importante p/ colorir azul
            "placeholder_bond": True,  # flag p/ o renderer saber que é vazio
        })
    for it in _collect_all_items(enriched):
        sym = (it.get("symbol") or "").upper()
        name = it.get("company_name") or it.get("name") or sym
        group = _group_of_symbol(enriched, sym)
        color = _rgb_for_group(group)
        p_first = _fetch_close_price(sym, four_fridays_ago)  # ← usa 4 sextas atrás
        p_now   = it.get("unit_price")  # já vem do enrich
        chg = None
        if p_first not in (None, 0) and p_now not in (None, 0):
            chg = ((float(p_now)/float(p_first))-1.0)*100.0
        rows.append({
            "symbol": sym,
            "company_name": name,
            "p0": p_first,
            "p1": p_now,
            "chg": chg,
            "group": group,
            "color": color,  # (r,g,b) em 0..1
        })
        

    return rows, label

# === abaixo das helpers já existentes ===
def _group_of_symbol(enriched: dict, sym: str) -> str:
    buckets = [
        ("bonds", "bonds"), ("reits_cons", "reits_cons"),
        ("etfs_cons", "etfs_cons"),  ("etfs_mod", "etfs_mod"), ("stocks_mod", "stocks_mod"),
        ("etfs_agr", "etfs_agr"), ("stocks_arj", "stocks_arj"), ("stocks_opp", "stocks_opp"),
        ("smallcaps_arj", "smallcaps_arj"), ("hedge", "hedge"),
        ("crypto", "crypto"), 
    ]
    sym = (sym or "").upper()
    for key, name in buckets:
        for it in (enriched.get(key) or []):
            if (it.get("symbol") or "").upper() == sym:
                return name
    return ""

def _rgb_for_group(group: str) -> tuple[float, float, float]:
    # azul
    if group in ("bonds", "reits_cons", "etfs_cons"):
        return (0.20, 0.55, 0.95)
    # verde
    if group in ("etfs_mod", "stocks_mod"):
        return (0.10, 0.80, 0.35)
    # vermelho (demais)
    return (1.0, 1.0, 0.0)




def build_report_assembleia_from_payload(payload: Dict[str, Any], selected_symbol: Optional[str] = None) -> BytesIO:
    
    enriched = enrich_payload_with_make_report(payload)
    enriched = fill_auto_notes(enriched)  
    monthly_rows, monthly_label = build_monthly_rows(enriched)

    # 2) Extrair listas para o builder
    bonds          = enriched.get("bonds", []) or []
    etfs_cons      = enriched.get("etfs_cons", []) or []
    etfs_mod       = enriched.get("etfs_mod", []) or []
    etfs_agr       = enriched.get("etfs_agr", []) or []
    stocks_mod     = enriched.get("stocks_mod", []) or []
    stocks_arj     = enriched.get("stocks_arj", []) or []
    stocks_opp     = enriched.get("stocks_opp", []) or []
    reits_cons     = enriched.get("reits_cons", []) or []
    smallcaps_arj  = enriched.get("smallcaps_arj", []) or []
    crypto         = enriched.get("crypto", []) or []
    hedge          = enriched.get("hedge", []) or []

    custom_ranges = []
    if hasattr(payload, 'custom_ranges') and payload.custom_ranges:
        custom_ranges = [cr.model_dump() if hasattr(cr, 'model_dump') else cr for cr in payload.custom_ranges]
    elif isinstance(payload, dict) and payload.get('custom_ranges'):
        custom_ranges = payload['custom_ranges']
        
    text_assets = []
    if hasattr(payload, 'text_assets') and payload.text_assets:
        text_assets = [ta.model_dump() if hasattr(ta, 'model_dump') else ta for ta in payload.text_assets]
    elif isinstance(payload, dict) and payload.get('text_assets'):
        text_assets = payload['text_assets']

    logger.info(
        "[ASSEMBLEIA] pós-prep: bonds=%d, etfs_cons=%d, etfs_mod=%d, etfs_agr=%d, "
        "stocks_mod=%d, stocks_arj=%d, stocks_opp=%d, reits_cons=%d, smallcaps_arj=%d, "
        "crypto=%d, hedge=%d, monthly_rows=%d",
        len(bonds), len(etfs_cons), len(etfs_mod), len(etfs_agr),
        len(stocks_mod), len(stocks_arj), len(stocks_opp),
        len(reits_cons), len(smallcaps_arj), len(crypto), len(hedge),
        len(monthly_rows),
    )
    
    

    # 3) Montar PDF
    buffer = generate_assembleia_report(
        bonds=bonds,
        etfs_cons=etfs_cons, etfs_mod=etfs_mod, etfs_agr=etfs_agr,
        stocks_mod=stocks_mod, stocks_arj=stocks_arj, stocks_opp=stocks_opp,
        reits_cons=reits_cons, smallcaps_arj=smallcaps_arj, crypto=crypto, hedge=hedge,
        monthly_rows=monthly_rows, monthly_label=monthly_label, custom_range_pages=custom_ranges,
        text_assets=text_assets,
        fetch_price_fn=_fetch_close_price,
    )

    # 4) Upload (opcional) e retorno
    upload_pdf_to_s3(buffer, NOME_RELATORIO_ASSEMBLEIA, BUCKET_RELATORIOS)
    logger.info("Relatorio gerado com sucesso!")
    return buffer
