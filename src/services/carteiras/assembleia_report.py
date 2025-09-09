# src/services/carteiras/assembleia_report.py
from typing import Any, Dict, Optional
from io import BytesIO
import logging
from .assembleia.monthly_calc import build_monthly_rows
from .assembleia.prep import enrich_payload_with_make_report, fill_auto_notes
from .assembleia.builder import generate_assembleia_report
from src.services.s3.aws_s3_service import upload_pdf_to_s3
from src.services.carteiras.assembleia.constants import NOME_RELATORIO_ASSEMBLEIA, BUCKET_RELATORIOS

logger = logging.getLogger(__name__)

def build_report_assembleia_from_payload(payload: Dict[str, Any], selected_symbol: Optional[str] = None) -> BytesIO:
    # 1) Enriquecer via make_report
    enriched = enrich_payload_with_make_report(payload)

    # 1.1) Preencher notas automaticamente onde estiver vazio (opcional: limitar)
    enriched = fill_auto_notes(enriched)  # ou fill_auto_notes(enriched, max_notes=5)
    monthly_label, monthly_rows = build_monthly_rows(payload)

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

    logger.info(
        "[ASSEMBLEIA] pós-prep: bonds=%d, etfs_cons=%d, etfs_mod=%d, etfs_agr=%d, "
        "stocks_mod=%d, stocks_arj=%d, stocks_opp=%d, reits_cons=%d, smallcaps_arj=%d, "
        "crypto=%d, hedge=%d",
        len(bonds), len(etfs_cons), len(etfs_mod), len(etfs_agr),
        len(stocks_mod), len(stocks_arj), len(stocks_opp),
        len(reits_cons), len(smallcaps_arj), len(crypto), len(hedge)
    )

    # 3) Montar PDF
    buffer = generate_assembleia_report(
        bonds=bonds,
        etfs_cons=etfs_cons, etfs_mod=etfs_mod, etfs_agr=etfs_agr,
        stocks_mod=stocks_mod, stocks_arj=stocks_arj, stocks_opp=stocks_opp,
        reits_cons=reits_cons, smallcaps_arj=smallcaps_arj, crypto=crypto, hedge=hedge,
        monthly_rows=monthly_rows, monthly_label=monthly_label,
    )

    # 4) Upload (opcional) e retorno
    upload_pdf_to_s3(buffer, NOME_RELATORIO_ASSEMBLEIA, BUCKET_RELATORIOS)
    logger.info("Relatorio gerado com sucesso!")

    return buffer
