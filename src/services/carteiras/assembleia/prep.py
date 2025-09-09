# src/services/carteiras/assembleia/prep.py

import logging
import json, os

from typing import Dict, Any, List, Optional, Tuple

from src.services.carteiras.make_report import (
    fetch_equity,
    fetch_crypto,
    generate_chart,
)

logger = logging.getLogger(__name__)
_NOTES_CACHE = None

def _load_notes() -> dict:
    """Carrega notes_catalog.json uma única vez (cache)."""
    global _NOTES_CACHE
    if _NOTES_CACHE is not None:
        return _NOTES_CACHE

    base_dir = os.path.dirname(__file__)
    path = os.path.join(base_dir, "notes.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                _NOTES_CACHE = json.load(f) or {}
        except Exception as e:
            logging.getLogger(__name__).warning("[notes] falha ao ler JSON: %s", e)
            _NOTES_CACHE = {}
    else:
        _NOTES_CACHE = {}
    return _NOTES_CACHE
# Campos que queremos observar no diff de mudanças (normalizando para snake_case)
_DIFF_KEYS = [
    "unit_price", "dividend_yield", "average_growth",
    "ema10", "ema20", "ema200",
    "chart", "vs", "vp", "vr",
    "company_name", "sector",
    "target_price",
]

def _norm_key(k: str) -> str:
    """Normaliza chave camelCase -> snake_case para comparação/log."""
    # Map rápido de alguns campos comuns
    m = {
        "unitPrice": "unit_price",
        "dividendYield": "dividend_yield",
        "averageGrowth": "average_growth",
        "targetPrice": "target_price",
        "ema_10": "ema10", "ema_20": "ema20", "ema_200": "ema200",
    }
    return m.get(k, k)

def _keep_manual_fields(dst: Dict[str, Any], src: Dict[str, Any], keys: List[str]) -> None:
    """Preserva no resultado (dst) alguns campos 'manuais' do payload original (src)."""
    for k in keys:
        if src.get(k) is not None:
            dst[k] = src[k]

def _coalesce(*vals):
    for v in vals:
        if v is not None:
            return v
    return None

def _to_float_or_none(v) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except Exception:
        return None

def _diff_report(before: Dict[str, Any], after: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Retorna (changed, added) considerando _DIFF_KEYS."""
    b = { _norm_key(k): before.get(k) for k in list(before.keys()) + [ "unitPrice","dividendYield","averageGrowth","targetPrice","ema_10","ema_20","ema_200" ] }
    a = { _norm_key(k): after.get(k)  for k in list(after.keys())  + [ "unitPrice","dividendYield","averageGrowth","targetPrice","ema_10","ema_20","ema_200" ] }
    changed, added = [], []
    for k in _DIFF_KEYS:
        if k not in a and k not in b:
            continue
        if k not in b and k in a and a[k] is not None:
            added.append(k)
        else:
            if (k in a) and (a[k] != b.get(k)):
                changed.append(k)
    return sorted(set(changed)), sorted(set(added))

def _force_equity(it: Dict[str, Any], is_etf: bool) -> Dict[str, Any]:
    """
    Sempre recalcula via fetch_equity; sobrepõe o retorno, mas preserva
    alguns campos "manuais" úteis do payload original (ex.: logo_path).
    """
    original = dict(it)  # cópia para diff

    sym = (it.get("symbol") or it.get("ticker") or "").strip().upper()
    qty = _to_float_or_none(it.get("quantity")) or 0.0
    tp  = _coalesce(it.get("target_price"), it.get("targetPrice"))
    tp  = _to_float_or_none(tp)
    score = it.get("score")  # pode ser str/float; fetch_equity lida

    if not sym:
        logger.warning("[ASSEMBLEIA:prep] item sem símbolo: %r", it)
        return it

    try:
        vr_payload = _to_float_or_none(original.get("vr"))
        fetched = fetch_equity(
            sym, qty,
            is_etf=is_etf,
            antifragile=False,
            target_price=tp,
            score=score,
            vr=vr_payload,
        ) or {}
    except Exception as e:
        logger.warning("[ASSEMBLEIA:prep] fetch_equity falhou para %s: %s", sym, e)
        fetched = {}

    # Base = fetched (recalculado sempre)
    out = dict(fetched)

    # Garanta o símbolo em maiúsculas
    out["symbol"] = sym

    # Se fetch não trouxe chart, tenta gerar (mantém target se houver)
    if not out.get("chart"):
        try:
            gen = generate_chart(sym, weekly_bars=[], target_price=_coalesce(out.get("target_price"), tp))
            if gen:
                out["chart"] = gen
        except Exception:
            pass

    # Preserve alguns campos manuais do payload original (se existirem)
    _keep_manual_fields(out, original, [
        "logo_path", "logoPath",     # logos customizadas
        # "chart",                    # se quiser preservar o chart do body, descomente
        # "target_price", "targetPrice",  # já passamos tp no fetch; opcional preservar
    ])
    _preserve_note(original, out)
    # Diff para logging
    changed, added = _diff_report(original, out)
    if changed or added:
        logger.info("[ASSEMBLEIA:prep] %s atualizado. changed=%s added=%s", sym, changed, added)
    else:
        logger.info("[ASSEMBLEIA:prep] %s sem mudanças relevantes.", sym)

    return out

def _force_crypto(it: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recalcula preço/dados via fetch_crypto; preserva entry/target/logo do body.
    Mantém chart do body (se existir) — páginas de cripto esperam caminho existente.
    """
    original = dict(it)
    sym = (it.get("symbol") or "").strip().upper()
    if not sym:
        logger.warning("[ASSEMBLEIA:prep] crypto sem símbolo: %r", it)
        return it

    qty = _to_float_or_none(it.get("quantity")) or 0.0
    expected_growth = _coalesce(it.get("average_growth"), it.get("averageGrowth"))
    company_name = it.get("company_name") or it.get("name")

    try:
        fetched = fetch_crypto(sym, quantity=qty, company_name=company_name, expected_growth=expected_growth) or {}
    except Exception as e:
        logger.warning("[ASSEMBLEIA:prep] fetch_crypto falhou para %s: %s", sym, e)
        fetched = {}

    # Base = fetched
    out = dict(fetched)
    out["symbol"] = sym

    # Preservar campos manuais importantes
    _keep_manual_fields(out, original, [
        "entry_price", "target_price", "logo_path", "chart",
        "entryPrice", "targetPrice", "logoPath",
    ])
    _preserve_note(original, out)
    changed, added = _diff_report(original, out)
    if changed or added:
        logger.info("[ASSEMBLEIA:prep] CRYPTO %s atualizado. changed=%s added=%s", sym, changed, added)
    else:
        logger.info("[ASSEMBLEIA:prep] CRYPTO %s sem mudanças relevantes.", sym)

    return out

def _prep_bucket_equities(bucket: List[Dict[str, Any]] | None, is_etf: bool) -> List[Dict[str, Any]]:
    if not bucket:
        return []
    return [_force_equity(dict(it), is_etf=is_etf) for it in bucket]

def _prep_bucket_crypto(bucket: List[Dict[str, Any]] | None) -> List[Dict[str, Any]]:
    if not bucket:
        return []
    return [_force_crypto(dict(it)) for it in bucket]

def _preserve_note(orig: dict, out: dict) -> dict:
    """Se o item original tiver 'note', preserva no item enriquecido."""
    n = (orig or {}).get("note")
    if n:
        out["note"] = n
    return out


NOTE_KIND = {
    "etfs_cons":     "ETF",
    "etfs_mod":      "ETF",
    "etfs_agr":      "ETF",
    "stocks_mod":    "STOCK",
    "stocks_arj":    "STOCK",
    "stocks_opp":    "STOCK",
    "reits_cons":    "REIT",
    "smallcaps_arj": "SMALLCAP",
    "hedge":         "HEDGE",
    "crypto":        "CRYPTO",   # ativei também para cripto
}



NOTE_GROUPS = (
    "etfs_cons","etfs_mod","etfs_agr",
    "stocks_mod","stocks_arj","stocks_opp",
    "reits_cons","smallcaps_arj",
    "hedge","crypto"
)

def fill_auto_notes(payload: dict, *, max_notes: int | None = None) -> dict:
    """
    Preenche item['note'] **apenas** quando vazia, usando notes_catalog.json.
    - Deduplica por símbolo (não gera nota repetida em excesso).
    - max_notes: limite opcional de quantas notas preencher nesta execução.
    """
    catalog = _load_notes()
    filled = 0
    seen = set()

    for group in NOTE_GROUPS:
        items = payload.get(group) or []
        for it in items:
            sym = (it.get("symbol") or "").upper().strip()
            if not sym or (group, sym) in seen:
                continue
            seen.add((group, sym))

            if (it.get("note") or "").strip():
                continue  # já tem nota no payload → preservar

            note = catalog.get(sym)
            if note:
                it["note"] = note
                filled += 1
                if max_notes is not None and filled >= max_notes:
                    return payload

    return payload




def enrich_payload_with_make_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Reprocessa SEMPRE usando as funções do make_report.
    - ETFs/Ações: fetch_equity (is_etf True/False) + chart (fallback).
    - Crypto: fetch_crypto; preserva entry/target/logo/chart do body.
    - Bonds: mantidos (não há cálculo específico aqui).
    """
    enriched = dict(payload)  # cópia rasa

    # ETFs
    enriched["etfs_cons"] = _prep_bucket_equities(enriched.get("etfs_cons"), is_etf=True)
    enriched["etfs_mod"]  = _prep_bucket_equities(enriched.get("etfs_mod"),  is_etf=True)
    enriched["etfs_agr"]  = _prep_bucket_equities(enriched.get("etfs_agr"),  is_etf=True)

    # Ações
    enriched["stocks_mod"] = _prep_bucket_equities(enriched.get("stocks_mod"), is_etf=False)
    enriched["stocks_arj"] = _prep_bucket_equities(enriched.get("stocks_arj"), is_etf=False)
    enriched["stocks_opp"] = _prep_bucket_equities(enriched.get("stocks_opp"), is_etf=False)
    enriched["reits_cons"] = _prep_bucket_equities(enriched.get("reits_cons"), is_etf=False)

    # (se usar smallcaps)
    enriched["smallcaps_arj"] = _prep_bucket_equities(enriched.get("smallcaps_arj"), is_etf=False)
    # Criptos
    enriched["crypto"] = _prep_bucket_crypto(enriched.get("crypto"))
    enriched["hedge"] = _prep_bucket_equities(enriched.get("hedge"), is_etf=False)

    return enriched
